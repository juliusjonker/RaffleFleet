# -*- coding: utf-8 -*-
import random
import hashlib
from common import http
from common.utils import sleep, current_ts
from tasks.common import Logger
from tasks.common.classes import Task
from tasks.common.errors import HTTPError, JSONError
from tasks.hooks import akamai_bmp
from .constants import NAME, DOMAIN, APP_NAME, APP_VERSION, APP_BUILD_NUMBER, API_KEY, API_SECRET, AKAMAI_BMP_VERSION, USER_AGENT, REGIONS


class GenerateAccount:
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

    def execute(self):
        status = "generated" if self.create_account() else "failed"

        self.task.manager.increment(
            status,
            task=self.task,
            parent=self.task.parent,
            proxy=self.session.proxy
        )

    def create_account(self):
        self.logger.info("Generating account...")

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
                    if not response.json()["exist"]:
                        break
                    else:
                        self.logger.error("Failed to generate account: Email already in use")
                        return False
                except (JSONError, KeyError):
                    self.logger.error("Failed to generate account"), self.delay()
                    error_count += 1
                    continue
            elif response.status in [400, 500]:
                self.logger.error("Failed to generate account"), self.delay()
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
                    f"https://{DOMAIN}/gw-api/v2/user",
                    body={
                        "email": self.task.parent.email,
                        "password": self.task.parent.password,
                        "membership_consent": True,
                        "dormant_period": "1y"
                    },
                    headers={
                        "content-type": "application/json; charset=UTF-8",
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
                    self.logger.error("Failed to generate account"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 409:
                self.logger.error("Failed to generate account: Email already in use")
                return False
            elif response.status in [400, 500]:
                self.logger.error("Failed to generate account"), self.delay()
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

        return self.add_address()

    def add_address(self):
        self.logger.info("Adding address...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.patch(
                    f"https://{DOMAIN}/gw-api/v2/user",
                    body={
                        "gender": "F" if self.task.parent.gender == "female" else "M",
                        "last_name": self.task.parent.last_name,
                        "date_of_birth": self.task.parent.format_date_of_birth("%Y-%m-%d"),
                        "first_name": self.task.parent.first_name
                    },
                    headers={
                        "x-app-info": f"platform/iOS version/{APP_VERSION}",
                        "user-agent": None,
                        "x-device-info": f"app/CONFIRMED; os/iOS; os-version/{self.akamai_bmp.device_os_version}; app-version/{APP_VERSION}; buildnumber/{APP_BUILD_NUMBER}; type/{self.akamai_bmp.device_name}; fingerprint/{self.akamai_bmp.device_id}",
                        "x-forter-mobile-uid": self.akamai_bmp.device_id,
                        "content-length": None,
                        "x-signature": self.generate_signature(),
                        "x-market": self.task.parent.country,
                        "authorization": "Bearer " + self.data["accessToken"],
                        "accept-language": None,
                        "accept": "application/hal+json",
                        "content-type": "application/json; charset=UTF-8",
                        "x-api-key": API_KEY,
                        "accept-encoding": "gzip, deflate, br"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                break
            elif response.status in [400, 500]:
                self.logger.error("Failed to add address"), self.delay()
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}/gw-api/v2/user/addresses",
                    body={
                        "first_name": self.task.parent.first_name,
                        "city": self.task.parent.city,
                        "address1": self.task.parent.address,
                        "postal_code": self.task.parent.postcode,
                        "last_name": self.task.parent.last_name,
                        "country_code": self.task.parent.country,
                        "type": "SHIPPING",
                        "address2": self.task.parent.line_2
                    },
                    headers={
                        "x-app-info": f"platform/iOS version/{APP_VERSION}",
                        "user-agent": None,
                        "x-device-info": f"app/CONFIRMED; os/iOS; os-version/{self.akamai_bmp.device_os_version}; app-version/{APP_VERSION}; buildnumber/{APP_BUILD_NUMBER}; type/{self.akamai_bmp.device_name}; fingerprint/{self.akamai_bmp.device_id}",
                        "x-forter-mobile-uid": self.akamai_bmp.device_id,
                        "content-length": None,
                        "x-signature": self.generate_signature(),
                        "x-market": self.task.parent.country,
                        "authorization": "Bearer " + self.data["accessToken"],
                        "accept-language": None,
                        "accept": "application/hal+json",
                        "content-type": "application/json; charset=UTF-8",
                        "x-api-key": API_KEY,
                        "accept-encoding": "gzip, deflate, br"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                break
            elif response.status in [400, 500]:
                self.logger.error("Failed to add address"), self.delay()
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

        self.logger.success("Successfully generated account")
        return True
