# -*- coding: utf-8 -*-
import re
from constants import regexes
from tasks.common.classes import Profile
from .constants import NAME
from .enter_raffle import EnterRaffle
from .check_orders import CheckOrders
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
    "Check orders": {
        "module": CheckOrders,
        "parent": Profile,
        "subject": "wins",
        "input": ["expiredRaffle", "profiles", "proxies"],
        "output": ["product", "size", *Profile.fields(), "proxy"],
        "statuses": ["pending", "found", "empty", "failed"],
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
    "raffle": {
        "type": "id",
        "regex": re.compile("^[A-Z0-9]{6}$")
    },
    "size": {
        "chart": None,
        "regex": regexes.ANY_SIZE
    }
}
