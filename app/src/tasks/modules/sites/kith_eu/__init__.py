# -*- coding: utf-8 -*-
import re
from constants import regexes
from tasks.common.classes import Profile
from .constants import NAME, LOCATIONS
from .enter_raffle import EnterRaffle
from .enter_instore_raffle import EnterInstoreRaffle
from .check_raffle_result import CheckRaffleResult
from .generate_account import GenerateAccount


SUBMODULES = {
    "Enter raffle": {
        "module": EnterRaffle,
        "parent": Profile,
        "subject": "entries",
        "input": ["activeRaffle", "sizeRange", "profiles", "proxies"],
        "output": ["product", "size", *Profile.fields(), "proxy"],
        "statuses": ["pending", "entered", "failed"],
        "isMultiThreaded": True
    },
    "Enter instore raffle": {
        "module": EnterInstoreRaffle,
        "parent": Profile,
        "subject": "entries",
        "input": ["storeLocation", "activeRaffle", "sizeRange", "profiles", "proxies"],
        "output": ["location", "product", "size", *Profile.fields(), "proxy"],
        "statuses": ["pending", "entered", "failed"],
        "isMultiThreaded": True
    },
    "Check raffle results": {
        "module": CheckRaffleResult,
        "parent": Profile,
        "subject": "wins",
        "input": ["expiredRaffle", "profiles", "proxies"],
        "output": ["location", "product", "size", *Profile.fields(), "proxy"],
        "statuses": ["pending", "won", "lost", "failed"],
        "isMultiThreaded": True
    },
    "Generate accounts": {
        "module": GenerateAccount,
        "parent": Profile,
        "subject": "accounts",
        "input": ["profiles", "proxies"],
        "output": [*Profile.fields(), "proxy"],
        "statuses": ["pending", "generated", "failed"],
        "isMultiThreaded": True
    }
}

INPUT_CONFIG = {
    "fileType": "csv",
    "location": {
        "options": LOCATIONS
    },
    "raffle": {
        "type": "id",
        "regex": re.compile("^[0-9]{3}$")
    },
    "size": {
        "chart": "US",
        "regex": regexes.US_SIZE
    }
}
