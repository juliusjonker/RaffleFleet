# -*- coding: utf-8 -*-
from constants.apis import ANTICAPTCHA_REF_ID
from common import http
from common.utils import sleep
from tasks.common.errors import JSONError, HTTPError, CaptchaError


class AntiCaptcha:
    api_domain = "api.anti-captcha.com"
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
                "task": {
                    "type": "RecaptchaV2TaskProxyless",
                    "websiteKey": site_key,
                    "websiteURL": f"https://{domain}/"
                },
                "softId": ANTICAPTCHA_REF_ID
            }
        elif variant == "v3":
            return {
                "task": {
                    "type": "RecaptchaV3TaskProxyless",
                    "websiteKey": site_key,
                    "websiteURL": f"https://{domain}/",
                    "pageAction": metadata.get("action", "verify"),
                    "minScore": 0.3
                },
                "softId": ANTICAPTCHA_REF_ID
            }
        elif variant == "h":
            return {
                "task": {
                    "type": "HCaptchaTaskProxyless",
                    "websiteKey": site_key,
                    "websiteURL": f"https://{domain}/"
                },
                "softId": ANTICAPTCHA_REF_ID
            }

    def fetch_token(self, api_key):
        self.body["clientKey"] = api_key

        for _ in range(self.max_retries):
            try:
                response = self.session.post(
                    f"https://{self.api_domain}/createTask",
                    body=self.body,
                    headers={
                        "content-type": "application/json"
                    }
                )
                content = response.json()

                if not content["errorId"]:
                    task_id = content["taskId"]
                    break
                else:
                    raise CaptchaError(2, self.variant_name, content["errorCode"])
            except (HTTPError, JSONError, KeyError):
                continue
        else:
            raise CaptchaError(3, self.variant_name, "API_ERROR")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{self.api_domain}/getTaskResult",
                    body={
                        "clientKey": api_key,
                        "taskId": task_id
                    },
                    headers={
                        "content-type": "application/json"
                    }
                )
                content = response.json()

                if not content["errorId"]:
                    if content["status"] == "ready":
                        return content["solution"]["gRecaptchaResponse"]
                    else:
                        sleep(self.interval)
                        continue
                else:
                    raise CaptchaError(4, self.variant_name, content["errorCode"])
            except (HTTPError, JSONError, KeyError):
                error_count += 1
                continue
        else:
            raise CaptchaError(5, self.variant_name, "API_ERROR")
