# -*- coding: utf-8 -*-
from common import errors
from managers import LogManager


JSONError = errors.JSONError


class HTTPError(Exception):
    msg = (
        "Request failed: Connection error", "switching proxy"
    )


class CaptchaError(Exception):
    ids = {
        "INVALID_PROVIDER": "Invalid provider loaded",
        "ERROR_WRONG_USER_KEY": "Invalid key loaded",
        "ERROR_INVALID_TASK_DATA": "Invalid key loaded",
        "ERROR_KEY_DOES_NOT_EXIST": "Invalid key loaded",
        "ERROR_KEY_DENIED_ACCESS": "Invalid key loaded",
        "ERROR_ZERO_BALANCE": "No balance",
        "ERROR_IP_NOT_ALLOWED": "IP not allowed",
        "ERROR_ACCOUNT_SUSPENDED": "Account suspended",
        "ERROR_IP_BLOCKED": "IP blocked by provider",
        "ERROR_IP_BLOCKED_5MIN": "IP blocked by provider",
        "IP_BANNED": "IP blocked by provider"
    }

    def __init__(self, caller_id, variant, error_id):
        LogManager.write("captcha", caller_id, f"{variant} - {error_id}")

        self.id = error_id
        if error_msg := self.ids.get(error_id):
            if "blocked" in error_msg:
                self.msg = (
                    f"Failed to solve {variant}: {error_msg}", "waiting 5m"
                )
                self.delay = 300
            else:
                self.msg = (
                    f"Failed to solve {variant}: {error_msg}", "waiting 30s"
                )
                self.delay = 30
        else:
            self.msg = f"Failed to solve {variant}"
            self.delay = 1


class CloudflareError(Exception):
    msg = "Failed to solve Cloudflare"

    def __init__(self, caller_id, info):
        LogManager.write("cloudflare", caller_id, info)


class TurnstileError(Exception):
    msg = "Failed to solve Turnstile"


class ChallengeError(Exception):
    msg = "Failed to solve challenge"
