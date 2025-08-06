# -*- coding: utf-8 -*-
import random
import re
import json
from datetime import datetime, timezone
from common import http
from common.utils import sleep, current_ts, size_to_float, extract_domain
from tasks.common import webhooks, Logger, Browser
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, JSONError
from tasks.hooks import captcha
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
            "raffleId": task.input.raffle["url"].split("-")[-1].split("?")[0],
            "regionDomain": ".".join(extract_domain(task.input.raffle["url"]).split(".")[1:])
        }

        self.captcha = captcha.Solver(
            self.logger, "v3", f"raffles.{self.data['regionDomain']}"
        )

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
            size = size_data["size"].split(" -")[0]
            if self.task.input.size_range.fits(size_to_float(size)):
                sizes_in_range.append((
                    size, size_data["size"].split("- ")[1], size_data
                ))

        if sizes_in_range:
            return random.choice(sizes_in_range)
        else:
            return "", "", ""

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
                    f"https://raffles-resources.{DOMAIN}/raffles/raffles_{self.data['raffleId']}.js",
                    params={
                        "_": current_ts() * 1000
                    },
                    headers={
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "accept": "*/*",
                        "sec-fetch-site": "cross-site",
                        "sec-fetch-mode": "no-cors",
                        "sec-fetch-dest": "script",
                        "referer": f"https://raffles.{self.data['regionDomain']}/",
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
                    content = json.loads(re.findall(
                        r"var raffles = \[([\s|\S]*?)];", response.body
                    )[0])

                    if self.is_raffle_closed(content["raffle_end_date"]):
                        self.logger.error("Failed to enter raffle: Raffle closed")
                        return False

                    self.product.name = content["product_name"]
                    self.product.image = content["product_image"]
                    self.product.size, self.product.price, self.data["size"] = self.get_size([
                        size for category in content["size_categories"]
                        for size in category["group_skus"]
                    ])

                    self.data["siteCode"] = content["site_code"]
                    self.captcha.set_site_key(content["captcha"])
                    break
                except (JSONError, IndexError, KeyError, ValueError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 403:
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
            return self.submit_order()
        else:
            self.logger.error("Failed to enter raffle: No sizes in range")
            return False

    def submit_order(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    "https://nk7vfpucy5.execute-api.eu-west-1.amazonaws.com/prod/save_entry",
                    body={
                        "firstName": self.task.parent.first_name,
                        "rafflesID": self.data["raffleId"],
                        "lastName": self.task.parent.last_name,
                        "email": self.task.parent.email,
                        "paypalEmail": self.task.parent.paypal_email,
                        "mobile": self.task.parent.full_phone,
                        "dateofBirth": self.task.parent.format_date_of_birth("%d/%m/%Y"),
                        "shoeSize": self.data["size"]["sku_size_id"],
                        "shoeSizeSkuId": self.data["size"]["sku_id"],
                        "address1": self.task.parent.address,
                        "address2": self.task.parent.line_2,
                        "city": self.task.parent.city,
                        "county": self.task.parent.province,
                        "siteCode": self.data["siteCode"],
                        "postCode": self.task.parent.postcode,
                        "hostname": f"https://raffles.{self.data['regionDomain']}",
                        "sms_optin": 0,
                        "email_optin": 0,
                        "token": self.captcha.solve()
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "text/plain, */*; q=0.01",
                        "content-type": "application/json",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://raffles.{self.data['regionDomain']}",
                        "sec-fetch-site": "cross-site",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://raffles.{self.data['regionDomain']}/",
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
                    content = response.json()

                    if content["status"]:
                        self.data["checkoutToken"] = content["pre_auth"].split("preauth=")[1].split("&")[0]
                        break
                    else:
                        raise KeyError
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
                    f"https://raffles-checkout-api.{DOMAIN}/mini_checkout/siteCode/" + self.data["siteCode"],
                    body={
                        "pre_auth_token": self.data["checkoutToken"]
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "application/json, text/plain, */*",
                        "content-type": "application/json",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://raffles-checkout.{self.data['regionDomain']}",
                        "sec-fetch-site": "cross-site",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://raffles-checkout.{self.data['regionDomain']}/",
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
                    self.data["apiToken"] = response.json()["body"]["token"]
                    break
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
                response = self.session.post(
                    f"https://raffles-checkout-api.{DOMAIN}/payments/init_Payment",
                    body={
                        "paymentMethod": "PAYPAL"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "application/json, text/plain, */*",
                        "sec-ch-ua-platform": None,
                        "content-type": "application/json",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "x-api-token": self.data["apiToken"],
                        "origin": f"https://raffles-checkout.{self.data['regionDomain']}",
                        "sec-fetch-site": "cross-site",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://raffles-checkout.{self.data['regionDomain']}/",
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
                    self.data["paypalTransactionId"] = response.json()["body"]["token"]
                    break
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

        return self.handle_paypal()

    def handle_paypal(self):
        try:
            browser = Browser()
        except:
            self.logger.error("Failed to enter raffle: Browser error")
            return False

        try:
            browser.get(
                "https://www.paypal.com/checkoutnow",
                params={
                    "token": self.data["paypalTransactionId"],
                    "locale.x": "en_GB"
                }
            )

            content = json.loads(browser.await_response(
                re.compile('"state":"APPROVED"'), advanced=True
            ))["data"]["approveMemberPayment"]

            self.data["paypalUserId"] = content["buyer"]["userId"]
            self.data["paypalPaymentId"] = content["cart"]["paymentId"]
            self.data["returnUrl"] = content["cart"]["returnUrl"]["href"] if content["cart"]["returnUrl"] else ""
        except:
            self.logger.error("Failed to enter raffle: PayPal error")
            return False
        finally:
            browser.close()

        return self.submit_paypal()

    def submit_paypal(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://raffles-checkout-api.{DOMAIN}/payments/complete_Payment",
                    body={
                        "returnUrl": self.data["returnUrl"],
                        "billingToken": None,
                        "orderID": self.data["paypalTransactionId"],
                        "payerID": self.data["paypalUserId"],
                        "paymentToken": self.data["paypalTransactionId"],
                        "paymentID": self.data["paypalPaymentId"],
                        "paymentId": self.data["paypalPaymentId"],
                        "intent": "authorize",
                        "button_version": "4.0.37"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "application/json, text/plain, */*",
                        "sec-ch-ua-platform": None,
                        "content-type": "application/json",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "x-api-token": self.data["apiToken"],
                        "origin": f"https://raffles-checkout.{self.data['regionDomain']}",
                        "sec-fetch-site": "cross-site",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://raffles-checkout.{self.data['regionDomain']}/",
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
                    if response.json()["code"] == 200:
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
