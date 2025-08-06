# -*- coding: utf-8 -*-
import re
from constants import regexes
from tasks.common.classes import Instagram
from .constants import NAME, POST_DOMAIN
from .enter_raffle import EnterRaffle
from .check_inbox import CheckInbox


SUBMODULES = {
    "Enter raffle": {
        "module": EnterRaffle,
        "parent": Instagram,
        "subject": "entries",
        "input": ["activeRaffle", "tasks", "proxies"],
        "output": ["raffle", *Instagram.fields(), "proxy"],
        "statuses": ["pending", "entered", "failed"],
        "isMultiThreaded": True
    },
    "Check inbox": {
        "module": CheckInbox,
        "parent": Instagram,
        "subject": "wins",
        "input": ["instagramAccount", "tasks", "proxies"],
        "output": ["sender", "message", *Instagram.fields(), "proxy"],
        "statuses": ["pending", "new_message", "empty", "failed"],
        "isMultiThreaded": True
    }
}

INPUT_CONFIG = {
    "fileType": "csv",
    "raffle": {
        "type": "url",
        "regex": re.compile(
            regexes.URL.pattern.format(re.escape(POST_DOMAIN))
        )
    }
}
