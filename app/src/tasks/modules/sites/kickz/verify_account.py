# -*- coding: utf-8 -*-
import random
from common import http
from common.utils import sleep
from tasks.common import Logger
from tasks.common.classes import Task
from tasks.common.errors import HTTPError, ChallengeError, JSONError
from tasks.hooks import pow_challenge
from .constants import NAME, DOMAIN


class VerifyAccount:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = Logger(
            NAME, task.id, task.formatted_parent_id
        )

        self.session = http.Session(
            proxy=task.proxies.get(),
            hook=pow_challenge.hook
        )

        self.data = {}

    @staticmethod
    def delay():
        sleep(random.randint(1000, 2000) / 1000)

    def switch_proxy(self):
        self.session.set_proxy(
            self.task.proxies.get()
        )

    def execute(self):
        status = "verified" if self.verify_account() else "failed"

        self.task.manager.increment(
            status,
            task=self.task,
            parent=self.task.parent,
            proxy=self.session.proxy
        )

    def verify_account(self):
        self.logger.info("Verifying account...")

        if content := self.task.manager.sessions.get(self.task.parent):
            self.data.update(content)
        else:
            self.logger.error("Failed to verify account: No session found")
            return False

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://account.kickz.com/davinci/connections/{self.data['connectionId']}/capabilities/customHTMLTemplate",
                    body={
                        "id": self.data["id"],
                        "nextEvent": {
                            "constructType": "skEvent",
                            "eventName": "continue",
                            "params": [],
                            "eventType": "post",
                            "postProcess": {}
                        },
                        "parameters": {
                            "buttonType": "form-submit",
                            "buttonValue": "submit",
                            "verificationCode": self.task.input.verification["code"]
                        },
                        "eventName": "continue"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "interactiontoken": self.data["interactionToken"],
                        "user-agent": None,
                        "content-type": "application/json",
                        "interactionid": self.data["interactionId"],
                        "sec-ch-ua-platform": None,
                        "accept": "*/*",
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-site",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{DOMAIN}/",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, ChallengeError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                break
            elif response.status == 400:
                try:
                    error_msg = response.json()["message"]

                    if "Your code is invalid or has expired" in error_msg:
                        self.logger.error("Failed to verify account: Invalid code")
                        return False
                    elif "Capability not found" in error_msg or "Request timed out" in error_msg:
                        self.logger.error("Failed to verify account: Already verified")
                        return False
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to verify account"), self.delay()
                    error_count += 1
                    continue
            else:
                self.logger.error((
                    f"Request failed: {response.status} - {response.reason}",
                    "switching proxy" if response.status in [403, 429] else None
                )), self.delay()
                if response.status in [403, 429]:
                    self.switch_proxy()
                error_count += 1
                continue
        else:
            return False

        self.logger.success("Successfully verified account")
        return True
