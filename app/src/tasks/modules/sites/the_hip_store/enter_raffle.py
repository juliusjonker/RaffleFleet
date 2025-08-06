# -*- coding: utf-8 -*-
import random
import re
from datetime import datetime, timezone
from common import http
from common.utils import sleep, current_ts, size_to_float
from tasks.common import webhooks, Logger, Browser
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, JSONError
from tasks.hooks import adyen, captcha
from .constants import NAME, DOMAIN, STORE_NAME, URL_PARAMS, USER_AGENT, ADYEN_VERSION, ADYEN_PUBLIC_KEY, RECAPTCHA_SITE_KEY


class EnterRaffle:
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

        self.adyen = adyen.Encryptor(
            ADYEN_VERSION, ADYEN_PUBLIC_KEY
        )
        self.captcha = captcha.Solver(
            self.logger, "v3", DOMAIN, RECAPTCHA_SITE_KEY, metadata={
                "action": "PreAuth_Create"
            }
        )

        self.product = Product()
        self.data = {
            "raffleId": task.input.raffle["url"].split("/")[-1].split("?")[0],
            "googleClientId": f"{random.randint(10000000, 1000000000)}.{current_ts()}"
        }

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
            close_datetime, "%Y-%m-%dT%H:%M:%S.%f%z"
        ).astimezone(timezone.utc) < datetime.now(timezone.utc)

    def get_size(self, sizes):
        sizes_in_range = []
        for size_data in sizes:
            size = size_data["name"].split(" |")[0]
            if self.task.input.size_range.fits(size_to_float(size)):
                sizes_in_range.append((
                    size, size_data["optionID"]
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
                    content = response.json()["customer"]

                    self.data["userId"] = content["userID"]
                    self.data["customer"] = content["personal"]
                    self.data["billing"] = content["billing"]
                    self.data["delivery"] = content["delivery"]
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
        return self.fetch_raffle()

    def fetch_raffle(self):
        self.logger.info("Entering raffle...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/stores/{STORE_NAME}/products/{self.data['raffleId']}/details",
                    params=URL_PARAMS,
                    headers={
                        "Origin": "https://launches.thehipstore.co.uk",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Accept": "*/*",
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
                    content = response.json()

                    if content["status"] != "available" or self.is_raffle_closed(content["launchDate"]):
                        self.logger.error("Failed to enter raffle: Raffle closed")
                        return False

                    self.product.name = f"{content['name']} {content['subTitle']}"
                    self.product.price = "£ " + content["price"]["amount"]
                    self.product.image = content["mainImage"]["original"]
                    self.product.size, self.data["sizeId"] = self.get_size(
                        content["options"]
                    )
                    break
                except (JSONError, KeyError, ValueError):
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
            return self.fetch_shipping_method()
        else:
            self.logger.error("Failed to enter raffle: No sizes in range")
            return False

    def fetch_shipping_method(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/stores/{STORE_NAME}/deliverymethods",
                    params={
                        "locale": self.task.parent.country.lower() if self.task.parent.is_address_loaded else self.data["delivery"]["locale"],
                        **URL_PARAMS
                    },
                    headers={
                        "Origin": "https://launches.thehipstore.co.uk",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Accept": "*/*",
                        "User-Agent": None,
                        "originalhost": DOMAIN,
                        "Accept-Language": None,
                        "Referer": f"https://launches.thehipstore.co.uk/"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    for method in response.json()["deliverytypes"][0]["options"]:
                        name = method["name"].lower()
                        if "standard" in name and "free" not in name:
                            self.data["shippingMethod"] = method
                            break
                    else:
                        raise KeyError

                    break
                except (JSONError, KeyError, IndexError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 400:
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

        return self.submit_order()

    def submit_order(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}/stores/{STORE_NAME}/preAuthorise/order",
                    params={
                        "userID": self.data["userId"],
                        **URL_PARAMS
                    },
                    body={
                        "customer": {
                            "isPrefilled": False,
                            "firstName": self.task.parent.first_name or self.data["customer"]["firstName"],
                            "lastName": self.task.parent.last_name or self.data["customer"]["lastName"],
                            "email": self.task.parent.email,
                            "phone": self.task.parent.full_phone or self.data["customer"]["phone"]
                        },
                        "delivery": {
                            "isPrefilled": False,
                            "firstName": self.task.parent.first_name or self.data["delivery"]["firstName"],
                            "lastName": self.task.parent.last_name or self.data["delivery"]["lastName"],
                            "postcode": self.task.parent.postcode if self.task.parent.is_address_loaded else self.data["delivery"]["postcode"],
                            "address1": self.task.parent.address if self.task.parent.is_address_loaded else self.data["delivery"]["address1"],
                            "address2": self.task.parent.line_2 if self.task.parent.is_address_loaded else self.data["delivery"]["address2"],
                            "town": self.task.parent.city if self.task.parent.is_address_loaded else self.data["delivery"]["town"],
                            "county": self.task.parent.province if self.task.parent.is_address_loaded else self.data["delivery"]["county"],
                            "locale": self.task.parent.country.lower() if self.task.parent.is_address_loaded else self.data["delivery"]["locale"]
                        },
                        "billing": {
                            "isPrefilled": False,
                            "firstName": self.task.parent.first_name or self.data["billing"]["firstName"],
                            "lastName": self.task.parent.last_name or self.data["billing"]["lastName"],
                            "postcode": self.task.parent.postcode if self.task.parent.is_address_loaded else self.data["billing"]["postcode"],
                            "address1": self.task.parent.address if self.task.parent.is_address_loaded else self.data["billing"]["address1"],
                            "address2": self.task.parent.line_2 if self.task.parent.is_address_loaded else self.data["billing"]["address2"],
                            "town": self.task.parent.city if self.task.parent.is_address_loaded else self.data["billing"]["town"],
                            "county": self.task.parent.province if self.task.parent.is_address_loaded else self.data["billing"]["county"],
                            "locale": self.task.parent.country.lower() if self.task.parent.is_address_loaded else self.data["billing"]["locale"]
                        },
                        "deliveryMethod": {
                            "isPrefilled": False,
                            "type": "delivery",
                            **self.data["shippingMethod"]
                        },
                        "optionID": self.data["sizeId"],
                        "productID": self.data["raffleId"],
                        "verification": self.captcha.solve(),
                        "googleClientID": self.data["googleClientId"]
                    },
                    headers={
                        "Accept": "*/*",
                        "Authorization": self.data["accessToken"],
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
                    self.data["orderId"] = response.json()["orderID"]
                    break
                except (JSONError, KeyError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status in [400, 409, 500]:
                try:
                    if response.json()["errorInfo"] == "You have already entered this raffle.":
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.put(
                    f"https://{DOMAIN}/stores/{STORE_NAME}/preAuthorise/payment/{self.data['orderId']}",
                    params={
                        "type": "CARD",
                        **URL_PARAMS
                    },
                    body={
                        "encryptedData": {
                            "encryptedCardNumber": self.adyen.encrypt({"number": self.task.parent.card_number}),
                            "encryptedExpiryMonth": self.adyen.encrypt({"expiryMonth": self.task.parent.card_month}),
                            "encryptedExpiryYear": self.adyen.encrypt({"expiryYear": self.task.parent.card_year}),
                            "encryptedSecurityCode": self.adyen.encrypt({"cvc": self.task.parent.card_cvc}),
                            "holderName": self.task.parent.full_name
                        }
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
                    content = response.json()

                    if content.get("successCode") == "order-complete":
                        break
                    else:
                        self.data["3ds"] = {
                            "url": content["redirectUrl"],
                            "md": content["md"],
                            "paReq": content["paReq"]
                        }
                        break
                except (JSONError, KeyError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status in [400, 500]:
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

        if self.data.get("3ds"):
            return self.handle_3ds()
        else:
            self.logger.success("Successfully entered raffle")
            return True

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
                    "MD": self.data["3ds"]["md"],
                    "PaReq": self.data["3ds"]["paReq"],
                    "TermUrl": "data:text/html,"
                }
            )

            body = browser.await_response(re.compile(
                '<input type="hidden" name="PaRes" value="(.*?)"'
            ))

            self.data["3ds"]["md"] = re.findall('name="MD" value="(.*?)"', body)[0]
            self.data["3ds"]["paRes"] = re.findall('name="PaRes" value="(.*?)"', body)[0]
        except:
            self.logger.error("Failed to enter raffle: 3DS error")
            return False
        finally:
            browser.close()

        return self.submit_3ds()

    def submit_3ds(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}/stores/{STORE_NAME}/preAuthorise/{self.data['orderId']}/payment/3dsecure",
                    body={
                        "MD": self.data["3ds"]["md"],
                        "PaRes": self.data["3ds"]["paRes"]
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": "https://checkoutshopper-live.adyen.com",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "User-Agent": None,
                        "Referer": "https://checkoutshopper-live.adyen.com/",
                        "Content-Length": None,
                        "Accept-Language": None
                    }
                )
            except HTTPError as error:
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
                response = self.session.put(
                    f"https://{DOMAIN}/stores/{STORE_NAME}/preAuthorise/{self.data['orderId']}/payment/3dsecure",
                    params=URL_PARAMS,
                    body={},
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
                    if response.json()["successCode"] == "payment-complete":
                        break
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status in [500, 502]:
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
