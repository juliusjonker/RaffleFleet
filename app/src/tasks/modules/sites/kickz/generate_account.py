# -*- coding: utf-8 -*-
import random
import re
from common import http
from common.utils import sleep
from tasks.common import Logger
from tasks.common.classes import Task
from tasks.common.errors import HTTPError, ChallengeError, JSONError
from tasks.hooks import pow_challenge
from .constants import NAME, DOMAIN, REGIONS


class GenerateAccount:
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

        self.data = {
            "region": REGIONS.get(self.task.parent.country, "en")
        }

    @staticmethod
    def delay():
        sleep(random.randint(1000, 2000) / 1000)

    def switch_proxy(self):
        self.session.set_proxy(
            self.task.proxies.get()
        )

    def execute(self):
        status = "generated" if self.create_account() else "failed"

        self.task.manager.increment(
            status,
            task=self.task,
            parent=self.task.parent,
            proxy=self.session.proxy
        )

    def create_account(self):
        self.logger.info("Generating account...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/{self.data['region']}/login/",
                    headers={
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
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
                try:
                    self.data["companyId"] = re.findall('data-company-id="(.*?)"', response.body)[0]
                    self.data["policyId"] = re.findall('data-registration-policy-id="(.*?)"', response.body)[0]
                    self.data["apiKey"] = re.findall('data-api-key="(.*?)"', response.body)[0]
                    break
                except IndexError:
                    self.logger.error("Failed to generate account"), self.delay()
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://orchestrate-api.pingone.eu/v1/company/{self.data['companyId']}/sdktoken",
                    headers={
                        "sec-ch-ua": None,
                        "x-sk-api-key": self.data["apiKey"],
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "accept": "*/*",
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "cross-site",
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
                try:
                    self.data["accessToken"] = response.json()["access_token"]
                    break
                except (JSONError, KeyError):
                    self.logger.error("Failed to generate account"), self.delay()
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://account.kickz.com/davinci/policy/{self.data['policyId']}/start",
                    body={
                        "lang": "en",
                        "locale": "en"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "content-type": "application/json",
                        "sec-ch-ua-mobile": "?0",
                        "authorization": "Bearer " + self.data["accessToken"],
                        "user-agent": None,
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
                try:
                    content = response.json()

                    self.data["id"] = content["id"]
                    self.data["connectionId"] = content["connectionId"]
                    self.data["interactionId"] = content["interactionId"]
                    self.data["interactionToken"] = content["interactionToken"]
                    break
                except (JSONError, KeyError):
                    self.logger.error("Failed to generate account"), self.delay()
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
                            "customer_salutation": "mrs" if self.task.parent.gender == "female" else "mr",
                            "customer_firstname": self.task.parent.first_name,
                            "customer_lastname": self.task.parent.last_name,
                            "customer_phone": self.task.parent.full_phone,
                            "email-input": self.task.parent.email,
                            "email-confirm-input": self.task.parent.email,
                            "register-password": self.task.parent.password,
                            "password-confirm": self.task.parent.password,
                            "consent": True
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
                try:
                    content = response.json()

                    self.data["id"] = content["id"]
                    self.data["connectionId"] = content["connectionId"]
                    self.data["interactionId"] = content["interactionId"]
                    self.data["interactionToken"] = content["interactionToken"]
                    break
                except (JSONError, KeyError):
                    self.logger.error("Failed to generate account"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 400:
                try:
                    if "E-mail address already used for registration" in response.json()["message"]:
                        self.logger.error("Failed to generate account: Email already in use")
                        return False
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to generate account"), self.delay()
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

        self.task.manager.sessions.save(self.task.parent, {
            "id": self.data["id"],
            "connectionId": self.data["connectionId"],
            "interactionId": self.data["interactionId"],
            "interactionToken": self.data["interactionToken"]
        })

        self.logger.success("Successfully generated account")
        return True
