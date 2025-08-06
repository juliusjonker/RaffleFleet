# -*- coding: utf-8 -*-
import os
import time
import math
import ctypes
import random
import string
import uuid
import subprocess
import urllib.request
from threading import Thread
from datetime import datetime
from dateutil import tz
from urllib.parse import urlparse, quote_plus
from constants import app
from constants.env import OS, TEMP_PATH
from constants.apis import MAPBOX_KEY
from .errors import HTTPError, JSONError, DownloadError
from . import data, http


def close(delay=8):
    sleep(delay)
    os._exit(1)  # NOQA


def sleep(duration):
    time.sleep(duration)


def current_ts(exact=False):
    return time.time() if exact else round(time.time())


def current_date():
    return time.strftime("%d-%m-%y")


def current_datetime(filename_proof=False):
    return time.strftime(
        "%d %b %H-%M-%S" if filename_proof else "%d %b %H:%M:%S"
    )


def utc_to_local(utc_datetime):
    return utc_datetime.astimezone(tz.tzlocal())


def calc_ts_delta(timestamp):
    return (
        datetime.now() - datetime.fromtimestamp(timestamp)
    ).days


def is_update_available():
    return app.VERSION != data.APP["version"]


def generate_temp_path(prefix, file_ext):
    return TEMP_PATH / f"{prefix}-{uuid.uuid4()}{file_ext}"


def hide_file(file_path):
    if OS.Windows:
        ctypes.windll.kernel32.SetFileAttributesW(
            str(file_path), 0x02
        )


def extract_domain(url):
    return urlparse(url).netloc


def joins(*strings, sep="", modifier=None):
    return sep.join(
        modifier(x) if modifier else x
        for x in strings if x is not None
    )


def get_average_length(iterator, key):
    return math.floor(
        sum(len(key(item)) for item in iterator) / len(iterator)
    ) if iterator else 0


def threaded(function):
    def wrapper(*args, **kwargs):
        Thread(target=function, args=args, kwargs=kwargs).start()

    return wrapper


def fetch_device_id():
    if OS.Windows:
        return subprocess.check_output(
            "wmic csproduct get uuid", stderr=False
        ).decode().split("\n")[1].strip()
    else:
        return subprocess.check_output(
            "ioreg -d2 -c IOPlatformExpertDevice | awk -F\\\" '/IOPlatformUUID/{print $(NF-1)}'",
            stderr=False, shell=True
        ).decode().strip()


def download_file(url, target_path):
    try:
        return urllib.request.urlretrieve(url, target_path)[0]
    except:
        raise DownloadError


def get_choice(choice, options, digit_only=False):
    choice = choice.lower().replace(" ", "")

    if choice.isdigit():
        return (
            options[int(choice) - 1]
            if len(options) >= int(choice) > 0 else None
        )
    elif not digit_only:
        try:
            return options[[
                opt.lower().replace(" ", "") for opt in options
            ].index(choice)]
        except ValueError:
            return None


def get_choices(choices, options):
    choices = choices.lower().replace(" ", "").split("," if "," in choices else ";")

    return [
        options[int(x) - 1] for x in choices
        if x.isdigit() and len(options) >= int(x) > 0
    ]


def size_to_float(size):
    return float(
        size.replace(" ", "")
        .replace(",", ".")
        .replace("1/2", ".5")
        .replace("1/3", ".33")
        .replace("2/3", ".66")
        .replace("½", ".5")
        .replace("⅓", ".33")
        .replace("⅔", ".66")
        .replace("(", "")
        .replace(")", "")
        .strip(string.ascii_letters)
    )


def prettify_ts_delta(timestamp):
    delta = timestamp - current_ts()

    days = int(delta / 86400)
    hours = int(delta / 86400 % 1 * 24)
    minutes = math.ceil(delta / 60)

    if days >= 1:
        return f"{days}d {hours}h" if hours > 0 else f"{days}d"
    elif hours >= 1:
        return f"{hours}h"
    else:
        return f"{minutes}m"


def xxx_jig(value):
    while "XXX" in value or "xxx" in value:
        value = value.replace(
            "XXX" if "XXX" in value else "xxx",
            "".join(random.choices(string.ascii_letters, k=3)), 1
        )

    return value


def generate_coordinate(coordinate, radius):
    a = radius / 111.3 * math.sqrt(random.random())
    b = 2 * math.pi * random.random()

    return (
        coordinate[0] + a * math.sin(b),
        coordinate[1] + a * math.cos(b)
    )


def is_dict_complete(dictionary, blueprint):
    if dictionary.keys() != blueprint.keys():
        return False

    for key, value in blueprint.items():
        if isinstance(value, dict):
            if not isinstance(dictionary[key], dict) or dictionary[key].keys() != value.keys():
                return False

    return True


def deep_update(base_dict, filled_dict):
    updated_dict = base_dict.copy()

    for key, value in base_dict.items():
        if key in filled_dict:
            if isinstance(value, dict):
                if isinstance(filled_dict[key], dict):
                    updated_dict[key] = deep_update(value, filled_dict[key])
            else:
                updated_dict[key] = filled_dict[key]

    return updated_dict


def fetch_coordinate(country, city):
    try:
        response = http.get(
            f"https://api.mapbox.com/geocoding/v5/mapbox.places/{quote_plus(city)}.json",
            params={
                "access_token": MAPBOX_KEY,
                "country": country
            }
        )
        content = response.json()

        return (
            content["features"][0]["center"][1],
            content["features"][0]["center"][0]
        )
    except (HTTPError, JSONError, KeyError, IndexError):
        return None
