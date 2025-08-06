# -*- coding: utf-8 -*-
import re
from constants import regexes
from tasks.common.classes import Profile
from .constants import NAME
from .enter_raffle import EnterRaffle


SUBMODULES = {
    "Enter raffle": {
        "module": EnterRaffle,
        "parent": Profile,
        "subject": "entries",
        "input": ["activeRaffle", "sizeRange", "profiles", "proxies"],
        "output": ["product", "size", *Profile.fields(), "proxy"],
        "statuses": ["pending", "entered", "failed"],
        "isMultiThreaded": True
    }
}

INPUT_CONFIG = {
    "fileType": "csv",
    "raffle": {
        "type": "url",
        "regex": re.compile(
            regexes.URL.pattern.format(r"raffles\.jdsports\..*?")
        )
    },
    "size": {
        "chart": "EU",
        "regex": regexes.EU_SIZE
    }
}
