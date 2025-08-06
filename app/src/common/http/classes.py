# -*- coding: utf-8 -*-
import json
import random
from common.data import USER_AGENTS
from tasks.common.classes import CaseInsensitiveDict
from .client import CLIENT
from .constants import CHROME_VERSION, CHROME_CLIENT_HINT, ACCEPT_LANGUAGE, STATUS_CODE_REASONS


class Request:
    def __init__(self, request):
        self.method = request["method"]
        self.url = request["url"]
        self.body = request["body"]
        self.headers = self.format_headers(request["headers"])

    @staticmethod
    def format_headers(headers):
        return {header[0]: header[1] for header in headers}


class Response:
    def __init__(self, response, request):
        self.status = response["Status"]
        self.reason = STATUS_CODE_REASONS[self.status]
        self.ok = self.status < 400

        self.url = response["Url"]
        if response.get("RawBody"):
            self.body = bytes(response["RawBody"])
        else:
            self.body = response["Body"]

        self.headers = CaseInsensitiveDict(response["Headers"])
        self.cookies = self.format_cookies(response["Cookies"])

        self.request = request

    @staticmethod
    def format_cookies(cookies):
        return {
            cookie["Name"]: cookie["Value"] for cookie in cookies
        }

    def json(self):
        return json.loads(self.body)


class Headers:
    def __init__(self, client, user_agent=None, accept_language=None):
        if client == "ios":
            self.user_agent = (
                user_agent or
                random.choice(USER_AGENTS["ios"])
            )

            self.client_hint = None
            self.platform = None
            self.accept_language = accept_language or ACCEPT_LANGUAGE
        else:
            self.user_agent = (
                user_agent or
                random.choice(USER_AGENTS["windows"]).format(
                    version=CHROME_VERSION
                )
            )

            self.client_hint = CHROME_CLIENT_HINT
            self.platform = '"Windows"'
            self.accept_language = accept_language or ACCEPT_LANGUAGE


class Cookies:
    def __init__(self, session_uuid):
        self.session_uuid = session_uuid

        self.jar = {}

    def get(self, name, domain=None, alt=None):
        if domain:
            try:
                return self.jar[domain][name]
            except KeyError:
                return alt
        else:
            for domain in self.jar:
                if name in self.jar[domain]:
                    return self.jar[domain][name]
            else:
                return alt

    def set(self, name, value, domain):
        if domain not in self.jar:
            self.jar[domain] = {}

        self.jar[domain][name] = value

        CLIENT.addCookie(json.dumps({
            "name": name,
            "value": value,
            "url": "https://" + domain,
            "maxAge": 31536000,
            "uuid": self.session_uuid
        }).encode())

    def set_local(self, name, value, domain):
        if domain not in self.jar:
            self.jar[domain] = {}

        self.jar[domain][name] = value

    def delete(self, name, domain):
        try:
            del self.jar[domain][name]
        except KeyError:
            pass

        CLIENT.deleteCookie(json.dumps({
            "name": name,
            "url": "https://" + domain,
            "uuid": self.session_uuid
        }).encode())

    def clear(self):
        self.jar = {}

        CLIENT.clearCookies(self.session_uuid.encode())
