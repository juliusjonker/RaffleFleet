# -*- coding: utf-8 -*-
CHROME_VERSION = "115.0.0.0"
CHROME_CLIENT_HINT = '"Not/A)Brand";v="99", "Google Chrome";v="{version}", "Chromium";v="{version}"'.format(
    version=CHROME_VERSION.split(".")[0]
)
ACCEPT_LANGUAGE = "en-GB,en;q=0.9"

CLIENTS = {
    "chrome": {
        "clienthello": "HelloChrome_91",
        "http2Frame": {
            "maxHeaderListSize": 262144,
            "initialWindowSize": 6291456,
            "initialHeaderTableSize": 65536,
            "maxConcurrentStream": 1000,
            "maxHeaderListSizeUnlimited": False,
            "maxConcurrentStreamUnlimited": False
        }
    },
    "ios": {
        "clienthello": "HelloIOS_14_2",
        "http2Frame": {
            "initialHeaderTableSize": 4096,
            "initialWindowSize": 2097152,
            "maxConcurrentStream": 100,
            "maxHeaderListSizeUnlimited": True
        }
    },
    "iosConfirmed": {
        "clienthello": "HelloAndroid_ConfirmedOld",
        "http2Frame": {
            "initialHeaderTableSize": 4096,
            "initialWindowSize": 2097152,
            "maxConcurrentStream": 100,
            "maxHeaderListSizeUnlimited": True
        }
    }
}

STATUS_CODE_REASONS = {
    100: "Continue",
    101: "Switching Protocols",
    102: "Processing",
    103: "Early Hints",

    200: "OK",
    201: "Created",
    202: "Accepted",
    203: "Non-Authoritative Information",
    204: "No Content",
    205: "Reset Content",
    206: "Partial Content",
    207: "Multi-Status",
    208: "Already Reported",
    226: "IM Used",

    300: "Multiple Choices",
    301: "Moved Permanently",
    302: "Found (Moved Temporarily)",
    303: "See Other",
    304: "Not Modified",
    305: "Use Proxy",
    306: "reserved",
    307: "Temporary Redirect",
    308: "Permanent Redirect",

    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    407: "Proxy Authentication Required",
    408: "Request Timeout",
    409: "Conflict",
    410: "Gone",
    411: "Length Required",
    412: "Precondition Failed",
    413: "Payload Too Large",
    414: "URI Too Long",
    415: "Unsupported Media Type",
    416: "Range Not Satisfiable",
    417: "Expectation Failed",
    418: "I’m a teapot",
    420: "Policy Not Fulfilled",
    421: "Misdirected Request",
    422: "Unprocessable Entity",
    423: "Locked",
    424: "Failed Dependency",
    425: "Too Early",
    426: "Upgrade Required",
    428: "Precondition Required",
    429: "Too Many Requests",
    431: "Request Header Fields Too Large",
    444: "No Response",
    449: "The request should be retried after doing the appropriate action",
    451: "Unavailable For Legal Reasons",
    499: "Client Closed Request",

    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
    505: "HTTP Version not supported",
    506: "Variant Also Negotiates",
    507: "Insufficient Storage",
    508: "Loop Detected",
    509: "Bandwidth Limit Exceeded",
    510: "Not Extended",
    511: "Network Authentication Required"
}
