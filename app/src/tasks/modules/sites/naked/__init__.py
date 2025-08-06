# -*- coding: utf-8 -*-
import re
from constants import regexes
from tasks.common.classes import Profile
from .constants import NAME, DOMAIN
from .enter_raffle_middleware import EnterRaffleMiddleware
from .generate_account import GenerateAccount


SUBMODULES = {
    "Enter raffle": {
        "module": EnterRaffleMiddleware,
        "parent": Profile,
        "subject": "entries",
        "input": ["activeRaffle", "sizeRange", "profiles", "proxies"],
        "output": ["product", "size", *Profile.fields(), "proxy"],
        "statuses": ["pending", "entered", "failed"],
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
        "type": "url",
        "regex": re.compile(
            regexes.URL.pattern.format(re.escape(DOMAIN))
        )
    },
    "size": {
        "chart": "EU",
        "regex": regexes.EU_SIZE
    }
}
