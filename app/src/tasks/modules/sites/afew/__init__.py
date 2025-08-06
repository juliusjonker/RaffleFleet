# -*- coding: utf-8 -*-
import re
from constants import regexes
from tasks.common.classes import Profile, Email
from .constants import NAME
from .enter_raffle import EnterRaffle
from .verify_entry import VerifyEntry
from .fetch_emails import FetchEmails


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
    "Verify entries": {
        "module": VerifyEntry,
        "parent": Email,
        "hook": FetchEmails,
        "subject": "verification",
        "input": ["maxEmailAge", "proxies"],
        "output": [*Email.fields(), "proxy"],
        "statuses": ["pending", "verified", "failed"],
        "isMultiThreaded": True
    }
}

INPUT_CONFIG = {
    "fileType": "csv",
    "raffle": {
        "type": "url",
        "regex": re.compile(
            regexes.URL.pattern.format(r".*?\.afew-store\.com")
        )
    },
    "size": {
        "chart": "US",
        "regex": regexes.US_SIZE
    }
}
