# -*- coding: utf-8 -*-
import random
import re
import html
import json
from common import http
from common.utils import sleep, size_to_float
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME, DOMAIN


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

    def get_size(self, sizes):
        sizes_in_range = []
        for size_data in sizes:
            size = size_data["public_title"]
            if self.task.input.size_range.fits(size_to_float(size)):
                sizes_in_range.append(size)

        if sizes_in_range:
            return random.choice(sizes_in_range)
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
                        "sec-fetch-site": "same-origin",
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
                    self.product.name = html.unescape(re.findall('<meta property="og:title" content="(.*?)">', response.body)[0])
                    self.product.image = re.findall('<meta property="og:image" content="(.*?)">', response.body)[0]
                    self.product.size = self.get_size(json.loads(
                        re.findall("var meta = (.*?);", response.body)[0]
                    )["product"]["variants"])

                    self.data["productId"] = re.findall('name="g" value="(.*?)"', response.body)[0]
                    break
                except (JSONError, IndexError, KeyError, ValueError):
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
                    "https://manage.kmail-lists.com/ajax/subscriptions/subscribe",
                    body={
                        "g": self.data["productId"],
                        "$fields": "email,$first_name,$last_name,draw_shoeSize,draw_instagram,$phone_number,$consent,sms_consent",
                        "email": self.task.parent.email,
                        "$first_name": self.task.parent.first_name,
                        "$last_name": self.task.parent.last_name,
                        "draw_shoeSize": self.product.size,
                        "draw_instagram": self.task.parent.instagram,
                        "$consent": "email,mobile,sms",
                        "sms_consent": "false"
                    },
                    headers={
                        "Connection": "keep-alive",
                        "Content-Length": None,
                        "sec-ch-ua": None,
                        "Accept": "*/*",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "cache-control": "no-cache",
                        "sec-ch-ua-mobile": "?0",
                        "User-Agent": None,
                        "sec-ch-ua-platform": None,
                        "Origin": f"https://{DOMAIN}",
                        "Sec-Fetch-Site": "cross-site",
                        "Sec-Fetch-Mode": "cors",
                        "Sec-Fetch-Dest": "empty",
                        "Referer": f"https://{DOMAIN}/",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Accept-Language": None
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
