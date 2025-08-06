# -*- coding: utf-8 -*-
import uuid
from common import http
from common.utils import sleep
from tasks.common.errors import JSONError, HTTPError, CaptchaError


RESULTS = []


class AutoSolve:
    api_domain = "autosolve-api.aycd.io"
    auth_domain = "autosolve-dashboard-api.aycd.io"
    max_retries = 3
    interval = 3

    def __init__(self, variant_name, variant, domain, site_key, metadata):
        self.variant_name = variant_name

        self.session = http.Session()

        self.body = self.format_body(
            variant, domain, site_key, metadata
        )

    @staticmethod
    def format_body(variant, domain, site_key, metadata):
        if variant == "v2":
            return {
                "version": 0,
                "siteKey": site_key,
                "url": f"https://{domain}/"
            }
        elif variant == "v3":
            return {
                "version": 2,
                "siteKey": site_key,
                "url": f"https://{domain}/",
                "action": metadata.get("action", "verify")
            }
        elif variant == "h":
            return {
                "version": 3,
                "siteKey": site_key,
                "url": f"https://{domain}/"
            }

    def fetch_token(self, api_key):
        self.body["taskId"] = str(uuid.uuid4())

        for _ in range(self.max_retries):
            try:
                response = self.session.get(
                    f"https://{self.auth_domain}/api/v1/auth/generate-token",
                    params={
                        "apiKey": api_key
                    }
                )

                if response.ok:
                    auth_token = response.json()["token"]
                    break
                else:
                    raise CaptchaError(6, self.variant_name, "ERROR_WRONG_USER_KEY")
            except (HTTPError, JSONError, KeyError):
                continue
        else:
            raise CaptchaError(7, self.variant_name, "API_ERROR")

        for _ in range(self.max_retries):
            try:
                response = self.session.post(
                    f"https://{self.api_domain}/api/v1/tasks/create",
                    body=self.body,
                    headers={
                        "content-type": "application/json",
                        "authorization": "Token " + auth_token
                    }
                )

                if response.ok:
                    break
                else:
                    raise HTTPError
            except HTTPError:
                continue
        else:
            raise CaptchaError(8, self.variant_name, "API_ERROR")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{self.api_domain}/api/v1/tasks",
                    headers={
                        "authorization": "Token " + auth_token
                    }
                )

                if response.ok:
                    for task in response.json():
                        RESULTS.append(task)

                    for task in RESULTS:
                        if task["taskId"] == self.body["taskId"]:
                            RESULTS.remove(task)

                            if task["status"] == "success":
                                return task["token"]
                            else:
                                raise CaptchaError(9, self.variant_name, task["status"])
                    else:
                        sleep(self.interval)
                        continue
                else:
                    raise HTTPError
            except (HTTPError, JSONError, KeyError):
                error_count += 1
                continue
        else:
            raise CaptchaError(10, self.variant_name, "API_ERROR")
