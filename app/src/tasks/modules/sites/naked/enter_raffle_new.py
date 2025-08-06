# -*- coding: utf-8 -*-
import random
import re
import html
from common.utils import sleep, size_to_float
from tasks.common import webhooks, Browser
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, CloudflareError, JSONError
from .constants import NAME, DOMAIN


class EnterRaffleNew:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = task.inheritance.logger
        self.session = task.inheritance.session

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
            size = re.findall('data-target="#raffle-form-select">\n(.*?)\n', size_data)[0]
            if self.task.input.size_range.fits(size_to_float(size)):
                sizes_in_range.append((
                    size, re.findall('data-value="(.*?)"', size_data)[0]
                ))

        if sizes_in_range:
            return random.choice(sizes_in_range)
        else:
            return "", ""

    def execute(self):
        status = "entered" if self.log_in() else "failed"

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

    def log_in(self):
        self.logger.info("Logging in...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/en/auth/view",
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
                    self.data["antiCsrfToken"] = re.findall('name="_AntiCsrfToken" value="(.*?)"', response.body)[0]
                    break
                except IndexError:
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}/en/auth/submit",
                    body={
                        "_AntiCsrfToken": self.data["antiCsrfToken"],
                        "action": "Login",
                        "email": self.task.parent.email,
                        "password": self.task.parent.password,
                        "g-recaptcha-response": ""
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "content-type": "multipart/form-data",
                        "x-requested-with": "XMLHttpRequest",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "accept": "*/*",
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{DOMAIN}/en/auth/view",
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
                    if response.json()["Response"]["Success"]:
                        break
                    else:
                        self.logger.error("Failed to log in: Invalid credentials")
                        return False
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
        return self.fetch_raffle()

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
                if "<h2>You have succefully signed up to the raffle!</h2>" in response.body:
                    self.logger.error("Failed to enter raffle: Already entered")
                    return False

                try:
                    self.product.name = html.unescape(re.findall('property="og:title" content="(.*?)"', response.body)[0]).split(" |")[0]
                    self.product.price = re.findall('property="og:price" content="(.*?)"', response.body)[0]
                    self.product.image = re.findall('property="og:image" content="(.*?)"', response.body)[0]
                    self.product.size, self.data["sizeId"] = self.get_size(
                        re.findall(r'<a href="#" class="dropdown-item"([\s|\S]*?)</a>', response.body)
                    )

                    self.data["raffleId"] = re.findall('name="raffleId" value="(.*?)"', response.body)[0]
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
                    f"https://{DOMAIN}/en/raffle/signup",
                    body={
                        "raffleId": self.data["raffleId"],
                        "productId": self.data["sizeId"],
                        "raffleFormCountryShipping": self.task.parent.country,
                        "firstName": self.task.parent.first_name,
                        "lastName": self.task.parent.last_name,
                        "addressLine2": self.task.parent.address,
                        "addressLine3": "",
                        "postalCode": self.task.parent.postcode,
                        "city": self.task.parent.city,
                        "phoneNumber": self.task.parent.full_phone,
                        "billing-address-toggle": "true",
                        "languagecode": "en",
                        "email": self.task.parent.email,
                        "termsAccepted": "on"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "content-type": "multipart/form-data",
                        "x-requested-with": "XMLHttpRequest",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "accept": "*/*",
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
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
                    content = response.json()["Response"]

                    self.data["paymentUrl"] = re.findall('class="stored-card-form" action="(.*?)"', content)[0]
                    self.data["paymentHash"] = re.findall("name='hash' value='(.*?)'", content)[0]
                    break
                except (JSONError, KeyError, IndexError):
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
                    self.data["paymentUrl"],
                    body={
                        "store_card": "true",
                        "subscription_quantity": "1",
                        "hash": self.data["paymentHash"],
                        "card_holder": self.task.parent.full_name,
                        "card_number": self.task.parent.card_number,
                        "card_type": self.task.parent.card_type.upper(),
                        "card_expiry": self.task.parent.card_month + self.task.parent.card_year[2:],
                        "expDate": f"{self.task.parent.card_month} / {self.task.parent.card_year[2:]}",
                        "card_cvv": self.task.parent.card_cvc
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
                        "sec-fetch-site": "cross-site",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "iframe",
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
                try:
                    self.data["3ds"] = {
                        "url": re.findall('id="method-data-processing-form" action="(.*?)"', response.body)[0],
                        "methodData": re.findall('name="threeDSMethodData" value="(.*?)"', response.body)[0]
                    }
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

        return self.handle_3ds()

    def handle_3ds(self):
        try:
            browser = Browser()
        except:
            self.logger.error("Failed to enter raffle: Browser error")
            return False

        try:
            browser.post(
                self.data["3ds"]["url"],
                body={
                    "threeDSMethodData": self.data["3ds"]["methodData"],
                    "browser_screen_height": "720",
                    "browser_screen_width": "1280",
                    "browser_color_depth": "24",
                    "browser_tz": "-420",
                    "browser_javascript_enabled": "true",
                    "browser_java_enabled": "false"
                }
            )

            body = browser.await_response(re.compile(
                "/mondido/success|/mondido/error"
            ))
        except:
            self.logger.error("Failed to enter raffle: 3DS error")
            return False
        finally:
            browser.close()

        if "/mondido/success" in body:
            self.logger.success("Successfully entered raffle")
            return True
        else:
            self.logger.error("Failed to enter raffle")
            return False
