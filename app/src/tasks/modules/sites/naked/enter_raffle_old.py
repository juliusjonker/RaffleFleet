# -*- coding: utf-8 -*-
import random
import re
import html
from common.utils import sleep
from tasks.common import webhooks
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, CloudflareError
from tasks.hooks import captcha
from .constants import NAME, DOMAIN, RAFFLE_DOMAIN, HCAPTCHA_SITE_KEY


class EnterRaffleOld:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = task.inheritance.logger
        self.session = task.inheritance.session

        self.captcha = captcha.Solver(
            self.logger, "h", DOMAIN, HCAPTCHA_SITE_KEY
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
                        "cache-control": "max-age=0",
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
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
                try:
                    self.product.name = html.unescape(re.findall('property="og:title" content="(.*?)"', response.body)[0]).split(" |")[0]
                    self.product.price = re.findall('property="og:price" content="(.*?)"', response.body)[0]
                    self.product.image = re.findall('property="og:image" content="(.*?)"', response.body)[0]

                    self.data["raffleUrl"] = re.findall("DON'T KNOW YET", response.body)[0]
                    break
                except IndexError:
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
                    self.data["raffleUrl"],
                    headers={
                        "cache-control": "max-age=0",
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "sec-fetch-site": "cross-site",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
                        "referer": self.task.input.raffle["url"],
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
                    self.data["tags"] = re.findall('name="tags\[]" type="hidden" value="(.*?)"', response.body)[0]
                    self.data["token"] = re.findall('name="token" type="hidden" value="(.*?)"', response.body)[0]
                    self.data["ip"] = re.findall('name="fields\[SignupSource\.ip]" type="hidden" value="(.*?)"', response.body)[0]
                    self.data["userAgent"] = re.findall('name="fields\[SignupSource\.useragent]" type="hidden" value="(.*?)"', response.body)[0]
                    self.data["language"] = re.findall('name="language" type="hidden" value="(.*?)"', response.body)[0]
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

        return self.enter_raffle()

    def enter_raffle(self):
        error_count = 0
        while error_count < self.max_retries:
            captcha_token = self.captcha.solve()

            try:
                response = self.session.post(
                    f"https://{RAFFLE_DOMAIN}/raffle/naked.php",
                    body={
                        "tags[]": self.data["tags"],
                        "token": self.data["token"],
                        "rule_email": self.task.parent.email,
                        "fields[Raffle.Instagram Handle]": self.task.parent.instagram,
                        "fields[Raffle.Phone Number]": self.task.parent.full_phone,
                        "fields[Raffle.First Name]": self.task.parent.first_name,
                        "fields[Raffle.Last Name]": self.task.parent.last_name,
                        "fields[Raffle.Shipping Address]": self.task.parent.address,
                        "fields[Raffle.Postal Code]": self.task.parent.postcode,
                        "fields[Raffle.City]": self.task.parent.city,
                        "fields[Raffle.Country]": self.task.parent.country,
                        "fields[SignupSource.ip]": self.data["ip"],
                        "fields[SignupSource.useragent]": self.data["userAgent"],
                        "language": self.data["language"],
                        "g-recaptcha-response": captcha_token,
                        "h-captcha-response": captcha_token
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
                        "sec-fetch-site": "cross-site",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
                        "referer": f"https://{DOMAIN}/",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, CloudflareError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                if "You are now registered!" in response.body:
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
