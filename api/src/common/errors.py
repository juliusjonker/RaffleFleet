# -*- coding: utf-8 -*-
DFLT_MSG = "Unexpected error (ID: {})"

IDS = {
    "http": 2001,
    "whop": 2002,
    "webhook": 2003,
    "unknown": 2004
}


class LicenseError(Exception):
    def __init__(self, msg):
        self.msg = msg


class HTTPError(Exception):
    msg = DFLT_MSG.format(IDS["http"])


class WhopError(Exception):
    msg = DFLT_MSG.format(IDS["whop"])


class WebhookError(Exception):
    msg = DFLT_MSG.format(IDS["webhook"])
