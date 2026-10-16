#!/usr/local/bin/python3

import argparse
import hashlib
import json
import math
import os
import sys
import time as time_module
from datetime import datetime, time as datetime_time, timedelta, timezone
from getpass import getpass
from pathlib import Path

from requests.exceptions import HTTPError, RequestException
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

WYZE_EMAIL = os.environ.get("WYZE_EMAIL")
WYZE_PASSWORD = os.environ.get("WYZE_PASSWORD")
WYZE_KEY_ID = os.environ.get("WYZE_KEY_ID")
WYZE_API_KEY = os.environ.get("WYZE_API_KEY")

GARMIN_USERNAME = (
    os.environ.get("GARMIN_EMAIL")
    or os.environ.get("Garmin_username")
)

GARMIN_PASSWORD = (
    os.environ.get("GARMIN_PASSWORD")
    or os.environ.get("Garmin_password")
)

GARMIN_TOKEN_DIR = (
    os.environ.get("GARMINTOKENS")
    or "/wyze_garmin_sync/tokens"
)

# Prefer the descriptive variable name, but keep "token" for backward
# compatibility with older docker-compose files.
WYZE_TOKEN_FILE = (
    os.environ.get("WYZE_TOKEN_FILE")
    or os.environ.get("token")
    or "/wyze_garmin_sync/tokens/wyze_tokens.json"
)

try:
    BACKFILL_DELAY_SECONDS = max(
        0.0,
        float(os.environ.get("BACKFILL_DELAY_SECONDS", "1.0")),
    )
except ValueError:
    BACKFILL_DELAY_SECONDS = 1.0

WORK_DIR = "/wyze_garmin_sync"

# Store the new record checksum in the persistent token directory by default.
# CHECKSUM_FILE can override this if desired.
CHECKSUM_FILE_PATH = (
    os.environ.get("CHECKSUM_FILE")
    or os.path.join(GARMIN_TOKEN_DIR, "cksum.txt")
)

# Old versions stored an MD5 of wyze_scale.fit here. We only read this as a
# fallback during migration. Because the checksum algorithm changed, an old
# 32-character MD5 will naturally differ once and then be replaced by SHA-256.
LEGACY_CHECKSUM_FILE_PATH = os.path.join(WORK_DIR, "cksum.txt")


# -----------------------------------------------------------------------------
# Command-line arguments
# -----------------------------------------------------------------------------

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Synchronize Wyze Scale measurements to Garmin Connect."
    )

    parser.add_argument(
        "-timewindow",
        "--timewindow",
        nargs=2,
        metavar=("START_DATE", "END_DATE"),
        help=(
            "Upload all Wyze Scale readings in the requested inclusive time "
            "window. Examples: -timewindow '2026-01-01' '2026-09-30' or "
            "-timewindow '2026-01-01 08:00' '2026-01-31 18:00'."
        ),
    )

    return parser.parse_args()


def parse_date_value(value, *, is_end=False):
    """
    Parse a CLI date/time into a timezone-aware datetime.

    Accepted examples:
      2026-01-01
      2026-01-01 08:30
      2026-01-01 08:30:00
      2026-01-01T08:30
      2026-01-01T08:30:00
      2026-01-01T08:30:00-04:00

    Date-only end values include the entire end date.
    Naive values are interpreted in the container's local timezone.
    """
    value = value.strip()

    try:
        date_only = (
            len(value) == 10
            and value[4] == "-"
            and value[7] == "-"
        )

        if date_only:
            parsed = datetime.strptime(value, "%Y-%m-%d")
            if is_end:
                parsed = datetime.combine(parsed.date(), datetime_time.max)
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    except ValueError as exc:
        raise ValueError(
            f"Invalid date/time '{value}'. Use YYYY-MM-DD or an ISO date/time."
        ) from exc

    # For a naive datetime, astimezone() interprets it in the system/container
    # local timezone, including DST for that date.
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()

    return parsed


# -----------------------------------------------------------------------------
# Wyze authentication
# -----------------------------------------------------------------------------

def save_wyze_tokens(tokens):
    """Atomically save Wyze authentication information."""
    token_path = os.path.abspath(os.path.expanduser(WYZE_TOKEN_FILE))
    os.makedirs(os.path.dirname(token_path), exist_ok=True)

    tmp_file = token_path + ".tmp"

    with open(tmp_file, "w", encoding="utf-8") as token_file:
        json.dump(tokens, token_file)

    os.chmod(tmp_file, 0o600)
    os.replace(tmp_file, token_path)


def load_wyze_tokens():
    """Load cached Wyze authentication information."""
    try:
        with open(WYZE_TOKEN_FILE, "r", encoding="utf-8") as token_file:
            tokens = json.load(token_file)

        if not tokens.get("access_token"):
            return None

        return tokens

    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def credential_login_to_wyze(*, reauthentication=False):
    """Perform exactly one Wyze username/password/API-key login attempt."""
    if not all((WYZE_EMAIL, WYZE_PASSWORD, WYZE_KEY_ID, WYZE_API_KEY)):
        print(
            "Wyze credentials are incomplete. WYZE_EMAIL, WYZE_PASSWORD, "
            "WYZE_KEY_ID and WYZE_API_KEY are required for a fresh login."
        )
        return None, None

    if reauthentication:
        print("Performing fresh Wyze authentication...")
    else:
        print("Performing initial Wyze authentication...")

    try:
        client = Client()

        response = client.login(
            email=WYZE_EMAIL,
            password=WYZE_PASSWORD,
            key_id=WYZE_KEY_ID,
            api_key=WYZE_API_KEY,
        )

        access_token = response.get("access_token")
        refresh_token = response.get("refresh_token")
        user_id = response.get("user_id")

        if not access_token or not refresh_token:
            print(
                "Wyze login did not return both an access token and a refresh "
                "token."
            )
            return None, None

        tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": user_id,
        }

        save_wyze_tokens(tokens)

        if reauthentication:
            print("Wyze re-authentication successful.")
            print("New Wyze authentication tokens saved.")
        else:
            print("Wyze authentication successful.")
            print("Wyze authentication tokens saved.")

        return client, tokens

    except HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None

        if status == 429:
            print(
                "Wyze authentication rate limited (HTTP 429). "
                "No additional login attempt will be made during this run."
            )
        else:
            print(f"Wyze HTTP authentication error: {exc}")

    except WyzeApiError as exc:
        print(f"Wyze API authentication error: {exc}")

    except RequestException as exc:
        print(f"Wyze network error: {exc}")

    except Exception as exc:
        print(f"Unexpected Wyze authentication error: {exc}")

    return None, None


def login_to_wyze():
    """
    Reuse cached Wyze tokens whenever possible.

    A full credential login is only performed when no cached token exists.
    """
    tokens = load_wyze_tokens()

    if tokens:
        print("Using cached Wyze authentication token.")

        client = Client(
            token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
        )

        # Required by the Wyze Scale API for user-specific records.
        if tokens.get("user_id"):
            client._user_id = tokens["user_id"]

        return client, tokens

    print("No cached Wyze token found.")
    return credential_login_to_wyze(reauthentication=False)


def wyze_refresh_token_is_invalid(exc):
    """Return True when Wyze explicitly rejects the stored refresh token."""
    text = str(exc).lower()

    return (
        "refresh token is error" in text
        or ("2002" in text and "refresh token" in text)
    )


def refresh_wyze_token(client, tokens):
    """
    Attempt to refresh the Wyze access token.

    Returns:
      "success" - refresh succeeded and the rotated token pair was saved
      "invalid" - refresh token itself is unavailable/invalid
      "failed"  - temporary or unexpected failure; do not credential-login
    """
    if not tokens:
        print("No cached Wyze token information available.")
        return "invalid"

    if not tokens.get("refresh_token"):
        print("No Wyze refresh token available.")
        return "invalid"

    try:
        print("Refreshing Wyze authentication token...")
        response = client.refresh_token()
        refreshed = response.get("data", {})

        new_access_token = refreshed.get("access_token")
        new_refresh_token = refreshed.get("refresh_token")

        if not new_access_token or not new_refresh_token:
            print(
                "Wyze refresh response did not contain both a new access token "
                "and a new refresh token."
            )
            return "failed"

        # Wyze rotates both values during refresh. Save both immediately.
        tokens["access_token"] = new_access_token
        tokens["refresh_token"] = new_refresh_token
        save_wyze_tokens(tokens)

        print("Wyze authentication token refreshed successfully.")
        return "success"

    except Exception as exc:
        print(f"Unable to refresh Wyze authentication token: {exc}")

        if wyze_refresh_token_is_invalid(exc):
            print(
                "Wyze refresh token is no longer valid. "
                "A fresh Wyze login is required."
            )
            return "invalid"

        return "failed"


def get_wyze_devices(client, tokens):
    """
    Retrieve devices and recover authentication when possible.

    Returns (client, tokens, devices). Returning the client is important because
    an invalid refresh token requires a brand-new Client instance.
    """
    try:
        return client, tokens, client.devices_list()

    except Exception as exc:
        print(f"Cached Wyze token failed: {exc}")

    refresh_status = refresh_wyze_token(client, tokens)

    if refresh_status == "success":
        try:
            return client, tokens, client.devices_list()
        except Exception as exc:
            print(f"Wyze API still unavailable after token refresh: {exc}")
            return None, None, None

    if refresh_status == "invalid":
        new_client, new_tokens = credential_login_to_wyze(
            reauthentication=True
        )

        if new_client is None:
            print("Unable to re-authenticate with Wyze. Stopping this run.")
            return None, None, None

        try:
            devices = new_client.devices_list()
            return new_client, new_tokens, devices
        except Exception as exc:
            print(f"Wyze API unavailable after re-authentication: {exc}")
            return None, None, None

    print(
        "Wyze token refresh failed for a temporary or unexpected reason. "
        "Stopping this run without performing another credential login."
    )
    return None, None, None


# -----------------------------------------------------------------------------
# Garmin authentication
# -----------------------------------------------------------------------------

def login_to_garmin():
    """
    Garmin authentication flow:

    1. Use garmin_tokens.json if it exists.
    2. If the token is unavailable/invalid and this is an interactive terminal,
       perform credential login and prompt for MFA if required.
    3. In a non-interactive cron run, never wait for MFA or repeatedly attempt
       credential authentication.
    """
    token_dir = Path(GARMIN_TOKEN_DIR).expanduser()
    token_dir.mkdir(parents=True, exist_ok=True)
    token_file = token_dir / "garmin_tokens.json"

    if token_file.is_file():
        print("Garmin token found. Trying cached authentication...")

        try:
            garmin = Garmin()
            garmin.login(str(token_dir))

            print("Using cached Garmin authentication token.")
            return garmin

        except GarminConnectTooManyRequestsError as exc:
            print(f"Garmin rate limit while using cached token: {exc}")
            return None

        except (
            GarminConnectAuthenticationError,
            GarminConnectConnectionError,
        ) as exc:
            print(f"Cached Garmin authentication failed: {exc}")
            print("Stored Garmin token may be invalid or expired.")

        except Exception as exc:
            print(f"Unexpected error loading Garmin token: {exc}")
            return None

    else:
        print(f"No Garmin token found at {token_file}")

    if not sys.stdin.isatty():
        print("Garmin authentication requires an interactive login.")
        print("Run:")
        print("  docker compose run --rm wyzegarminconnect")
        print("to authenticate and create garmin_tokens.json.")
        return None

    print()
    print("Starting interactive Garmin authentication.")
    print()

    email = GARMIN_USERNAME or input("Garmin email: ").strip()
    password = GARMIN_PASSWORD or getpass("Garmin password: ")

    if not email or not password:
        print("Garmin username/password were not supplied.")
        return None

    try:
        garmin = Garmin(
            email=email,
            password=password,
            prompt_mfa=lambda: input("Enter Garmin MFA code: ").strip(),
        )

        # These mobile strategies were observed returning 429 for this project.
        # Skip them during initial credential authentication and use the
        # widget/portal strategies instead.
        if (
            hasattr(garmin, "client")
            and hasattr(garmin.client, "skip_strategies")
        ):
            garmin.client.skip_strategies.update({
                "mobile+cffi",
                "mobile+requests",
            })

        print("Authenticating with Garmin Connect...")
        garmin.login(str(token_dir))

        print("Garmin authentication successful.")
        print(f"Garmin token saved to {token_file}")
        return garmin

    except GarminConnectTooManyRequestsError as exc:
        print(f"Garmin authentication rate limited: {exc}")

    except GarminConnectAuthenticationError as exc:
        print(f"Garmin authentication failed: {exc}")

    except GarminConnectConnectionError as exc:
        print(f"Garmin connection error: {exc}")

    except KeyboardInterrupt:
        print()
        print("Garmin authentication cancelled.")

    except Exception as exc:
        print(f"Unexpected Garmin authentication error: {exc}")

    return None


# -----------------------------------------------------------------------------
# Record helpers / checksum
# -----------------------------------------------------------------------------

def optional_float(value):
    """Convert a value to a finite float, or return None if unavailable."""
    if value is None or value == "":
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    return result


def optional_int(value):
    """Convert an optional numeric value to int, or return None."""
    result = optional_float(value)

    if result is None:
        return None

    return int(result)


def record_datetime(record):
    """Convert a Wyze millisecond epoch timestamp to local timezone."""
    measure_ts = optional_float(
        getattr(record, "measure_ts", None)
    )

    if measure_ts is None:
        raise ValueError(
            "Wyze record does not contain a valid measure_ts."
        )

    return datetime.fromtimestamp(
        measure_ts / 1000,
        tz=timezone.utc,
    ).astimezone()


def record_identity(record):
    """Build a stable key for deduplicating records returned by Wyze."""
    data_id = (
        getattr(record, "id", None)
        or getattr(record, "data_id", None)
    )

    if data_id not in (None, "", "None"):
        return ("data_id", str(data_id))

    measure_ts = optional_float(
        getattr(record, "measure_ts", None)
    )

    weight = optional_float(
        getattr(record, "weight", None)
    )

    return (
        "measurement",
        None if measure_ts is None else int(measure_ts),
        None if weight is None else round(weight, 4),
    )


def measurement_checksum(record):
    """
    Hash the Wyze measurement identity, not a generated FIT file.

    This intentionally uses record ID + timestamp + weight rather than every
    optional body-composition field. If Wyze later enriches the same reading
    with an optional field, it should not be mistaken for a new weigh-in.
    """
    data_id = (
        getattr(record, "id", None)
        or getattr(record, "data_id", None)
    )

    measure_ts = optional_float(
        getattr(record, "measure_ts", None)
    )

    weight = optional_float(
        getattr(record, "weight", None)
    )

    payload = {
        "id": (
            None
            if data_id in (None, "", "None")
            else str(data_id)
        ),
        "measure_ts": (
            None
            if measure_ts is None
            else int(measure_ts)
        ),
        "weight": (
            None
            if weight is None
            else round(weight, 4)
        ),
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def load_previous_checksum():
    """Load the previous successful latest-reading checksum."""
    paths = [CHECKSUM_FILE_PATH]

    if (
        os.path.abspath(LEGACY_CHECKSUM_FILE_PATH)
        != os.path.abspath(CHECKSUM_FILE_PATH)
    ):
        paths.append(LEGACY_CHECKSUM_FILE_PATH)

    for path in paths:
        try:
            with open(
                path,
                "r",
                encoding="utf-8",
            ) as checksum_file:
                value = checksum_file.read().strip()

            if value:
                if (
                    path == LEGACY_CHECKSUM_FILE_PATH
                    and path != CHECKSUM_FILE_PATH
                ):
                    print(
                        "Using legacy checksum file at "
                        f"{path} for this comparison."
                    )

                return value

        except FileNotFoundError:
            continue

        except OSError as exc:
            print(
                f"Unable to read checksum file {path}: {exc}"
            )
            return None

    return None


def save_checksum(checksum):
    """Atomically save the latest successfully uploaded record checksum."""
    checksum_path = os.path.abspath(
        os.path.expanduser(CHECKSUM_FILE_PATH)
    )

    os.makedirs(
        os.path.dirname(checksum_path),
        exist_ok=True,
    )

    tmp_file = checksum_path + ".tmp"

    with open(
        tmp_file,
        "w",
        encoding="utf-8",
    ) as checksum_file:
        checksum_file.write(checksum)

    os.chmod(tmp_file, 0o600)
    os.replace(tmp_file, checksum_path)


# -----------------------------------------------------------------------------
# Record normalization / Garmin upload
# -----------------------------------------------------------------------------

def normalize_scale_record(record):
    """
    Normalize a Wyze ScaleRecord.

    Weight and timestamp are required.
    All body-composition values are optional.
    """
    weight_lb = optional_float(
        getattr(record, "weight", None)
    )

    measure_ts = optional_float(
        getattr(record, "measure_ts", None)
    )

    if weight_lb is None:
        raise ValueError(
            "Wyze scale record does not contain a valid weight."
        )

    if measure_ts is None:
        raise ValueError(
            "Wyze scale record does not contain a valid timestamp."
        )

    bmr = optional_float(
        getattr(record, "bmr", None)
    )

    return {
        "measure_ts": int(measure_ts),
        "weight_lb": weight_lb,
        "weight_kg": weight_lb * 0.45359237,

        "percent_fat": optional_float(
            getattr(record, "body_fat", None)
        ),

        "percent_hydration": optional_float(
            getattr(record, "body_water", None)
        ),

        "bone_mass": optional_float(
            getattr(record, "bone_mineral", None)
        ),

        "muscle_mass": optional_float(
            getattr(record, "muscle", None)
        ),

        "basal_met": bmr,

        "active_met": (
            int(bmr * 1.25)
            if bmr is not None
            else None
        ),

        # Do not manufacture a physique rating if Wyze
        # did not supply one.
        "physique_rating": optional_int(
            getattr(record, "body_type", None)
        ),

        "metabolic_age": optional_int(
            getattr(record, "metabolic_age", None)
        ),

        "visceral_fat_rating": optional_int(
            getattr(record, "body_vfr", None)
        ),

        "bmi": optional_float(
            getattr(record, "bmi", None)
        ),
    }


def upload_record_to_garmin(record, garmin):
    """
    Upload one Wyze record to Garmin.

    Partial body composition:
        Missing values are sent as None.

    Weight-only:
        Uses Garmin's weigh-in API rather than forcing a
        body-composition FIT record.
    """
    try:
        data = normalize_scale_record(record)

        measurement_utc = datetime.fromtimestamp(
            data["measure_ts"] / 1000,
            tz=timezone.utc,
        )

        measurement_local = measurement_utc.astimezone()

        composition_fields = (
            "percent_fat",
            "percent_hydration",
            "bone_mass",
            "muscle_mass",
            "basal_met",
            "physique_rating",
            "metabolic_age",
            "visceral_fat_rating",
            "bmi",
        )

        has_body_composition = any(
            data[field] is not None
            for field in composition_fields
        )

        if has_body_composition:
            missing_fields = [
                field
                for field in composition_fields
                if data[field] is None
            ]

            print(
                "Uploading body composition to Garmin: "
                f"{measurement_local.strftime('%Y-%m-%d %H:%M:%S %Z')} - "
                f"{data['weight_lb']:.1f} lb / "
                f"{data['weight_kg']:.2f} kg"
            )

            if missing_fields:
                print(
                    "Wyze did not provide: "
                    + ", ".join(missing_fields)
                    + ". Uploading the available values."
                )

            garmin.add_body_composition(
                timestamp=measurement_local.isoformat(),
                weight=data["weight_kg"],

                percent_fat=data["percent_fat"],
                percent_hydration=data["percent_hydration"],

                bone_mass=data["bone_mass"],
                muscle_mass=data["muscle_mass"],

                basal_met=data["basal_met"],
                active_met=data["active_met"],

                physique_rating=data["physique_rating"],
                metabolic_age=data["metabolic_age"],

                visceral_fat_rating=data[
                    "visceral_fat_rating"
                ],

                bmi=data["bmi"],
            )

            print(
                "Garmin body composition upload successful."
            )

        else:
            print(
                "Wyze measurement contains weight only. "
                "Uploading as a Garmin weigh-in: "
                f"{measurement_local.strftime('%Y-%m-%d %H:%M:%S %Z')} - "
                f"{data['weight_lb']:.1f} lb / "
                f"{data['weight_kg']:.2f} kg"
            )

            garmin.add_weigh_in_with_timestamps(
                weight=data["weight_kg"],
                unitKey="kg",

                dateTimestamp=measurement_local.strftime(
                    "%Y-%m-%dT%H:%M:%S"
                ),

                gmtTimestamp=measurement_utc.strftime(
                    "%Y-%m-%dT%H:%M:%S"
                ),
            )

            print(
                "Garmin weight-only upload successful."
            )

        return True

    except GarminConnectTooManyRequestsError:
        # Let the caller decide whether to abort a historical batch.
        raise

    except GarminConnectAuthenticationError as exc:
        print(
            f"Garmin authentication failed during upload: {exc}"
        )

    except GarminConnectConnectionError as exc:
        print(
            f"Garmin upload failed: {exc}"
        )

    except ValueError as exc:
        print(
            f"Invalid Wyze measurement: {exc}"
        )

    except Exception as exc:
        print(
            f"Unexpected Garmin upload error: {exc}"
        )

    return False


# -----------------------------------------------------------------------------
# Historical / time-window synchronization
# -----------------------------------------------------------------------------

def collect_timewindow_records(
    client,
    scale_devices,
    start_date,
    end_date,
):
    """
    Retrieve every Wyze scale record in the requested window.

    Wyze's current SDK passes end_time to the API but hard-codes
    start_time=0. The API may also return only a limited number
    of records.

    Walk backwards through history by progressively reducing
    end_time.
    """
    records_by_id = {}
    queried_models = set()

    # Safety guard against unexpected API behavior.
    max_pages = 10000

    for device in scale_devices:
        product = getattr(
            device,
            "product",
            None,
        )

        device_model = getattr(
            product,
            "model",
            None,
        )

        model_key = (
            device_model
            or "__default__"
        )

        # Scale history is user-oriented. Avoid asking for
        # the same model twice.
        if model_key in queried_models:
            continue

        queried_models.add(model_key)

        print(
            "Requesting Wyze historical records"
            + (
                f" for model {device_model}"
                if device_model
                else ""
            )
            + "..."
        )

        page = 0
        query_end = end_date
        previous_oldest_ms = None

        while (
            query_end >= start_date
            and page < max_pages
        ):
            page += 1

            try:
                kwargs = {
                    "start_time": start_date,
                    "end_time": query_end,
                }

                if device_model:
                    kwargs["device_model"] = device_model

                page_records = list(
                    client.scales.get_records(
                        **kwargs
                    )
                    or []
                )

            except Exception as exc:
                print(
                    f"Unable to retrieve Wyze history page {page}"
                    + (
                        f" for model {device_model}"
                        if device_model
                        else ""
                    )
                    + f": {exc}"
                )

                break

            if not page_records:
                print(
                    f"History page {page}: "
                    "Wyze returned 0 records. "
                    "No older measurements are available."
                )

                break

            valid_page_records = []

            for record in page_records:
                try:
                    measurement_time = record_datetime(
                        record
                    )

                except Exception as exc:
                    print(
                        "Skipping record with invalid timestamp: "
                        f"{exc}"
                    )
                    continue

                valid_page_records.append(
                    (
                        record,
                        measurement_time,
                    )
                )

                # Enforce the requested time window locally.
                if (
                    start_date
                    <= measurement_time
                    <= end_date
                ):
                    records_by_id[
                        record_identity(record)
                    ] = record

            if not valid_page_records:
                print(
                    f"History page {page}: "
                    "no records had usable timestamps. "
                    "Stopping history scan."
                )

                break

            oldest_record, oldest_time = min(
                valid_page_records,
                key=lambda item: float(
                    item[0].measure_ts
                ),
            )

            newest_record, newest_time = max(
                valid_page_records,
                key=lambda item: float(
                    item[0].measure_ts
                ),
            )

            oldest_ms = int(
                float(
                    oldest_record.measure_ts
                )
            )

            print(
                f"History page {page}: "
                f"Wyze returned {len(page_records)} record(s), "
                f"{oldest_time.strftime('%Y-%m-%d %H:%M:%S')} "
                "through "
                f"{newest_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            if oldest_time <= start_date:
                break

            # Protect against a server that ignores the
            # progressively earlier end_time.
            if (
                previous_oldest_ms is not None
                and oldest_ms >= previous_oldest_ms
            ):
                print(
                    "WARNING: Wyze did not return an older "
                    "measurement after moving end_time backwards. "
                    "Stopping to avoid an infinite loop."
                )

                break

            previous_oldest_ms = oldest_ms

            query_end = (
                oldest_time
                - timedelta(milliseconds=1)
            )

    return sorted(
        records_by_id.values(),
        key=lambda record: float(
            record.measure_ts
        ),
    )


def update_latest_checksum_if_uploaded(
    client,
    scale_devices,
    uploaded_ids,
):
    """
    If a backfill included the current latest reading,
    save its record checksum so the next scheduled run
    does not upload it again.
    """
    for device in scale_devices:
        try:
            scale = client.scales.info(
                device_mac=device.mac
            )

        except Exception as exc:
            print(
                "Unable to refresh latest scale record "
                f"for checksum: {exc}"
            )
            continue

        if (
            not scale
            or not scale.latest_records
        ):
            continue

        latest = scale.latest_records[0]

        if (
            record_identity(latest)
            not in uploaded_ids
        ):
            continue

        try:
            save_checksum(
                measurement_checksum(
                    latest
                )
            )

            print(
                "Updated cksum.txt because the time-window "
                "upload included the latest Wyze measurement."
            )

            return

        except Exception as exc:
            print(
                "Unable to update latest-reading checksum: "
                f"{exc}"
            )

            return


def sync_timewindow(
    client,
    scale_devices,
    start_date,
    end_date,
):
    """
    Upload every Wyze Scale reading in an inclusive
    time window to Garmin.
    """
    print()
    print("=" * 72)
    print(
        "Wyze -> Garmin historical synchronization"
    )
    print("=" * 72)

    print(
        f"Start: {start_date.isoformat()}"
    )

    print(
        f"End:   {end_date.isoformat()}"
    )

    print()

    if start_date > end_date:
        print(
            "ERROR: Start date must be before end date."
        )
        return False

    if not scale_devices:
        print(
            "No Wyze Scale devices found."
        )
        return False

    records = collect_timewindow_records(
        client,
        scale_devices,
        start_date,
        end_date,
    )

    print(
        f"Found {len(records)} measurement(s) "
        "in the requested time window."
    )

    if not records:
        return True

    print()

    print(
        "WARNING: time-window mode uploads every Wyze "
        "reading in the requested window. "
        "It does not check Garmin for existing "
        "historical duplicates."
    )

    print()

    # Authenticate once for the entire batch.
    garmin = login_to_garmin()

    if garmin is None:
        print(
            "Unable to authenticate with Garmin."
        )
        return False

    uploaded = 0
    failed = 0
    attempted = 0
    uploaded_ids = set()
    rate_limited = False

    for index, record in enumerate(
        records,
        start=1,
    ):
        attempted += 1

        try:
            measurement_time = record_datetime(
                record
            )

            weight = optional_float(
                getattr(
                    record,
                    "weight",
                    None,
                )
            )

            weight_text = (
                "unknown weight"
                if weight is None
                else f"{weight:.1f} lb"
            )

            print(
                f"[{index}/{len(records)}] "
                f"{measurement_time.strftime('%Y-%m-%d %H:%M:%S %Z')} "
                f"- {weight_text}"
            )

            success = upload_record_to_garmin(
                record,
                garmin,
            )

        except GarminConnectTooManyRequestsError as exc:
            print(
                "Garmin rate limit reached during "
                f"historical upload: {exc}"
            )

            print(
                "Stopping the batch to avoid further requests."
            )

            failed += 1
            rate_limited = True
            break

        except Exception as exc:
            print(
                "Unexpected error processing "
                f"historical record: {exc}"
            )

            success = False

        if success:
            uploaded += 1

            uploaded_ids.add(
                record_identity(
                    record
                )
            )

        else:
            failed += 1

        if (
            index < len(records)
            and BACKFILL_DELAY_SECONDS > 0
        ):
            time_module.sleep(
                BACKFILL_DELAY_SECONDS
            )

    not_attempted = (
        len(records)
        - attempted
    )

    if uploaded_ids:
        update_latest_checksum_if_uploaded(
            client,
            scale_devices,
            uploaded_ids,
        )

    print()
    print("=" * 72)

    print(
        "Historical synchronization complete"
    )

    print("=" * 72)

    print(
        f"Measurements found:     {len(records)}"
    )

    print(
        f"Successfully uploaded:  {uploaded}"
    )

    print(
        f"Failed:                 {failed}"
    )

    print(
        f"Not attempted:          {not_attempted}"
    )

    print("=" * 72)

    if rate_limited:
        return False

    return failed == 0


# -----------------------------------------------------------------------------
# Normal latest-reading synchronization
# -----------------------------------------------------------------------------

def sync_latest(
    client,
    devices,
):
    scale_found = False
    garmin = None

    for device in devices:
        if device.type != "WyzeScale":
            continue

        scale_found = True

        try:
            scale = client.scales.info(
                device_mac=device.mac
            )

        except Exception as exc:
            print(
                f"Unable to retrieve scale {device.mac}: {exc}"
            )
            continue

        if (
            not scale
            or not scale.latest_records
        ):
            print(
                f"Scale {device.mac} has no measurements available."
            )
            continue

        record = scale.latest_records[0]

        print(
            f"Scale found with MAC {device.mac}. "
            "Latest record is:"
        )

        print(
            scale.latest_records
        )

        current_checksum = measurement_checksum(
            record
        )

        previous_checksum = load_previous_checksum()

        if previous_checksum == current_checksum:
            print(
                "No new measurement"
            )
            continue

        if previous_checksum:
            print(
                "New measurement detected. "
                "Uploading to Garmin..."
            )

        else:
            print(
                "No checksum detected. "
                "Uploading measurement and creating checksum..."
            )

        if garmin is None:
            garmin = login_to_garmin()

            if garmin is None:
                print(
                    "Unable to authenticate with Garmin."
                )
                continue

        try:
            success = upload_record_to_garmin(
                record,
                garmin,
            )

        except GarminConnectTooManyRequestsError as exc:
            print(
                "Garmin rate limit reached during upload: "
                f"{exc}"
            )
            return

        if success:
            # Only advance the checksum after Garmin
            # accepted the measurement.
            save_checksum(
                current_checksum
            )

            print(
                "Measurement synchronized successfully."
            )

        else:
            print(
                "Measurement upload failed. "
                "Checksum was not updated, so the next "
                "scheduled run will retry it."
            )

    if not scale_found:
        print(
            "No Wyze Scale device found on this account."
        )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    args = parse_arguments()
    os.chdir(WORK_DIR)

    client, tokens = login_to_wyze()

    if client is None:
        print(
            "Unable to establish Wyze session."
        )
        return 1

    client, tokens, devices = get_wyze_devices(
        client,
        tokens,
    )

    if (
        client is None
        or devices is None
    ):
        return 1

    scale_devices = [
        device
        for device in devices
        if device.type == "WyzeScale"
    ]

    if args.timewindow:
        try:
            start_date = parse_date_value(
                args.timewindow[0],
                is_end=False,
            )

            end_date = parse_date_value(
                args.timewindow[1],
                is_end=True,
            )

        except ValueError as exc:
            print(
                f"ERROR: {exc}"
            )
            return 2

        success = sync_timewindow(
            client,
            scale_devices,
            start_date,
            end_date,
        )

        return (
            0
            if success
            else 1
        )

    sync_latest(
        client,
        devices,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
