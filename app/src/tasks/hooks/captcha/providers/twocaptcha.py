# -*- coding: utf-8 -*-
from constants.apis import TWOCAPTCHA_REF_ID
from common import http
from common.utils import sleep
from tasks.common.errors import JSONError, HTTPError, CaptchaError


class TwoCaptcha:
    api_domain = "2captcha.com"
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
                "method": "userrecaptcha",
                "googlekey": site_key,
                "pageurl": f"https://{domain}/",
                "soft_id": TWOCAPTCHA_REF_ID,
                "json": 1,
            }
        elif variant == "v3":
            return {
                "method": "userrecaptcha",
                "version": "v3",
                "googlekey": site_key,
                "pageurl": f"https://{domain}/",
                "action": metadata.get("action", "verify"),
                "soft_id": TWOCAPTCHA_REF_ID,
                "json": 1
            }
        elif variant == "h":
            return {
                "method": "hcaptcha",
                "sitekey": site_key,
                "pageurl": f"https://{domain}/",
                "soft_id": TWOCAPTCHA_REF_ID,
                "json": 1
            }

    def fetch_token(self, api_key):
        self.body["key"] = api_key

        for _ in range(self.max_retries):
            try:
                response = self.session.get(
                    f"https://{self.api_domain}/in.php",
                    params=self.body
                )
                content = response.json()

                if content["status"]:
                    task_id = content["request"]
                    break
                else:
                    raise CaptchaError(19, self.variant_name, content["request"])
            except (HTTPError, JSONError, KeyError):
                continue
        else:
            raise CaptchaError(20, self.variant_name, "API_ERROR")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{self.api_domain}/res.php",
                    params={
                        "key": api_key,
                        "id": task_id,
                        "action": "get",
                        "json": 1
                    }
                )
                content = response.json()

                if content["status"]:
                    return content["request"]
                elif content["request"] == "CAPCHA_NOT_READY":
                    sleep(self.interval)
                    continue
                else:
                    raise CaptchaError(21, self.variant_name, content["request"])
            except (HTTPError, JSONError, KeyError):
                error_count += 1
                continue
        else:
            raise CaptchaError(22, self.variant_name, "API_ERROR")
