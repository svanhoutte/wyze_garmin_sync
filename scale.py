#!/usr/bin/python3
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
    fit.write_file_info(time_created=timestamp)
    fit.write_file_creator()
    fit.write_device_info(timestamp=timestamp)
    fit.write_weight_scale(
        timestamp=timestamp,
        weight=weight_in_kg,
        percent_fat=float(scale.latest_records[0].body_fat),
        percent_hydration=float(scale.latest_records[0].body_water),
        visceral_fat_mass=float(scale.latest_records[0].body_vfr),
        bone_mass=float(scale.latest_records[0].bone_mineral),
        muscle_mass=float(scale.latest_records[0].muscle),
        basal_met=float(scale.latest_records[0].bmr),
        physique_rating=float(scale.latest_records[0].body_type or 5),
        active_met=int(float(scale.latest_records[0].bmr) * 1.25),
        metabolic_age=float(scale.latest_records[0].metabolic_age),
        visceral_fat_rating=float(scale.latest_records[0].body_vfr),
        bmi=float(scale.latest_records[0].bmi),
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

                try:
                    with open("wyze_scale.fit", "rb") as fitfile:
                        cksum = hashlib.md5(fitfile.read()).hexdigest()

                    if not os.path.exists("./cksum.txt"):
                        with open("./cksum.txt", "w") as cksum_file:
                            cksum_file.write(cksum)
                            print("cksum.txt created.")

                    with open("./cksum.txt", "r") as cksum_file:
                        stored_cksum = cksum_file.read().strip()

                    if cksum == stored_cksum:
                        print("No new measurement")
                    else:
                        print("New measurement detected. Uploading file...")
                        if upload_to_garmin('wyze_scale.fit'):
                            print("File uploaded successfully.")
                            with open("./cksum.txt", "w") as cksum_file:
                                cksum_file.write(cksum)
                        else:
                            print("File upload failed.")

                except OSError as e:
                    print(f"Got an error: {e}")

if __name__ == "__main__":
    main()

