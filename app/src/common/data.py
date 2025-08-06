# -*- coding: utf-8 -*-
import json
from constants.env import FILE_ENCODING, DEPS_PATH, SETTINGS_FIELDS


APP = {}
USER = {}
RAFFLES = {}

SETTINGS = SETTINGS_FIELDS.copy()

SITE_FILES = {}
TOOL_FILES = {}
PROXY_FILES = []

with open(DEPS_PATH / "countries.json", encoding=FILE_ENCODING) as file:
    content = json.load(file)

    COUNTRY_IDS = {
        country["convertedName"]: country["id"]
        for country in content
    }
    COUNTRY_DATA = {
        country["id"]: country
        for country in content
    }
    PHONE_DATA = {
        country["phone"]["prefix"]: country["phone"]
        for country in content
    }

with open(DEPS_PATH / "user_agents.json", encoding=FILE_ENCODING) as file:
    USER_AGENTS = json.load(file)

with open(DEPS_PATH / "first_names.csv", encoding=FILE_ENCODING) as file:
    FIRST_NAMES = [
        line.split(",")
        for line in file.read().splitlines()
    ]

with open(DEPS_PATH / "last_names.txt", encoding=FILE_ENCODING) as file:
    LAST_NAMES = file.read().splitlines()
