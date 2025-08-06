# -*- coding: utf-8 -*-
import random
import re
import html
import string
from common import http
from common.utils import sleep, current_ts, size_to_float
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError
from tasks.hooks import captcha, id_numbers
from .constants import NAME, DOMAIN, RAFFLE_DOMAIN, RECAPTCHA_SITE_KEY


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

        self.captcha = captcha.Solver(
            self.logger, "v2", RAFFLE_DOMAIN, RECAPTCHA_SITE_KEY
        )
        self.id_numbers = id_numbers.Generator()

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
            size = size_data.removeprefix("UK")
            if self.task.input.size_range.fits(size_to_float(size)):
                sizes_in_range.append((
                    size, size_data
                ))

        if sizes_in_range:
            return random.choice(sizes_in_range)
        else:
            return "", ""

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
                        "sec-fetch-site": "cross-site",
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
                    if "raffle is now closed" in response.body:
                        self.logger.error("Failed to enter raffle: Raffle closed")
                        return False

                    self.product.name = html.unescape(re.findall("<title>(.*?)</title>", response.body)[0]).removesuffix(" Raffle")
                    self.product.image = re.findall('class="jfWelcome-imageWrapper"><img src="(.*?)"', response.body)[0]
                    self.product.size, self.data["sizeId"] = self.get_size(
                        re.findall(r'<option value="(.*?)">', response.body)
                    )

                    self.data["formUrl"] = re.findall(' action="(.*?)"', response.body)[0]
                    self.data["formId"] = re.findall('name="formID" value="(.*?)"', response.body)[0]
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
                    body={
                        "formID": self.data["formId"],
                        "q1_name[first]": self.task.parent.first_name,
                        "q1_name[last]": self.task.parent.last_name,
                        "q2_emailmust": self.task.parent.email,
                        "q3_idNumber": self.id_numbers.generate(),
                        "q56_shoeSize56": self.data["sizeId"],
                        "dropdown_search": self.data["sizeId"],
                        "q22_doYou22": "YES",
                        "q5_doYou": "YES",
                        "q9_city": self.task.parent.city,
                        "q59_signature": self.task.parent.signature_image,
                        "g-recaptcha-response": self.captcha.solve(),
                        "recaptcha_visible": "1",
                        "website": "",
                        "event_id": f"{current_ts() * 1000}_{self.data['formId']}_{''.join(random.choices(string.ascii_letters + string.digits, k=7))}",
                        "validatedRequiredFieldIDs": '{"id_1":true,"id_2":true,"id_3":true,"id_56":true,"id_22":true,"id_5":true,"id_9":true,"id_59":true,"id_7":true}'
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
                if "entry has been submitted" in response.body:
                    break
                else:
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
