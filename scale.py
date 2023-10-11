#!/usr/local/bin/python3
import math
import os
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError
from fit import FitEncoder_Weight
import hashlib
import garth
from getpass import getpass

WYZE_EMAIL = os.environ.get('WYZE_EMAIL')
WYZE_PASSWORD = os.environ.get('WYZE_PASSWORD')
WYZE_KEY_ID = os.environ.get('WYZE_KEY_ID')
WYZE_API_KEY = os.environ.get('WYZE_API_KEY')
GARMIN_USERNAME = os.environ.get('Garmin_username')
GARMIN_PASSWORD = os.environ.get('Garmin_password')

def login_to_wyze():
    try:
        response = Client().login(email=WYZE_EMAIL, password=WYZE_PASSWORD, key_id=WYZE_KEY_ID, api_key=WYZE_API_KEY)
        access_token = response.get('access_token')
        return access_token
    except WyzeApiError as e:
        print(f"Wyze API Error: {e}")
        return None

def upload_to_garmin(file_path):
    try:
        garth.resume('./tokens')
        garth.client.username
    except:
        try:
            garth.login(GARMIN_USERNAME, GARMIN_PASSWORD)
            garth.save('./tokens')
        except:
            email = input("Enter Garmin email address: ")
            password = getpass("Enter Garmin password: ")
            try:
                garth.login(email, password)
                garth.save('./tokens')
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
        'active_met': int(float(scale.latest_records[0].bmr) * 1.25),
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
    access_token = login_to_wyze()

    if access_token:
        client = Client(token=access_token)
        for device in client.devices_list():
            if device.type == "WyzeScale":
                scale = client.scales.info(device_mac=device.mac)
                print(f"Scale found with MAC {device.mac}. Latest record is:")
                print(scale.latest_records)
                print(f"Body Type: {scale.latest_records[0].body_type or 5}")

                print("Generating fit data...")
                generate_fit_file(scale)
                print("Fit data generated...")

                fitfile_path = "wyze_scale.fit"
                cksum_file_path = "./cksum.txt"

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

