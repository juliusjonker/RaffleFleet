# -*- coding: utf-8 -*-
import json


DFLT_MSG = "Unexpected error (ID: {})"

IDS = {
    "http": 1001,
    "json": 1002,
    "security": 1003,
    "download": 1004,
    "keyError": 1005,
    "unknown": 1006
}


class FileError(Exception):
    def __init__(self, file_name, reason):
        self.reason = reason
        self.msg = f"{file_name} is {reason}"


class TaskError(Exception):
    def __init__(self, msg):
        self.msg = msg


class HTTPError(Exception):
    msg = DFLT_MSG.format(IDS["http"])


class JSONError(Exception):
    msg = DFLT_MSG.format(IDS["json"])


class SecurityError(Exception):
    msg = DFLT_MSG.format(IDS["security"])


class DownloadError(Exception):
    msg = DFLT_MSG.format(IDS["download"])


json.decoder.JSONDecodeError = JSONError
