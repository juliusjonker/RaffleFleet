# -*- coding: utf-8 -*-
import re
from constants import regexes
from tasks.common.classes import Profile
from .constants import NAME, RAFFLE_DOMAIN
from .enter_raffle import EnterRaffle
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
            regexes.URL.pattern.format(re.escape(RAFFLE_DOMAIN))
        )
    },
    "size": {
        "chart": "EU",
        "regex": regexes.EU_SIZE
    }
}
