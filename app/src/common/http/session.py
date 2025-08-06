# -*- coding: utf-8 -*-
import os
import ctypes
import binascii
import uuid
import json
from urllib.parse import urlencode
from common.errors import HTTPError as HubHTTPError
from common.utils import extract_domain
from tasks.common.errors import HTTPError as TaskHTTPError
from .classes import Request, Response, Headers, Cookies
from .client import CLIENT
from .constants import CLIENTS


class Session:
    def __init__(self, client="chrome", proxy=None, **kwargs):
        self.settings = {
            "uuid": str(uuid.uuid4()),
            "proxy": proxy.url if proxy else "",
            "timeout": kwargs.get("timeout", 60),
            "enableCookieJar": kwargs.get("cookie_jar", True),
            "discardResponse": kwargs.get("discard_response", False),
            "sslpin": kwargs.get("ssl_pin", False),
            "clienthello": kwargs.get("clienthello") or CLIENTS[client]["clienthello"],
            "http2Frame": kwargs.get("http2_frame") or CLIENTS[client]["http2Frame"]
        }

        self.headers = Headers(client,
            user_agent=kwargs.get("user_agent"),
            accept_language=kwargs.get("accept_language")
        )
        self.cookies = Cookies(self.settings["uuid"])
        self.proxy = proxy

        if function := kwargs.get("hook"):
            self.request = function(self.request)

        if kwargs.get("in_hub"):
            self.http_error = HubHTTPError
        else:
            self.http_error = TaskHTTPError

        self.configure_client()

    def configure_client(self):
        CLIENT.createClient(
            json.dumps(self.settings).encode()
        )

    def set_proxy(self, proxy):
        self.settings["proxy"] = proxy.url
        self.proxy = proxy

        self.configure_client()

    def clear_proxy(self):
        self.settings["proxy"] = ""
        self.proxy = None

        self.configure_client()

    def format_body(self, body, content_type):
        if content_type in ["application/json", "text/plain"]:
            return json.dumps(body, ensure_ascii=False), content_type
        elif content_type == "application/x-www-form-urlencoded":
            return urlencode(body), content_type
        elif content_type == "multipart/form-data":
            boundary = binascii.hexlify(os.urandom(16)).decode()

            return (
                "".join(
                    f'--{boundary}\nContent-Disposition: form-data; name="{key}"; filename="{value[0]}"\nContent-Type: {value[1]}\n\n{value[2]}\n'
                    if isinstance(value, tuple) and len(value) == 3 else
                    f'--{boundary}\nContent-Disposition: form-data; name="{key}"\n\n{value}\n'
                    for key, value in body.items()
                ) + f"--{boundary}--\n",
                f"multipart/form-data; boundary={boundary}"
            )
        else:
            raise self.http_error

    def format_headers(self, headers):
        for header in headers:
            if header.lower() == "user-agent":
                headers[header] = self.headers.user_agent
            elif header.lower() == "sec-ch-ua":
                headers[header] = self.headers.client_hint
            elif header.lower() == "sec-ch-ua-platform":
                headers[header] = self.headers.platform
            elif header.lower() == "accept-language":
                headers[header] = self.headers.accept_language

        headers["Cookie" if headers.get("User-Agent") else "cookie"] = ""

        return [
            [key, value] for key, value in headers.items()
        ]

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def head(self, url, **kwargs):
        return self.request("HEAD", url, **kwargs)

    def patch(self, url, **kwargs):
        return self.request("PATCH", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def request(self, method, url, params=None, body=None, headers=None, **kwargs):
        request = {
            "method": method,
            "url": url,
            "body": "",
            "headers": [],
            "uuid": self.settings["uuid"],
            "followRedirect": kwargs.get("allow_redirects", True),
            "sendRawBody": kwargs.get("return_bytes", False)
        }

        body = body or {}
        headers = headers or {}

        if params:
            request["url"] += f"?{urlencode(params)}"

        if body:
            content_type_name = (
                "Content-Type" if "Content-Type" in headers else "content-type"
            )

            request["body"], headers[content_type_name] = self.format_body(
                body, headers[content_type_name].split(";")[0]
            )

        request["headers"] = self.format_headers(headers)

        raw_response = CLIENT.execReq(
            json.dumps(request).encode()
        )
        response = json.loads(
            ctypes.c_char_p.from_buffer(raw_response).value
        )
        CLIENT.freeMemory(raw_response)

        if response["Status"] in [0, 999]:
            raise self.http_error

        if response["Cookies"] and response["Cookies"] != "null":
            for cookie in response["Cookies"]:
                self.cookies.set_local(
                    cookie["Name"], cookie["Value"], extract_domain(response["Url"])
                )
        else:
            response["Cookies"] = {}

        return Response(
            response, Request(request | {"body": body})
        )
