# -*- coding: utf-8 -*-
import random
import re
import html
from common import http
from common.utils import sleep, size_to_float
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, JSONError
from tasks.hooks import captcha
from .constants import NAME, DOMAIN, RECAPTCHA_SITE_KEY


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
            self.logger, "v3", DOMAIN, RECAPTCHA_SITE_KEY, metadata={
                "action": "contactform"
            }
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
        for size in sizes:
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
                    self.product.name = html.unescape(re.findall('<meta property="og:title" content="RAFFLE (.*?)" />', response.body)[0])
                    self.product.image = re.findall('<img loading="lazy" width=".*?" height=".*?" src="(.*?)"', response.body)[0]
                    self.product.size = self.get_size(
                        re.findall('<option value="(.*?)">', response.body)
                    )

                    self.data["formId"] = re.findall('name="_wpcf7" value="(.*?)"', response.body)[0]
                    self.data["version"] = re.findall('name="_wpcf7_version" value="(.*?)"', response.body)[0]
                    self.data["locale"] = re.findall('name="_wpcf7_locale" value="(.*?)"', response.body)[0]
                    self.data["unitTag"] = re.findall('name="_wpcf7_unit_tag" value="(.*?)"', response.body)[0]
                    self.data["containerPost"] = re.findall('name="_wpcf7_container_post" value="(.*?)"', response.body)[0]
                    self.data["raffleTag"] = re.findall('name="raffle-tag" value="(.*?)"', response.body)[0]
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
                    f"https://{DOMAIN}/wp-admin/admin-ajax.php",
                    body={
                        "name": self.task.parent.full_name,
                        "email": self.task.parent.email,
                        "custom_details[talla_pie]": self.product.size,
                        "tags[]": self.data["raffleTag"],
                        "action": "SMcontactUpsert",
                        "honeypot": ""
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
                        "referer": self.task.input.raffle["url"],
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                if '"success":true' in response.body:
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}/wp-json/contact-form-7/v1/contact-forms/{self.data['formId']}/feedback",
                    body={
                        "_wpcf7": self.data["formId"],
                        "_wpcf7_version": self.data["version"],
                        "_wpcf7_locale": self.data["locale"],
                        "_wpcf7_unit_tag": self.data["unitTag"],
                        "_wpcf7_container_post": self.data["containerPost"],
                        "_wpcf7_posted_data_hash": "",
                        "_wpcf7_recaptcha_response": self.captcha.solve(),
                        "your-name": self.task.parent.first_name,
                        "lastname": self.task.parent.last_name,
                        "email": self.task.parent.email,
                        "acceptance-737": "1",
                        "talla": self.product.size,
                        "honeypot-992": "",
                        "raffle-tag": self.data["raffleTag"]
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "application/json, */*;q=0.1",
                        "content-type": "multipart/form-data",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": self.task.input.raffle["url"],
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
                    if response.json()["status"] == "mail_sent":
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
