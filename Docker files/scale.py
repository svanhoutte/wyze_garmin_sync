#!/usr/local/bin/python3
import math
import os
import json
import hashlib

from requests.exceptions import HTTPError, RequestException

from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError

from fit import FitEncoder_Weight

from datetime import datetime, timezone

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

import sys

from getpass import getpass
from pathlib import Path

WYZE_EMAIL = os.environ.get('WYZE_EMAIL')
WYZE_PASSWORD = os.environ.get('WYZE_PASSWORD')
WYZE_KEY_ID = os.environ.get('WYZE_KEY_ID')
WYZE_API_KEY = os.environ.get('WYZE_API_KEY')
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
WYZE_TOKEN_FILE = (
    os.environ.get("token")
    or "/wyze_garmin_sync/tokens/wyze_tokens.json"
)

def save_wyze_tokens(tokens):
    """
    Save Wyze authentication information in the persistent tokens volume.
    """
    os.makedirs(os.path.dirname(WYZE_TOKEN_FILE), exist_ok=True)

    tmp_file = WYZE_TOKEN_FILE + ".tmp"

    with open(tmp_file, "w") as f:
        json.dump(tokens, f)

    os.chmod(tmp_file, 0o600)
    os.replace(tmp_file, WYZE_TOKEN_FILE)


def load_wyze_tokens():
    """
    Load cached Wyze authentication information.
    """
    try:
        with open(WYZE_TOKEN_FILE, "r") as f:
            tokens = json.load(f)

        if not tokens.get("access_token"):
            return None

        return tokens

    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def login_to_wyze():
    """
    Use cached Wyze tokens whenever possible.

    Username/password authentication is only performed when there
    is no cached token.
    """

    tokens = load_wyze_tokens()

    if tokens:
        print("Using cached Wyze authentication token.")

        client = Client(
            token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token")
        )

        # Required by the Wyze Scale API.
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
            api_key=WYZE_API_KEY
        )

        tokens = {
            "access_token": response["access_token"],
            "refresh_token": response["refresh_token"],
            "user_id": response["user_id"]
        }

        save_wyze_tokens(tokens)

        print("Wyze authentication successful.")
        print("Wyze authentication tokens saved.")

        return client, tokens

    except HTTPError as e:
        status = (
            e.response.status_code
            if e.response is not None
            else None
        )

        if status == 429:
            print(
                "Wyze authentication rate limited (HTTP 429). "
                "Stopping this run without retrying."
            )
        else:
            print(f"Wyze HTTP authentication error: {e}")

    except WyzeApiError as e:
        print(f"Wyze API authentication error: {e}")

    except RequestException as e:
        print(f"Wyze network error: {e}")

    except Exception as e:
        print(f"Unexpected Wyze authentication error: {e}")

    return None, None


def refresh_wyze_token(client, tokens):
    """
    Refresh the Wyze access token using the refresh token.

    This does NOT perform another username/password login.
    """

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

    except Exception as e:
        print(f"Unable to refresh Wyze authentication token: {e}")
        return False

def login_to_garmin():
    """
    Garmin authentication flow:

    1. Try existing garmin_tokens.json.
    2. If valid, use it without credentials/MFA.
    3. If tokens are missing/invalid:
       - Interactive terminal -> login with credentials + MFA and save tokens.
       - Non-interactive/cron -> do NOT attempt credential login.
    """

    Path(GARMIN_TOKEN_DIR).mkdir(
        parents=True,
        exist_ok=True
    )

    token_file = os.path.join(
        GARMIN_TOKEN_DIR,
        "garmin_tokens.json"
    )

    #
    # STEP 1 - Try existing token first
    #
    if os.path.isfile(token_file):

        print("Garmin token found. Trying cached authentication...")

        try:
            garmin = Garmin()

            garmin.login(GARMIN_TOKEN_DIR)

            print("Using cached Garmin authentication token.")

            return garmin

        except GarminConnectTooManyRequestsError as e:
            print(
                f"Garmin rate limit while using cached token: {e}"
            )

            # Don't fall back to username/password because of a 429.
            return None

        except (
            GarminConnectAuthenticationError,
            GarminConnectConnectionError
        ) as e:

            print(
                f"Cached Garmin authentication failed: {e}"
            )

            print(
                "Stored Garmin token may be invalid or expired."
            )

            # Continue below only if interactive.

        except Exception as e:
            print(
                f"Unexpected error loading Garmin token: {e}"
            )

            return None

    else:
        print(
            f"No Garmin token found at {token_file}"
        )

    #
    # STEP 2 - Determine whether interactive authentication
    # is possible.
    #
    if not sys.stdin.isatty():

        print(
            "Garmin authentication requires an interactive login."
        )

        print(
            "Run:"
        )

        print(
            "  docker compose run --rm wyzegarminconnect"
        )

        print(
            "to authenticate and create garmin_tokens.json."
        )

        return None

    #
    # STEP 3 - Interactive credential login
    #
    print()
    print("Starting interactive Garmin authentication.")
    print()

    email = GARMIN_USERNAME

    if not email:
        email = input(
            "Garmin email: "
        ).strip()

    password = GARMIN_PASSWORD

    if not password:
        password = getpass(
            "Garmin password: "
        )

    if not email or not password:
        print(
            "Garmin username/password were not supplied."
        )

        return None

    try:

        garmin = Garmin(
            email=email,
            password=password,
            prompt_mfa=lambda: input(
                "Enter Garmin MFA code: "
            ).strip(),
        )

        #
        # Your environment is already getting HTTP 429 from
        # both mobile login strategies.
        #
        # Skip those and go directly to Garmin's web/widget
        # authentication strategies.
        #
        garmin.client.skip_strategies.update({
            "mobile+cffi",
            "mobile+requests",
        })

        print(
            "Authenticating with Garmin Connect..."
        )

        garmin.login(
            GARMIN_TOKEN_DIR
        )

        print()
        print(
            "Garmin authentication successful."
        )

        print(
            f"Garmin token saved to {token_file}"
        )

        return garmin

    except GarminConnectTooManyRequestsError as e:

        print(
            f"Garmin authentication rate limited: {e}"
        )

    except GarminConnectAuthenticationError as e:

        print(
            f"Garmin authentication failed: {e}"
        )

    except GarminConnectConnectionError as e:

        print(
            f"Garmin connection error: {e}"
        )

    except KeyboardInterrupt:

        print()
        print(
            "Garmin authentication cancelled."
        )

    except Exception as e:

        print(
            f"Unexpected Garmin authentication error: {e}"
        )

    return None


def upload_to_garmin(scale):
    """
    Upload the latest Wyze scale measurement to Garmin Connect.
    """

    garmin = login_to_garmin()

    if garmin is None:
        return False

    try:
        record = scale.latest_records[0]

        #
        # Wyze timestamp is milliseconds since Unix epoch.
        # Convert to a timezone-aware ISO timestamp.
        #
        measurement_time = datetime.fromtimestamp(
            record.measure_ts / 1000,
            tz=timezone.utc
        ).astimezone()

        timestamp = measurement_time.isoformat()

        #
        # Wyze reports weight in pounds.
        # Garmin expects kilograms.
        #
        weight_kg = record.weight * 0.45359237

        #
        # Calculate active metabolism the same way as your
        # existing FIT generation.
        #
        active_met = None

        if record.bmr is not None:
            active_met = int(float(record.bmr) * 1.25)

        print(
            f"Uploading body composition to Garmin: "
            f"{weight_kg:.2f} kg at {timestamp}"
        )

        response = garmin.add_body_composition(
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

            physique_rating=(
                float(record.body_type or 5)
            ),

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

    except GarminConnectTooManyRequestsError as e:
        print(f"Garmin rate limit reached during upload: {e}")

    except GarminConnectAuthenticationError as e:
        print(f"Garmin authentication failed during upload: {e}")

    except GarminConnectConnectionError as e:
        print(f"Garmin upload failed: {e}")

    except Exception as e:
        print(f"Unexpected Garmin upload error: {e}")

    return False
    
def generate_fit_file(scale):
    fit = FitEncoder_Weight()
    timestamp = math.trunc(scale.latest_records[0].measure_ts / 1000)
    weight_in_kg = scale.latest_records[0].weight * 0.45359237

    data_keys = {
        'percent_fat': scale.latest_records[0].body_fat,
        'percent_hydration': scale.latest_records[0].body_water,
        'visceral_fat_mass': scale.latest_records[0].body_fat,
        'bone_mass': scale.latest_records[0].bone_mineral,
        'muscle_mass': scale.latest_records[0].muscle,
        'basal_met': scale.latest_records[0].bmr,
        'physique_rating': scale.latest_records[0].body_type or 5,
        'active_met': scale.latest_records[0].bmr,
        'metabolic_age': scale.latest_records[0].metabolic_age,
        'visceral_fat_rating': scale.latest_records[0].body_vfr,
        'bmi': scale.latest_records[0].bmi
    }
    data = {}
    for key, value in data_keys.items():
        if value is not None:
            data[key] = float(value)
        else:
            data[key] = None
    if data.get('basal_met') is None:
        data['active_met'] = None
    else:
        data['active_met'] = int(float(scale.latest_records[0].bmr) * 1.25)
    fit.write_file_info(time_created=timestamp)
    fit.write_file_creator()
    fit.write_device_info(timestamp=timestamp)
    fit.write_weight_scale(
        timestamp=timestamp,
        weight=weight_in_kg,
        percent_fat = data.get('percent_fat'),
        percent_hydration = data.get('percent_hydration'),
        visceral_fat_mass = data.get('visceral_fat_mass'),
        bone_mass = data.get('bone_mass'),
        muscle_mass = data.get('muscle_mass'),
        basal_met = data.get('basal_met'),
        physique_rating = data.get('physique_rating'),
        active_met = data.get('active_met'),
        metabolic_age = data.get('metabolic_age'),
        visceral_fat_rating = data.get('visceral_fat_rating'),
        bmi = data.get('bmi'),
    )
    fit.finish()
    with open("wyze_scale.fit", "wb") as fitfile:
        fitfile.write(fit.getvalue())

def main():
    os.chdir("/wyze_garmin_sync")

    client, tokens = login_to_wyze()

    if client is None:
        print("Unable to establish Wyze session.")
        return

    #
    # First try using the cached access token.
    #
    try:
        devices = client.devices_list()

    except Exception as e:
        print(f"Cached Wyze token failed: {e}")

        #
        # Do NOT perform another username/password login.
        # Try the refresh token instead.
        #
        if not refresh_wyze_token(client, tokens):
            print(
                "Wyze session could not be refreshed. "
                "Stopping this run to avoid repeated login attempts."
            )
            return

        #
        # Retry once with refreshed token.
        #
        try:
            devices = client.devices_list()

        except Exception as e:
            print(f"Wyze API still unavailable after token refresh: {e}")
            return

    for device in devices:
        if device.type == "WyzeScale":
                scale = client.scales.info(device_mac=device.mac)
                print(f"Scale found with MAC {device.mac}. Latest record is:")
                print(scale.latest_records)
                print(f"Body Type: {scale.latest_records[0].body_type or 5}")
                print("Generating fit data...")
                generate_fit_file(scale)
                print("Fit data generated...")
          
                fitfile_path = "/wyze_garmin_sync/wyze_scale.fit"
                cksum_file_path = "/wyze_garmin_sync/cksum.txt"

                # Calculate checksum of the fit file
                with open(fitfile_path, "rb") as fitfile:
                    cksum = hashlib.md5(fitfile.read()).hexdigest()

                # Check if cksum.txt exists and read stored checksum
                if os.path.exists(cksum_file_path):
                    with open(cksum_file_path, "r") as cksum_file:
                        stored_cksum = cksum_file.read().strip()

                    # Compare calculated checksum with stored checksum
                    if cksum == stored_cksum:
                        print("No new measurement")
                    else:
                        print("New measurement detected. Uploading file...")
                        # Upload the fit file to Garmin
                        if upload_to_garmin(scale):
                            print("File uploaded successfully.")
                            # Update cksum.txt with the new checksum
                            with open(cksum_file_path, "w") as cksum_file:
                                cksum_file.write(cksum)
                        else:
                            print("File upload failed.")
                else:
                    print("No chksum detected. Uploading fit file and creating chksum...")
                    # Upload the fit file to Garmin
                    if upload_to_garmin(scale):
                        print("File uploaded successfully.")
                        # Create cksum.txt and write the checksum
                        with open(cksum_file_path, "w") as cksum_file:
                            cksum_file.write(cksum)
                        print("cksum.txt created.")
                    else:
                        print("File upload failed.")

if __name__ == "__main__":
    main()

