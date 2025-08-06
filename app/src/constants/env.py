# -*- coding: utf-8 -*-
import os
import sys
import platform
from pathlib import Path
from . import app


FILE_PATH = Path(sys.argv[0]).absolute()


class STAGE:
    DEV = True if os.environ.get("DEV") else False
    PROD = ".py" not in FILE_PATH.name


class OS:
    Windows = sys.platform == "win32"
    MacOS = sys.platform == "darwin"

    name = (
        "windows" if Windows else
        "macos_arm" if platform.machine() == "arm64" else
        "macos_x86"
    )

    app_ext = ".exe" if Windows else ""
    lib_ext = ".dll" if Windows else ".dylib"
    advanced_chars = (
        MacOS or int(platform.version().split(".")[-1]) >= 22000
    )

FILE_ENCODING = "utf-8"

ILLEGAL_FILE_CHARS = str.maketrans(
    "", "", "<>:\"/\|?*"
)

DEPS_PATH = (
    Path(__file__).parent.parent / "dependencies" if STAGE.PROD else
    Path(__file__).parent.parent.parent / "dependencies"
)

STORAGE_PATH = (
    Path.home()
    / ("AppData/Local" if OS.Windows else "Library/Application Support")
    / app.NAME
)

ENTRIES_PATH = STORAGE_PATH / "entries"
LOGS_PATH = STORAGE_PATH / "logs"
SESSIONS_PATH = STORAGE_PATH / "sessions"
TEMP_PATH = STORAGE_PATH / "temp"

SITES_PATH = Path("sites")
TOOLS_PATH = Path("tools")
PROXIES_PATH = Path("proxies")
RESULTS_PATH = Path("results")

SETTINGS_PATH = Path("settings.json")
MASTERS_PATH = Path("masters.csv")

SETTINGS_FIELDS = {
    "license-key": "",
    "webhook": "",
    "captcha-solver": {
        "provider": "",
        "key": ""
    },
    "capsolver-key": "",
    "mapbox-key": ""
}
PROFILE_FIELDS = {
    "Email": "example@email.com",
    "Password": "Password123",
    "First name": "John",
    "Last name": "Doe",
    "Gender": "Male",
    "Date of birth": "31/12/2000",
    "Phone prefix": "+44",
    "Phone number": "123456789",
    "Street": "Main road",
    "House number": "1",
    "Line 2": "Apt. 1",
    "City": "London",
    "Postcode": "SW1A 2AA",
    "Province": "LND",
    "Country": "GB",
    "Card number": "1111222233334444",
    "Card month": "01",
    "Card year": "2025",
    "Card cvc": "123",
    "Instagram": "john_doe",
    "PayPal email": "example@email.com"
}

SITE_FILES = {
    "24Segons": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "4Elementos": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Adidas Confirmed": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Afew": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Baseline": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "BSTN": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Empire Skate": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Fenom": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Footpatrol": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Footshop": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Impact Premium": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Instagram": {
        "placeholder": "tasks.csv",
        "fields": {
            "Username": "john_doe",
            "Password": "Password123",
            "Input": ""
        }
    },
    "JD Sports": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Kickz": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Kith EU": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Naked": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Shelflife": {
        "placeholder": "profiles.csv",
        "fields": {
            **PROFILE_FIELDS,
            "Signature image": ""
        }
    },
    "Size?": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "The Hip Store": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    },
    "Tops & Bottoms": {
        "placeholder": "profiles.csv",
        "fields": PROFILE_FIELDS
    }
}
TOOL_FILES = {}
