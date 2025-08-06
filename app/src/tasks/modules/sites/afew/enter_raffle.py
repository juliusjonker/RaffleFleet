# -*- coding: utf-8 -*-
import random
import re
import html
from common import http
from common.utils import sleep, size_to_float, extract_domain
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
        self.data = {
            "regionDomain": extract_domain(task.input.raffle["url"])
        }

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
            size = size_data["title"]
            if self.task.input.size_range.fits(size_to_float(size)):
                sizes_in_range.append((
                    size, size_data["id"]
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
                    self.product.price = "€ " + re.findall('property="product:price:amount" content="(.*?)"', response.body)[0]
                    self.product.image = re.findall('<meta property="og:image" content="(.*?)">', response.body)[2]
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
                    f"https://{DOMAIN}" + self.task.input.raffle["url"].split(self.data["regionDomain"])[1].split("?")[0] + ".json",
                    headers={
                        "sec-ch-ua": None,
                        "accept": "application/json, text/javascript, */*; q=0.01",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{self.data['regionDomain']}",
                        "sec-fetch-site": "same-site",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{self.data['regionDomain']}/",
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
                    self.product.size, self.data["sizeId"] = self.get_size(
                        response.json()["product"]["variants"]
                    )
                    break
                except (JSONError, KeyError, ValueError):
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
                response = self.session.get(
                    f"https://{DOMAIN}/cart/{self.data['sizeId']}:1",
                    params={
                        "locale": "en",
                        "attributes[locale]": "en",
                        "attributes[instagram]": self.task.parent.instagram,
                        "utm_source": ""
                    },
                    headers={
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "sec-fetch-site": "same-site",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
                        "referer": f"https://{self.data['regionDomain']}/",
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
                    self.data["checkoutPath"] = re.findall('class="edit_checkout" novalidate="novalidate" action="(.*?)"', response.body)[0]
                    self.data["authenticityToken"] = re.findall('name="authenticity_token" value="(.*?)"', response.body)[0]
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}" + self.data["checkoutPath"],
                    body={
                        "_method": "patch",
                        "authenticity_token": self.data["authenticityToken"],
                        "previous_step": "contact_information",
                        "step": "shipping_method",
                        "checkout[email]": self.task.parent.email,
                        "checkout[attributes][locale]": "en",
                        "checkout[attributes][instagram]": self.task.parent.instagram,
                        "checkout[shipping_address][first_name]": self.task.parent.first_name,
                        "checkout[shipping_address][last_name]": self.task.parent.last_name,
                        "checkout[shipping_address][company]": "",
                        "checkout[shipping_address][address1]": self.task.parent.address,
                        "checkout[shipping_address][address2]": self.task.parent.line_2,
                        "checkout[shipping_address][city]": self.task.parent.city,
                        "checkout[shipping_address][country]": self.task.parent.country_name,
                        "checkout[shipping_address][province]": self.task.parent.province,
                        "checkout[shipping_address][zip]": self.task.parent.postcode,
                        "checkout[shipping_address][phone]": self.task.parent.full_phone,
                        "checkout[remember_me]": "0",
                        "checkout[client_details][browser_width]": "1263",
                        "checkout[client_details][browser_height]": "569",
                        "checkout[client_details][javascript_enabled]": "1",
                        "checkout[client_details][color_depth]": "24",
                        "checkout[client_details][java_enabled]": "false",
                        "checkout[client_details][browser_tz]": "-60"
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
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "sec-fetch-site": "same-origin",
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
                    self.data["authenticityToken"] = re.findall('name="authenticity_token" value="(.*?)"', response.body)[0]
                    self.data["shippingMethod"] = re.findall('class="radio-wrapper" data-shipping-method="(.*?)"', response.body)[0]
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}" + self.data["checkoutPath"],
                    body={
                        "_method": "patch",
                        "authenticity_token": self.data["authenticityToken"],
                        "previous_step": "shipping_method",
                        "step": "payment_method",
                        "checkout[shipping_rate][id]": self.data["shippingMethod"],
                        "checkout[client_details][browser_width]": "1263",
                        "checkout[client_details][browser_height]": "569",
                        "checkout[client_details][javascript_enabled]": "1",
                        "checkout[client_details][color_depth]": "24",
                        "checkout[client_details][java_enabled]": "false",
                        "checkout[client_details][browser_tz]": "-60"
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
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "sec-fetch-site": "same-origin",
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
                    self.data["authenticityToken"] = re.findall('name="authenticity_token" value="(.*?)"', response.body)[0]
                    self.data["paymentGateway"] = re.findall('data-select-gateway="(.*?)"', response.body)[0]
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}" + self.data["checkoutPath"],
                    body={
                        "_method": "patch",
                        "authenticity_token": self.data["authenticityToken"],
                        "previous_step": "payment_method",
                        "step": "review",
                        "s": "",
                        "checkout[payment_gateway]": self.data["paymentGateway"],
                        "checkout[different_billing_address]": "false",
                        "checkout[client_details][browser_width]": "1263",
                        "checkout[client_details][browser_height]": "569",
                        "checkout[client_details][javascript_enabled]": "1",
                        "checkout[client_details][color_depth]": "24",
                        "checkout[client_details][java_enabled]": "false",
                        "checkout[client_details][browser_tz]": "-60"
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
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "sec-fetch-site": "same-origin",
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
                    self.data["authenticityToken"] = re.findall('name="authenticity_token" value="(.*?)"', response.body)[0]
                    self.data["totalPrice"] = re.findall('id="checkout_total_price" value="(.*?)"', response.body)[0]
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}" + self.data["checkoutPath"],
                    body={
                        "_method": "patch",
                        "authenticity_token": self.data["authenticityToken"],
                        "checkout[total_price]": self.data["totalPrice"],
                        "complete": "1",
                        "checkout[client_details][browser_width]": "1263",
                        "checkout[client_details][browser_height]": "569",
                        "checkout[client_details][javascript_enabled]": "1",
                        "checkout[client_details][color_depth]": "24",
                        "checkout[client_details][java_enabled]": "false",
                        "checkout[client_details][browser_tz]": "-60"
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
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "sec-fetch-site": "same-origin",
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
                    self.data["processingDelay"] = int(re.findall(r"var refreshPeriod = (.*?) \* 1000;", response.body)[0])
                    self.data["processingParams"] = re.findall('var toParam =  "(.*?)";', response.body)[0]  # NOQA
                    break
                except (IndexError, ValueError):
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

        sleep(self.data["processingDelay"])

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}{self.data['checkoutPath']}?{self.data['processingParams']}",
                    headers={
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "navigate",
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
                if "/thank_you" in response.url:
                    break
                else:
                    sleep(self.data["processingDelay"])
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
