# -*- coding: utf-8 -*-
import random
import re
import html
from datetime import datetime, timezone
from common import http
from common.utils import sleep
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME, DOMAIN, RAFFLE_DOMAIN


class EnterRaffle:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = Logger(
            NAME, task.id, task.formatted_parent_id
        )

        self.session = http.Session(
            proxy=task.proxies.get()
        )

        self.product = Product()
        self.data = {}

    @staticmethod
    def delay():
        sleep(random.randint(1000, 2000) / 1000)

    def switch_proxy(self):
        self.session.set_proxy(
            self.task.proxies.get()
        )

    @staticmethod
    def is_raffle_closed(close_datetime):
        return datetime.strptime(
            close_datetime, "%Y-%m-%dT%H:%M:%S%z"
        ).astimezone(timezone.utc) < datetime.now(timezone.utc)

    def get_size(self):
        sizes_in_range = [
            size for size in [
                4, 4.5, 5, 5.5,
                6, 6.5, 7, 7.5,
                8, 8.5, 9, 9.5,
                10, 10.5, 11, 11.5,
                12, 12.5, 13, 14
            ] if self.task.input.size_range.fits(size)
        ]

        if sizes_in_range:
            return str(random.choice(sizes_in_range))
        else:
            return ""

    def execute(self):
        status = "entered" if self.fetch_raffle() else "failed"

        if status == "entered":
            webhooks.Entry(
                NAME, self.product, self.task.parent, self.session.proxy
            ).send()

        self.task.manager.increment(
            status,
            task=self.task,
            product=self.product,
            parent=self.task.parent,
            proxy=self.session.proxy
        )

    def fetch_raffle(self):
        self.logger.info("Entering raffle...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    self.task.input.raffle["url"],
                    headers={
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
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    if self.is_raffle_closed(re.findall(r"Date\('(.*?)'", response.body)[0]):
                        self.logger.error("Failed to enter raffle: Raffle closed")
                        return False

                    self.product.name = html.unescape(re.findall('<meta property="og:title" content="(.*?)">', response.body)[0])
                    self.product.price = "$ " + re.findall('<meta property="og:price:amount" content="(.*?)">', response.body)[0]
                    self.product.image = re.findall('<meta property="og:image" content="(.*?)">', response.body)[0]
                    self.product.size = self.get_size()
                    break
                except (IndexError, ValueError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 404:
                self.logger.error("Failed to enter raffle: Raffle closed")
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
                response = self.session.get(
                    f"https://{RAFFLE_DOMAIN}/raffle-page/",
                    headers={
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                        "sec-fetch-site": "same-site",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
                        "referer": f"https://{DOMAIN}/",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["formUrl"] = re.findall('<form id="sib-form" method="POST" action="(.*?)"', response.body)[0]
                    break
                except IndexError:
                    self.logger.error("Failed to enter raffle"), self.delay()
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

        if self.product.size:
            return self.enter_raffle()
        else:
            self.logger.error("Failed to enter raffle: No sizes in range")
            return False

    def enter_raffle(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    self.data["formUrl"],
                    params={
                        "isAjax": "1"
                    },
                    body={
                        "FULLNAME": self.task.parent.full_name,
                        "EMAIL": self.task.parent.email,
                        "SMS__COUNTRY_CODE": self.task.parent.phone_prefix,
                        "SMS": self.task.parent.full_phone.removeprefix("+"),
                        "ADDRESS": self.task.parent.address,
                        "CITY": self.task.parent.city,
                        "STATE": self.task.parent.province,
                        "ZIP": self.task.parent.postcode,
                        "ITEMNAME": self.product.name,
                        "SIZE": self.product.size,
                        "INSTAGRAM": self.task.parent.instagram,
                        "email_address_check": "",
                        "locale": "en"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "sec-ch-ua-platform": None,
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "content-type": "multipart/form-data",
                        "accept": "*/*",
                        "origin": f"https://{RAFFLE_DOMAIN}",
                        "sec-fetch-site": "cross-site",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{RAFFLE_DOMAIN}/",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    if response.json()["success"]:
                        break
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 400:
                try:
                    if "already linked to an existing account" in response.json()["errors"]["SMS"]:
                        self.logger.error("Failed to enter raffle: Already entered")
                        return False
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to enter raffle"), self.delay()
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

        self.logger.success("Successfully entered raffle")
        return True
