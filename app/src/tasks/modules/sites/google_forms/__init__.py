# -*- coding: utf-8 -*-
import re
from constants import regexes
from tasks.common.classes import FormProfile
from .constants import NAME, DOMAIN, SHORT_DOMAIN
from .enter_form import EnterForm
from .scrape_form import ScrapeForm


SUBMODULES = {
    "Enter form": {
        "module": EnterForm,
        "parent": FormProfile,
        "subject": "formEntries",
        "input": ["form", "profiles", "proxies"],
        "output": None,
        "statuses": ["pending", "entered", "failed"],
        "isMultiThreaded": True
    },
    "Scrape form": {
        "module": ScrapeForm,
        "parent": None,
        "subject": "formScraping",
        "input": ["activeRaffle"],
        "output": None,
        "statuses": ["pending", "scraped", "failed"],
        "isMultiThreaded": False
    }
}

INPUT_CONFIG = {
    "fileType": "dir",
    "raffle": {
        "type": "url",
        "regex": re.compile(regexes.URL.pattern.format(
            f"({re.escape(DOMAIN)}|{re.escape(SHORT_DOMAIN)})"
        ))
    }
}
