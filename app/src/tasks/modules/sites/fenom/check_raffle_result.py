# -*- coding: utf-8 -*-
import random
import re
from common import http
from common.utils import sleep
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, CloudflareError
from tasks.hooks import cloudflare
from .constants import NAME, DOMAIN


class CheckRaffleResult:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = Logger(
            NAME, task.id, task.formatted_parent_id
        )

        self.session = http.Session(
            proxy=task.proxies.get(),
            hook=cloudflare.get_hook(self.logger)
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
            if not self.product.match(re.findall(r">\n(.*?) :", product)[0]):
                continue

            self.product.size = re.findall(r":.*?- (.*?) \|", product)[0]

            if "Your name was drawn" in product:
                return "won"
            elif "Your name wasn't drawn" in product:
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
                response = self.session.get(
                    f"https://{DOMAIN}/en/authentication?back=my-account",
                    headers={
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "referer": f"https://{DOMAIN}/en/",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, CloudflareError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                break
            else:
                self.logger.error((
                    f"Request failed: {response.status} - {response.reason}",
                    "switching proxy" if response.status in [401, 403, 429] else None
                )), self.delay()
                if response.status in [401, 403, 429]:
                    self.switch_proxy()
                error_count += 1
                continue
        else:
            return False

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}/en/authentication?back=my-account",
                    body={
                        "back": "my-account",
                        "email": self.task.parent.email,
                        "password": self.task.parent.password,
                        "submitLogin": "1"
                    },
                    headers={
                        "content-length": None,
                        "cache-control": "max-age=0",
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "origin": f"https://{DOMAIN}",
                        "content-type": "application/x-www-form-urlencoded",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
                        "referer": f"https://{DOMAIN}/en/authentication?back=my-account",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, CloudflareError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                if "/my-account" in response.url:
                    break
                elif "Authentication failed" in response.body:
                    self.logger.error("Failed to log in: Invalid credentials")
                    return False
                else:
                    self.logger.error("Failed to log in"), self.delay()
                    error_count += 1
                    continue
            else:
                self.logger.error((
                    f"Request failed: {response.status} - {response.reason}",
                    "switching proxy" if response.status in [401, 403, 429] else None
                )), self.delay()
                if response.status in [401, 403, 429]:
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
                    f"https://{DOMAIN}/en/my-entries",
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
                        "referer": f"https://{DOMAIN}/en/my-account",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, CloudflareError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["status"] = self.get_raffle_result(
                        re.findall(r"<tr>([\s|\S]*?)</tr>", re.findall(r"<tbody([\s|\S]*?)</tbody>", response.body)[0])
                    )
                    break
                except IndexError:
                    if "Your have no entry" in response.body:
                        self.logger.error("Failed to check raffle result: No entry found")
                        return False
                    else:
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
