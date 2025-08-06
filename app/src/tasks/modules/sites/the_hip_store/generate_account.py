# -*- coding: utf-8 -*-
import random
from common import http
from common.utils import sleep
from tasks.common import Logger
from tasks.common.classes import Task
from tasks.common.errors import HTTPError
from tasks.hooks import captcha
from .constants import NAME, DOMAIN, STORE_NAME, URL_PARAMS, USER_AGENT, RECAPTCHA_SITE_KEY


class GenerateAccount:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = Logger(
            NAME, task.id, task.formatted_parent_id
        )

        self.session = http.Session(
            client="ios",
            proxy=task.proxies.get(),
            user_agent=USER_AGENT
        )

        self.captcha = captcha.Solver(
            self.logger, "v3", DOMAIN, RECAPTCHA_SITE_KEY, metadata={
                "action": "Login/SignUp"
            }
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
                response = self.session.post(
                    f"https://{DOMAIN}/stores/{STORE_NAME}/users/signup",
                    params=URL_PARAMS,
                    body={
                        "guestUser": False,
                        "loggedIn": False,
                        "firstName": self.task.parent.first_name,
                        "lastName": self.task.parent.last_name,
                        "password": self.task.parent.password,
                        "addresses": [{
                            "firstName": self.task.parent.first_name,
                            "lastName": self.task.parent.last_name,
                            "address1": self.task.parent.address,
                            "address2": self.task.parent.line_2,
                            "town": self.task.parent.city,
                            "county": self.task.parent.province,
                            "postcode": self.task.parent.postcode,
                            "locale": self.task.parent.country.lower(),
                            "phone": self.task.parent.full_phone,
                            "isPrimaryAddress": True,
                            "isPrimaryBillingAddress": True
                        }],
                        "email": self.task.parent.email,
                        "verification": self.captcha.solve()
                    },
                    headers={
                        "Accept": "*/*",
                        "originalhost": DOMAIN,
                        "Accept-Language": None,
                        "Accept-Encoding": "gzip, deflate, br",
                        "Content-Type": "text/plain;charset=UTF-8",
                        "Origin": "https://launches.thehipstore.co.uk",
                        "Content-Length": None,
                        "Connection": "keep-alive",
                        "User-Agent": None,
                        "Referer": "https://launches.thehipstore.co.uk/"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                break
            elif response.status == 409:
                self.logger.error("Failed to generate account: Email already in use")
                return False
            elif response.status in [400, 500]:
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

        self.logger.success("Successfully generated account")
        return True
