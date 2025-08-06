# -*- coding: utf-8 -*-
import urllib3
import json
from urllib.parse import urlencode
from .errors import HTTPError


urllib3.HTTPResponse.json = lambda x: json.loads(x.data)

SESSION = urllib3.PoolManager(timeout=30)


def get(url, params=None, headers=None):
    if params:
        url += f"?{urlencode(params)}"

    try:
        return SESSION.request(
            "GET", url, headers=headers
        )
    except:
        raise HTTPError


def post(url, params=None, body=None, headers=None):
    if params:
        url += f"?{urlencode(params)}"

    if headers["Content-Type"] == "application/json":
        body = {
            "body": json.dumps(body)
        }
    elif headers["Content-Type"] == "multipart/form-data":
        del headers["Content-Type"]
        body = {
            "fields": body
        }

    try:
        return SESSION.request(
            "POST", url, headers=headers, **body
        )
    except:
        raise HTTPError
