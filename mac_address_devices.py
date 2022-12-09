import os
import wyze_sdk
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

client = Client(email=os.environ['WYZE_EMAIL'], password=os.environ['WYZE_PASSWORD'], totp_key=os.environ['WYZE_TOTP'])

try:
    response = client.devices_list()
    for device in client.devices_list():
        print(f"mac: {device.mac}")
        print(f"nickname: {device.nickname}")
        print(f"is_online: {device.is_online}")
        print(f"product model: {device.product.model}")
except WyzeApiError as e:
    # You will get a WyzeApiError is the request failed
    print(f"Got an error: {e}")

