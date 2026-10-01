#!/usr/local/bin/python3
import math
import os
import json
import hashlib

from requests.exceptions import HTTPError, RequestException

from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError

from fit import FitEncoder_Weight

import garth
from getpass import getpass

WYZE_EMAIL = os.environ.get('WYZE_EMAIL')
WYZE_PASSWORD = os.environ.get('WYZE_PASSWORD')
WYZE_KEY_ID = os.environ.get('WYZE_KEY_ID')
WYZE_API_KEY = os.environ.get('WYZE_API_KEY')
GARMIN_USERNAME = os.environ.get('Garmin_username')
GARMIN_PASSWORD = os.environ.get('Garmin_password')
WYZE_TOKEN_FILE = os.environ.get('token')

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

def upload_to_garmin(file_path):
    try:
        garth.resume('/wyze_garmin_sync/tokens')
        garth.client.username
    except:
        try:
            garth.login(GARMIN_USERNAME, GARMIN_PASSWORD)
            garth.save('/wyze_garmin_sync/tokens')
        except:
            email = input("Enter Garmin email address: ")
            password = getpass("Enter Garmin password: ")
            try:
                garth.login(email, password)
                garth.save('/wyze_garmin_sync/tokens')
            except Exception as exc:
                print(repr(exc))
                exit()

    try:
        with open(file_path, "rb") as f:
            garth.client.upload(f)
        return True
    except Exception as e:
        print(f"Garmin upload error: {e}")
        return False

def generate_fit_file(scale):
    fit = FitEncoder_Weight()
    timestamp = math.trunc(scale.latest_records[0].measure_ts / 1000)
    weight_in_kg = scale.latest_records[0].weight * 0.45359237

    data_keys = {
        'percent_fat': scale.latest_records[0].body_fat,
        'percent_hydration': scale.latest_records[0].body_water,
        'visceral_fat_mass': scale.latest_records[0].body_vfr,
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
                        if upload_to_garmin(fitfile_path):
                            print("File uploaded successfully.")
                            # Update cksum.txt with the new checksum
                            with open(cksum_file_path, "w") as cksum_file:
                                cksum_file.write(cksum)
                        else:
                            print("File upload failed.")
                else:
                    print("No chksum detected. Uploading fit file and creating chksum...")
                    # Upload the fit file to Garmin
                    if upload_to_garmin(fitfile_path):
                        print("File uploaded successfully.")
                        # Create cksum.txt and write the checksum
                        with open(cksum_file_path, "w") as cksum_file:
                            cksum_file.write(cksum)
                        print("cksum.txt created.")
                    else:
                        print("File upload failed.")

if __name__ == "__main__":
    main()

