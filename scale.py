#!/usr/local/bin/python3

import argparse
import hashlib
import json
import math
import os
import sys
import time as time_module
from datetime import datetime, time as datetime_time, timezone
from getpass import getpass
from pathlib import Path

from requests.exceptions import HTTPError, RequestException

from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError

from fit import FitEncoder_Weight

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
# compatibility with existing docker-compose files.
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
FIT_FILE_PATH = os.path.join(WORK_DIR, "wyze_scale.fit")
CHECKSUM_FILE_PATH = os.path.join(WORK_DIR, "cksum.txt")


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
    # local timezone, including the correct DST offset for that date.
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()

    return parsed


# -----------------------------------------------------------------------------
# Wyze authentication
# -----------------------------------------------------------------------------

def save_wyze_tokens(tokens):
    """Save Wyze authentication information to persistent storage."""
    os.makedirs(os.path.dirname(WYZE_TOKEN_FILE), exist_ok=True)

    tmp_file = WYZE_TOKEN_FILE + ".tmp"

    with open(tmp_file, "w") as token_file:
        json.dump(tokens, token_file)

    os.chmod(tmp_file, 0o600)
    os.replace(tmp_file, WYZE_TOKEN_FILE)


def load_wyze_tokens():
    """Load cached Wyze authentication information."""
    try:
        with open(WYZE_TOKEN_FILE, "r") as token_file:
            tokens = json.load(token_file)

        if not tokens.get("access_token"):
            return None

        return tokens

    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def login_to_wyze():
    """
    Reuse cached Wyze tokens whenever possible.

    Username/password authentication is only performed when no cached token
    exists.
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
    print("Performing initial Wyze authentication...")

    try:
        client = Client()

        response = client.login(
            email=WYZE_EMAIL,
            password=WYZE_PASSWORD,
            key_id=WYZE_KEY_ID,
            api_key=WYZE_API_KEY,
        )

        tokens = {
            "access_token": response["access_token"],
            "refresh_token": response["refresh_token"],
            "user_id": response["user_id"],
        }

        save_wyze_tokens(tokens)

        print("Wyze authentication successful.")
        print("Wyze authentication tokens saved.")

        return client, tokens

    except HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None

        if status == 429:
            print(
                "Wyze authentication rate limited (HTTP 429). "
                "Stopping this run without retrying."
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


def refresh_wyze_token(client, tokens):
    """Refresh the Wyze access token without username/password login."""
    if not tokens:
        print("No cached Wyze token information available.")
        return False

    if not tokens.get("refresh_token"):
        print("No Wyze refresh token available.")
        return False

    try:
        print("Refreshing Wyze authentication token...")
        response = client.refresh_token()

        refreshed = response["data"]

        tokens["access_token"] = refreshed["access_token"]
        tokens["refresh_token"] = refreshed["refresh_token"]

        save_wyze_tokens(tokens)

        print("Wyze authentication token refreshed.")
        return True

    except Exception as exc:
        print(f"Unable to refresh Wyze authentication token: {exc}")
        return False


def get_wyze_devices(client, tokens):
    """Get the Wyze device list, refreshing the access token once if needed."""
    try:
        return client.devices_list()

    except Exception as exc:
        print(f"Cached Wyze token failed: {exc}")

    if not refresh_wyze_token(client, tokens):
        print(
            "Wyze session could not be refreshed. "
            "Stopping this run to avoid repeated login attempts."
        )
        return None

    try:
        return client.devices_list()

    except Exception as exc:
        print(f"Wyze API still unavailable after token refresh: {exc}")
        return None


# -----------------------------------------------------------------------------
# Garmin authentication
# -----------------------------------------------------------------------------

def login_to_garmin():
    """
    Garmin authentication flow:

    1. Use garmin_tokens.json if it exists.
    2. If the token is unavailable/invalid and this is an interactive terminal,
       perform credential login and prompt for MFA if required.
    3. In a non-interactive cron run, never wait for MFA or continuously retry
       username/password authentication.
    """
    Path(GARMIN_TOKEN_DIR).mkdir(parents=True, exist_ok=True)
    token_file = Path(GARMIN_TOKEN_DIR) / "garmin_tokens.json"

    if token_file.is_file():
        print("Garmin token found. Trying cached authentication...")

        try:
            garmin = Garmin()
            garmin.login(GARMIN_TOKEN_DIR)

            print("Using cached Garmin authentication token.")
            return garmin

        except GarminConnectTooManyRequestsError as exc:
            print(f"Garmin rate limit while using cached token: {exc}")
            return None

        except (GarminConnectAuthenticationError, GarminConnectConnectionError) as exc:
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

        # These two strategies were observed returning 429 in this deployment.
        # Skip them and use Garmin's widget/portal strategies for initial auth.
        garmin.client.skip_strategies.update({
            "mobile+cffi",
            "mobile+requests",
        })

        print("Authenticating with Garmin Connect...")
        garmin.login(GARMIN_TOKEN_DIR)

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
# Record helpers / Garmin upload
# -----------------------------------------------------------------------------

def record_datetime(record):
    """Convert a Wyze millisecond epoch timestamp to local timezone."""
    return datetime.fromtimestamp(
        float(record.measure_ts) / 1000,
        tz=timezone.utc,
    ).astimezone()


def record_identity(record):
    """Build a stable-enough key for deduplicating records returned by Wyze."""
    data_id = getattr(record, "data_id", None)

    if data_id is not None:
        return ("data_id", str(data_id))

    weight = getattr(record, "weight", None)
    weight_key = None if weight is None else round(float(weight), 4)

    return (
        "measurement",
        int(float(record.measure_ts)),
        weight_key,
    )


def upload_record_to_garmin(record, garmin):
    """Upload one Wyze Scale record to Garmin Connect."""
    try:
        measurement_time = record_datetime(record)
        timestamp = measurement_time.isoformat()

        # Wyze reports weight in pounds. Garmin's body composition FIT expects kg.
        weight_kg = float(record.weight) * 0.45359237

        active_met = None
        if record.bmr is not None:
            active_met = int(float(record.bmr) * 1.25)

        print(
            f"Uploading body composition to Garmin: "
            f"{measurement_time.strftime('%Y-%m-%d %H:%M:%S %Z')} - "
            f"{float(record.weight):.1f} lb / {weight_kg:.2f} kg"
        )

        garmin.add_body_composition(
            timestamp=timestamp,
            weight=weight_kg,
            percent_fat=(
                float(record.body_fat)
                if record.body_fat is not None
                else None
            ),
            percent_hydration=(
                float(record.body_water)
                if record.body_water is not None
                else None
            ),
            bone_mass=(
                float(record.bone_mineral)
                if record.bone_mineral is not None
                else None
            ),
            muscle_mass=(
                float(record.muscle)
                if record.muscle is not None
                else None
            ),
            basal_met=(
                float(record.bmr)
                if record.bmr is not None
                else None
            ),
            active_met=active_met,
            physique_rating=float(record.body_type or 5),
            metabolic_age=(
                float(record.metabolic_age)
                if record.metabolic_age is not None
                else None
            ),
            visceral_fat_rating=(
                float(record.body_vfr)
                if record.body_vfr is not None
                else None
            ),
            bmi=(
                float(record.bmi)
                if record.bmi is not None
                else None
            ),
        )

        print("Garmin body composition upload successful.")
        return True

    except GarminConnectTooManyRequestsError:
        # Let the caller decide whether to abort a historical batch.
        raise

    except GarminConnectAuthenticationError as exc:
        print(f"Garmin authentication failed during upload: {exc}")

    except GarminConnectConnectionError as exc:
        print(f"Garmin upload failed: {exc}")

    except Exception as exc:
        print(f"Unexpected Garmin upload error: {exc}")

    return False


def upload_to_garmin(scale):
    """Upload the latest record from a Wyze Scale object."""
    if not scale.latest_records:
        print("No Wyze scale records available to upload.")
        return False

    garmin = login_to_garmin()

    if garmin is None:
        return False

    try:
        return upload_record_to_garmin(scale.latest_records[0], garmin)

    except GarminConnectTooManyRequestsError as exc:
        print(f"Garmin rate limit reached during upload: {exc}")
        return False


# -----------------------------------------------------------------------------
# Existing FIT/checksum handling for normal latest-reading mode
# -----------------------------------------------------------------------------

def generate_fit_file(scale):
    fit = FitEncoder_Weight()
    timestamp = math.trunc(scale.latest_records[0].measure_ts / 1000)
    weight_in_kg = scale.latest_records[0].weight * 0.45359237

    # Keep the existing FIT payload unchanged so existing cksum.txt files remain
    # compatible and upgrading does not force an unnecessary duplicate upload.
    data_keys = {
        "percent_fat": scale.latest_records[0].body_fat,
        "percent_hydration": scale.latest_records[0].body_water,
        "visceral_fat_mass": scale.latest_records[0].body_fat,
        "bone_mass": scale.latest_records[0].bone_mineral,
        "muscle_mass": scale.latest_records[0].muscle,
        "basal_met": scale.latest_records[0].bmr,
        "physique_rating": scale.latest_records[0].body_type or 5,
        "active_met": scale.latest_records[0].bmr,
        "metabolic_age": scale.latest_records[0].metabolic_age,
        "visceral_fat_rating": scale.latest_records[0].body_vfr,
        "bmi": scale.latest_records[0].bmi,
    }

    data = {}
    for key, value in data_keys.items():
        data[key] = float(value) if value is not None else None

    if data.get("basal_met") is None:
        data["active_met"] = None
    else:
        data["active_met"] = int(float(scale.latest_records[0].bmr) * 1.25)

    fit.write_file_info(time_created=timestamp)
    fit.write_file_creator()
    fit.write_device_info(timestamp=timestamp)
    fit.write_weight_scale(
        timestamp=timestamp,
        weight=weight_in_kg,
        percent_fat=data.get("percent_fat"),
        percent_hydration=data.get("percent_hydration"),
        visceral_fat_mass=data.get("visceral_fat_mass"),
        bone_mass=data.get("bone_mass"),
        muscle_mass=data.get("muscle_mass"),
        basal_met=data.get("basal_met"),
        physique_rating=data.get("physique_rating"),
        active_met=data.get("active_met"),
        metabolic_age=data.get("metabolic_age"),
        visceral_fat_rating=data.get("visceral_fat_rating"),
        bmi=data.get("bmi"),
    )
    fit.finish()

    with open(FIT_FILE_PATH, "wb") as fitfile:
        fitfile.write(fit.getvalue())


def fit_checksum():
    with open(FIT_FILE_PATH, "rb") as fitfile:
        return hashlib.md5(fitfile.read()).hexdigest()


def save_checksum(checksum):
    with open(CHECKSUM_FILE_PATH, "w") as checksum_file:
        checksum_file.write(checksum)


# -----------------------------------------------------------------------------
# Historical / time-window synchronization
# -----------------------------------------------------------------------------

def collect_timewindow_records(client, scale_devices, start_date, end_date):
    """
    Retrieve Wyze scale records for the requested window.

    The current Wyze SDK sends start_time=0 internally, so this function always
    applies its own local timestamp filter before returning records.
    """
    records_by_id = {}
    queried_models = set()

    for device in scale_devices:
        product = getattr(device, "product", None)
        device_model = getattr(product, "model", None)
        model_key = device_model or "__default__"

        # Scale history is user-oriented. Avoid querying the same model multiple
        # times when more than one scale device of that model is present.
        if model_key in queried_models:
            continue
        queried_models.add(model_key)

        try:
            print(
                "Requesting Wyze historical records"
                + (f" for model {device_model}" if device_model else "")
                + "..."
            )

            if device_model:
                records = client.scales.get_records(
                    device_model=device_model,
                    start_time=start_date,
                    end_time=end_date,
                )
            else:
                records = client.scales.get_records(
                    start_time=start_date,
                    end_time=end_date,
                )

        except Exception as exc:
            print(
                "Unable to retrieve historical records"
                + (f" for model {device_model}" if device_model else "")
                + f": {exc}"
            )
            continue

        for record in records:
            try:
                measurement_time = record_datetime(record)
            except Exception as exc:
                print(f"Skipping record with invalid timestamp: {exc}")
                continue

            # Explicit filtering is intentional because the Wyze SDK currently
            # ignores start_time in its lower-level scale-service request.
            if start_date <= measurement_time <= end_date:
                records_by_id[record_identity(record)] = record

    return sorted(
        records_by_id.values(),
        key=lambda record: float(record.measure_ts),
    )


def update_latest_checksum_if_uploaded(client, scale_devices, uploaded_ids):
    """
    If a historical backfill included the current latest reading, update the
    normal-mode checksum so the next cron execution does not upload it again.
    """
    for device in scale_devices:
        try:
            scale = client.scales.info(device_mac=device.mac)
        except Exception as exc:
            print(f"Unable to refresh latest scale record for checksum: {exc}")
            continue

        if not scale or not scale.latest_records:
            continue

        latest = scale.latest_records[0]

        if record_identity(latest) not in uploaded_ids:
            continue

        try:
            generate_fit_file(scale)
            checksum = fit_checksum()
            save_checksum(checksum)
            print(
                "Updated cksum.txt because the time-window upload included "
                "the latest Wyze measurement."
            )
            return
        except Exception as exc:
            print(f"Unable to update latest-reading checksum: {exc}")
            return


def sync_timewindow(client, scale_devices, start_date, end_date):
    """Upload every Wyze Scale reading in an inclusive time window to Garmin."""
    print()
    print("=" * 72)
    print("Wyze -> Garmin historical synchronization")
    print("=" * 72)
    print(f"Start: {start_date.isoformat()}")
    print(f"End:   {end_date.isoformat()}")
    print()

    if start_date > end_date:
        print("ERROR: Start date must be before end date.")
        return False

    if not scale_devices:
        print("No Wyze Scale devices found.")
        return False

    records = collect_timewindow_records(
        client,
        scale_devices,
        start_date,
        end_date,
    )

    print(f"Found {len(records)} measurement(s) in the requested time window.")

    if not records:
        return True

    print()
    print(
        "WARNING: time-window mode uploads every Wyze reading in the requested "
        "window. It does not check Garmin for existing historical duplicates."
    )
    print()

    # Authenticate once for the entire batch.
    garmin = login_to_garmin()

    if garmin is None:
        print("Unable to authenticate with Garmin.")
        return False

    uploaded = 0
    failed = 0
    attempted = 0
    uploaded_ids = set()
    rate_limited = False

    for index, record in enumerate(records, start=1):
        attempted += 1
        measurement_time = record_datetime(record)

        print(
            f"[{index}/{len(records)}] "
            f"{measurement_time.strftime('%Y-%m-%d %H:%M:%S %Z')} - "
            f"{float(record.weight):.1f} lb"
        )

        try:
            success = upload_record_to_garmin(record, garmin)

        except GarminConnectTooManyRequestsError as exc:
            print(f"Garmin rate limit reached during historical upload: {exc}")
            print("Stopping the batch to avoid further requests.")
            failed += 1
            rate_limited = True
            break

        if success:
            uploaded += 1
            uploaded_ids.add(record_identity(record))
        else:
            failed += 1

        if index < len(records) and BACKFILL_DELAY_SECONDS > 0:
            time_module.sleep(BACKFILL_DELAY_SECONDS)

    not_attempted = len(records) - attempted

    if uploaded_ids:
        update_latest_checksum_if_uploaded(
            client,
            scale_devices,
            uploaded_ids,
        )

    print()
    print("=" * 72)
    print("Historical synchronization complete")
    print("=" * 72)
    print(f"Measurements found:     {len(records)}")
    print(f"Successfully uploaded:  {uploaded}")
    print(f"Failed:                 {failed}")
    print(f"Not attempted:          {not_attempted}")
    print("=" * 72)

    if rate_limited:
        return False

    return failed == 0


# -----------------------------------------------------------------------------
# Normal latest-reading synchronization
# -----------------------------------------------------------------------------

def sync_latest(client, devices):
    scale_found = False

    for device in devices:
        if device.type != "WyzeScale":
            continue

        scale_found = True

        try:
            scale = client.scales.info(device_mac=device.mac)
        except Exception as exc:
            print(f"Unable to retrieve scale {device.mac}: {exc}")
            continue

        if not scale or not scale.latest_records:
            print(f"Scale {device.mac} has no measurements available.")
            continue

        print(f"Scale found with MAC {device.mac}. Latest record is:")
        print(scale.latest_records)
        print(f"Body Type: {scale.latest_records[0].body_type or 5}")

        print("Generating fit data...")
        generate_fit_file(scale)
        print("Fit data generated...")

        checksum = fit_checksum()

        checksum_exists = os.path.exists(CHECKSUM_FILE_PATH)

        if checksum_exists:
            with open(CHECKSUM_FILE_PATH, "r") as checksum_file:
                stored_checksum = checksum_file.read().strip()

            if checksum == stored_checksum:
                print("No new measurement")
                continue

            print("New measurement detected. Uploading to Garmin...")

        else:
            print("No checksum detected. Uploading measurement and creating checksum...")

        if upload_to_garmin(scale):
            print("Measurement uploaded successfully.")
            save_checksum(checksum)

            if not checksum_exists:
                print("cksum.txt created.")
        else:
            print("Measurement upload failed.")

    if not scale_found:
        print("No Wyze Scale device found on this account.")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    args = parse_arguments()
    os.chdir(WORK_DIR)

    client, tokens = login_to_wyze()

    if client is None:
        print("Unable to establish Wyze session.")
        return 1

    devices = get_wyze_devices(client, tokens)

    if devices is None:
        return 1

    scale_devices = [device for device in devices if device.type == "WyzeScale"]

    if args.timewindow:
        try:
            start_date = parse_date_value(args.timewindow[0], is_end=False)
            end_date = parse_date_value(args.timewindow[1], is_end=True)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 2

        success = sync_timewindow(
            client,
            scale_devices,
            start_date,
            end_date,
        )
        return 0 if success else 1

    sync_latest(client, devices)
    return 0


if __name__ == "__main__":
    sys.exit(main())
