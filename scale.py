import math
import os
import sys
import wyze_sdk
import logging
#logging.basicConfig(level=logging.DEBUG)
from fit import FitEncoder_Weight
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError
from datetime import datetime
from wyze_sdk.models import (JsonObject, PropDef, epoch_to_datetime,
                             show_unknown_key_warning)
from wyze_sdk.models.devices import AbstractWirelessNetworkedDevice, DeviceProp
from wyze_sdk.api.base import BaseClient
from wyze_sdk.errors import WyzeRequestError
from wyze_sdk.models.devices import DeviceModels, Scale, ScaleRecord, UserGoalWeight
from wyze_sdk.service import WyzeResponse

response = Client().login(email=os.environ['WYZE_EMAIL'], password=os.environ['WYZE_PASSWORD'], key_id=os.environ['WYZE_KEY_ID'],api_key=os.environ['WYZE_API_KEY'])
#print(f"access token: {response['access_token']}")
#print(f"refresh token: {response['refresh_token']}")
os.environ['WYZE_ACCESS_TOKEN'] = ', '.join({response['access_token']})

try:
    client = Client(token=os.environ['WYZE_ACCESS_TOKEN'])
    for device in client.devices_list():
        if "WyzeScale" == device.type:
            scale = client.scales.info(device_mac= ', '.join({device.mac}))
            print("Scale fund and with MAC " + device.mac + " latest record is")
            print(scale.latest_records)
            print("Firmware version is " + scale.firmware_version )
            print("testing body type")
            if scale.latest_records[0].body_type == None:
                bodytype = 5
            else:
                bodytype = scale.latest_records[0].body_type
            print(bodytype)
#             """Generate fit data from measured data"""
            print("Generating fit data...")
            fit = FitEncoder_Weight()
            fit.write_file_info(time_created=math.trunc(scale.latest_records[0].measure_ts / 1000))
            fit.write_file_creator()
            fit.write_device_info(timestamp=math.trunc(scale.latest_records[0].measure_ts / 1000))
            fit.write_weight_scale(
                        timestamp=math.trunc(scale.latest_records[0].measure_ts / 1000),
                        weight=float(scale.latest_records[0].weight * 0.45359237),
                        percent_fat=float(scale.latest_records[0].body_fat),
                        percent_hydration=float(scale.latest_records[0].body_water),
                        visceral_fat_mass=float(scale.latest_records[0].body_vfr),
                        bone_mass=float(scale.latest_records[0].bone_mineral),
                        muscle_mass=float(scale.latest_records[0].muscle),
                        basal_met=float(scale.latest_records[0].bmr),
                        physique_rating=float(bodytype),
                        active_met=int(float(scale.latest_records[0].bmr) * 1.25),
                        metabolic_age=float(scale.latest_records[0].metabolic_age),
                        visceral_fat_rating=float(scale.latest_records[0].body_vfr),
                        bmi=float(scale.latest_records[0].bmi),
            )
            fit.finish()
            print("Fit data generated...")
            #sys.stdout.buffer.write(fit.getvalue())
            try:
                with open("wyze_scale.fit", "wb") as fitfile:
                    fitfile.write(fit.getvalue())
                    print("Fit file wyze_scale.fit created")
            except OSError as e:
                print(f"Got an error: {e}")
except WyzeApiError as e:
    # You will get a WyzeApiError is the request failed
    print(f"Got an error: {e}")
