# -*- coding: utf-8 -*-
import random
import hashlib
from common import http
from common.utils import sleep, current_ts
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, JSONError
from tasks.hooks import akamai_bmp
from .constants import NAME, DOMAIN, APP_NAME, APP_VERSION, APP_BUILD_NUMBER, API_KEY, API_SECRET, AKAMAI_BMP_VERSION, USER_AGENT, REGIONS


class CheckOrders:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = Logger(
            NAME, task.id, task.formatted_parent_id
        )

        self.session = http.Session(
            client="iosConfirmed",
            proxy=task.proxies.get(),
            user_agent=USER_AGENT,
            accept_language=REGIONS.get(task.parent.country, "en-GB")
        )

        self.akamai_bmp = akamai_bmp.Solver(
            self.logger, APP_NAME, AKAMAI_BMP_VERSION
        )

        self.product = Product(
            name=task.input.raffle["productName"]
        )
        self.data = {}

    @staticmethod
    def delay():
        sleep(random.randint(2000, 3000) / 1000)

    def switch_proxy(self):
        self.session.set_proxy(
            self.task.proxies.get()
        )

    @staticmethod
    def generate_signature():
        sha256 = hashlib.sha256()
        sha256.update((
            API_KEY + API_SECRET + str(current_ts())
        ).encode())
        return sha256.hexdigest().upper()

    def get_order(self, orders):
        for order in orders:
            product = order["product_groups"][0]["order_items"][0]
            if product["product_id"] != self.task.input.raffle["id"]:
                continue

            self.product.price = order["total_view"][0]["display_value"]
            self.product.image = product["_links"]["thumbnail"]["href"]
            self.product.size = product["size"]

            self.data["orderNumber"] = order["order_number"]
            return "found"
        else:
            return "empty"

    def execute(self):
        status = self.data["status"] if self.log_in() else "failed"

        if status == "found":
            webhooks.Win(
                NAME, self.product, self.task.parent, self.session.proxy,
                order_number=self.data["orderNumber"]
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

        self.data["sensorData"] = self.akamai_bmp.solve()

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/gw-api/v2/user/lookup",
                    params={
                        "id": self.task.parent.email
                    },
                    headers={
                        "accept": "application/hal+json",
                        "x-device-info": f"app/CONFIRMED; os/iOS; os-version/{self.akamai_bmp.device_os_version}; app-version/{APP_VERSION}; buildnumber/{APP_BUILD_NUMBER}; type/{self.akamai_bmp.device_name}; fingerprint/{self.akamai_bmp.device_id}",
                        "x-market": self.task.parent.country,
                        "x-signature": self.generate_signature(),
                        "x-acf-sensor-data": self.data["sensorData"],
                        "x-api-key": API_KEY,
                        "accept-language": None,
                        "accept-encoding": "gzip, deflate, br",
                        "user-agent": None,
                        "x-app-info": f"platform/iOS version/{APP_VERSION}",
                        "x-forter-mobile-uid": self.akamai_bmp.device_id
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    if response.json()["exist"]:
                        break
                    else:
                        self.logger.error("Failed to log in: Invalid credentials")
                        return False
                except (JSONError, KeyError):
                    self.logger.error("Failed to log in"), self.delay()
                    error_count += 1
                    continue
            elif response.status in [400, 500]:
                self.logger.error("Failed to log in"), self.delay()
                error_count += 1
                continue
            elif response.status == 403:
                self.logger.error((
                    "Request failed: Akamai block", "switching proxy"
                )), self.delay()
                self.switch_proxy()
                error_count += 1
                if error_count < self.max_retries:
                    self.data["sensorData"] = self.akamai_bmp.solve()
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

        self.delay()

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}/gw-api/v2/token",
                    body={
                        "grant_type": "password",
                        "username": self.task.parent.email,
                        "password": self.task.parent.password
                    },
                    headers={
                        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "accept": "application/hal+json",
                        "x-device-info": f"app/CONFIRMED; os/iOS; os-version/{self.akamai_bmp.device_os_version}; app-version/{APP_VERSION}; buildnumber/{APP_BUILD_NUMBER}; type/{self.akamai_bmp.device_name}; fingerprint/{self.akamai_bmp.device_id}",
                        "x-market": self.task.parent.country,
                        "x-signature": self.generate_signature(),
                        "x-acf-sensor-data": self.data["sensorData"],
                        "x-api-key": API_KEY,
                        "accept-language": None,
                        "accept-encoding": "gzip, deflate, br",
                        "content-length": None,
                        "user-agent": None,
                        "x-app-info": f"platform/iOS version/{APP_VERSION}",
                        "x-forter-mobile-uid": self.akamai_bmp.device_id
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
            elif response.status in [400, 500]:
                self.logger.error("Failed to log in"), self.delay()
                error_count += 1
                continue
            elif response.status == 403:
                self.logger.error((
                    "Request failed: Akamai block", "switching proxy"
                )), self.delay()
                self.switch_proxy()
                error_count += 1
                if error_count < self.max_retries:
                    self.data["sensorData"] = self.akamai_bmp.solve()
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
        return self.fetch_orders()

    def fetch_orders(self):
        self.logger.info("Checking orders...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/gw-api/v2/orders",
                    params={
                        "page": "0",
                        "limit": "0"
                    },
                    headers={
                        "accept": "application/hal+json",
                        "x-device-info": f"app/CONFIRMED; os/iOS; os-version/{self.akamai_bmp.device_os_version}; app-version/{APP_VERSION}; buildnumber/{APP_BUILD_NUMBER}; type/{self.akamai_bmp.device_name}; fingerprint/{self.akamai_bmp.device_id}",
                        "x-market": self.task.parent.country,
                        "authorization": "Bearer " + self.data["accessToken"],
                        "x-signature": self.generate_signature(),
                        "accept-language": None,
                        "x-api-key": API_KEY,
                        "x-acf-sensor-data": self.data["sensorData"],
                        "accept-encoding": "gzip, deflate, br",
                        "user-agent": None,
                        "x-app-info": f"platform/iOS version/{APP_VERSION}",
                        "x-forter-mobile-uid": self.akamai_bmp.device_id
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["status"] = self.get_order(
                        response.json()["_embedded"]["orders"]
                    )
                    break
                except (JSONError, KeyError, IndexError):
                    self.logger.error("Failed to check orders"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 403:
                self.logger.error((
                    "Request failed: Akamai block", "switching proxy"
                )), self.delay()
                self.switch_proxy()
                error_count += 1
                if error_count < self.max_retries:
                    self.data["sensorData"] = self.akamai_bmp.solve()
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

        if self.data["status"] == "found":
            self.logger.success("Checked orders: Found")
            return True
        else:
            self.logger.info("Checked orders: Empty")
            return True
