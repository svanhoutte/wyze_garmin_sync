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
