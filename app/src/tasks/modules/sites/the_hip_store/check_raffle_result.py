# -*- coding: utf-8 -*-
import random
from common import http
from common.utils import sleep
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME, DOMAIN, STORE_NAME, URL_PARAMS, USER_AGENT


class CheckRaffleResult:
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

        self.product = Product(
            name=task.input.raffle["productName"]
        )
        self.data = {}

    @staticmethod
    def delay():
        sleep(random.randint(1000, 2000) / 1000)

    def switch_proxy(self):
        self.session.set_proxy(
            self.task.proxies.get()
        )

    def get_raffle_result(self, products):
        for product in products:
            if not self.product.match(f"{product['product']['name']} {product['product']['subTitle']}"):
                continue

            self.product.image = product["product"]["mainImage"]["original"]
            self.product.size = product["product"]["option"].split(" |")[0]

            if product["status"] == "winner":
                return "won"
            elif product["status"] == "looser_processed":
                return "lost"
            else:
                return "pending"

    def execute(self):
        status = self.data["status"] if self.log_in() else "failed"

        if status == "won":
            webhooks.Win(
                NAME, self.product, self.task.parent, self.session.proxy
            ).send()

        self.task.manager.increment(
            status,
            task=self.task,
            product=self.product,
            parent=self.task.parent,
            proxy=self.session.proxy
        )

    def log_in(self):
        self.logger.info("Logging in...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://prod.jdgroupmesh.cloud/oauth2/{STORE_NAME}/token",
                    params={
                        "channel": "iphone-app",
                        "api_key": "244343803EAA4F10AE31BEEB10ECF5B8"
                    },
                    body={
                        "grant_type": "password",
                        "username": self.task.parent.email,
                        "password": self.task.parent.password,
                        "client_id": f"com.jd.{STORE_NAME}"
                    },
                    headers={
                        "content-type": "application/x-www-form-urlencoded; charset=utf-8",
                        "accept": "application/json",
                        "accept-language": None,
                        "accept-encoding": "gzip, deflate, br",
                        "content-length": None,
                        "user-agent": None
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["accessToken"] = response.json()["access_token"]
                    break
                except (JSONError, KeyError):
                    self.logger.error("Failed to log in"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 401:
                self.logger.error("Failed to log in: Invalid credentials")
                return False
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
                    f"https://{DOMAIN}/stores/{STORE_NAME}/users/oauth",
                    params=URL_PARAMS,
                    body={
                        "oauthToken": self.data["accessToken"]
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
                try:
                    self.data["userId"] = response.json()["customer"]["userID"]
                    break
                except (JSONError, KeyError):
                    self.logger.error("Failed to log in"), self.delay()
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

        self.logger.success("Successfully logged in")
        return self.fetch_raffle_result()

    def fetch_raffle_result(self):
        self.logger.info("Checking raffle result...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/stores/{STORE_NAME}/user/{self.data['userId']}/preauth",
                    params=URL_PARAMS,
                    headers={
                        "Origin": "https://launches.thehipstore.co.uk",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Accept": "*/*",
                        "Authorization": self.data["accessToken"],
                        "User-Agent": None,
                        "originalhost": DOMAIN,
                        "Accept-Language": None,
                        "Referer": "https://launches.thehipstore.co.uk/"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["status"] = self.get_raffle_result(
                        response.json()["orders"]
                    )
                    break
                except (JSONError, KeyError):
                    self.logger.error("Failed to check raffle result"), self.delay()
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

        if self.data["status"] == "won":
            self.logger.success("Checked raffle result: Won")
            return True
        elif self.data["status"] == "lost":
            self.logger.info("Checked raffle result: Lost")
            return True
        elif self.data["status"] == "pending":
            self.logger.error("Failed to check raffle result: Awaiting draw")
            return False
        else:
            self.logger.error("Failed to check raffle result: No entry found")
            return False
