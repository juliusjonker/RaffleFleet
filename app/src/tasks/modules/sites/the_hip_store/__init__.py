# -*- coding: utf-8 -*-
import re
from constants import regexes
from tasks.common.classes import Profile
from .constants import NAME, RAFFLE_DOMAIN
from .enter_raffle import EnterRaffle
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
    "Check raffle results": {
        "module": CheckRaffleResult,
        "parent": Profile,
        "subject": "wins",
        "input": ["expiredRaffle", "profiles", "proxies"],
        "output": ["product", "size", *Profile.fields(), "proxy"],
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
    "raffle": {
        "type": "url",
        "regex": re.compile(
            regexes.URL.pattern.format(re.escape(RAFFLE_DOMAIN))
        )
    },
    "size": {
        "chart": "UK",
        "regex": regexes.UK_SIZE
    }
}
