# -*- coding: utf-8 -*-
import random
import re
import html
from common import http
from common.utils import sleep
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, CloudflareError, JSONError
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
            if not self.product.match(html.unescape(re.findall('alt="(.*?)"', product)[0])):
                continue

            self.product.price = re.findall("(€.*?) ", product)[0]
            self.product.image = html.unescape(re.findall('class="product-image-photo" src="(.*?)"', product)[0])
            self.product.size = re.findall(r"EU (.*?)&", product)[0].replace(",", ".")

            if "class='raffle-winner'" in product:
                return "won"
            elif "class='raffle-loose'" in product:
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
                    f"https://{DOMAIN}/eu_en/",
                    headers={
                        "cache-control": "max-age=0",
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                        "sec-fetch-site": "none",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
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
                    f"https://{DOMAIN}/eu_en/sociallogin/popup/login/",
                    body={
                        "username": self.task.parent.email,
                        "password": self.task.parent.password
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "*/*",
                        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "x-requested-with": "XMLHttpRequest",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{DOMAIN}/eu_en/",
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
                    content = response.json()

                    if content.get("success"):
                        break
                    elif "Invalid login" in content["message"]:
                        self.logger.error("Failed to log in: Invalid credentials")
                        return False
                    elif "This account isn't confirmed" in content["message"]:
                        self.logger.error("Failed to log in: Account isn't verified")
                        return False
                    else:
                        raise KeyError
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
                    f"https://{DOMAIN}/eu_en/raffle/customer/",
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
                        "referer": f"https://{DOMAIN}/eu_en/",
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
                        re.findall(r'<li class="product-item">([\s|\S]*?)</li>', response.body)
                    )
                    break
                except IndexError:
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
