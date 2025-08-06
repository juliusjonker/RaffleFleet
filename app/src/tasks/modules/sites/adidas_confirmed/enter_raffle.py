# -*- coding: utf-8 -*-
import random
import json
import re
import hashlib
import base64
from datetime import datetime, timezone
from common import http
from common.utils import sleep, current_ts, utc_to_local, size_to_float
from tasks.common import webhooks, Logger, Browser
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, JSONError
from tasks.hooks import adyen, akamai_bmp
from .constants import NAME, DOMAIN, APP_NAME, APP_VERSION, APP_BUILD_NUMBER, API_KEY, API_SECRET, AKAMAI_BMP_VERSION, USER_AGENT, ADYEN_VERSION, ADYEN_PUBLIC_KEY, REGIONS, CARD_TYPES


class EnterRaffle:
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
        self.adyen = adyen.Encryptor(
            ADYEN_VERSION, ADYEN_PUBLIC_KEY, string_prefix="adyenan"
        )

        self.product = Product()
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

    def generate_payment_body(self):
        if self.data["paymentId"]:
            return {
                "amount": self.data["totalPrice"],
                "security_check_info": {
                    "cvv": self.task.parent.card_cvc
                },
                "payment_info_reference_id": self.data["paymentId"],
                "payment_card_type": CARD_TYPES[self.task.parent.card_type].upper(),
                "event_id": self.data["eventId"],
                "currency": self.data["currency"],
                "payment_method_id": "CREDIT_CARD"
            }
        else:
            return {
                "amount": self.data["totalPrice"],
                "payment_card_encrypted": self.adyen.encrypt({
                    "holderName": self.task.parent.full_name,
                    "number": self.task.parent.card_number,
                    "expiryMonth": self.task.parent.card_month,
                    "expiryYear": self.task.parent.card_year,
                    "cvc": self.task.parent.card_cvc
                }),
                "payment_card_type": CARD_TYPES[self.task.parent.card_type],
                "event_id": self.data["eventId"],
                "save_payment_card": True,
                "currency": self.data["currency"],
                "payment_method_id": "CREDIT_CARD"
            }

    def wait_for_release(self):
        if self.data["eventStartTime"] > datetime.now(timezone.utc):
            self.logger.info(
                "Waiting for release: " +
                utc_to_local(self.data["eventStartTime"]).strftime("%H:%M")
            )

            sleep((
                self.data["eventStartTime"] - datetime.now(timezone.utc)
            ).total_seconds())

            self.logger.info("Entering raffle...")

    def get_size(self, sizes):
        sizes_in_range = []
        for size_data in sizes:
            if not size_data["orderable"]:
                continue

            size = size_data["size"]
            if self.task.input.size_range.fits(size_to_float(size)):
                sizes_in_range.append((
                    size, size_data["variation_product_id"]
                ))

        if sizes_in_range:
            return random.choice(sizes_in_range)
        else:
            return "", ""

    def get_address(self, addresses):
        blueprint = {
            "address1": self.task.parent.address.lower().replace(" ", ""),
            "city": self.task.parent.city.lower().replace(" ", ""),
            "postal_code": self.task.parent.postcode.lower().replace(" ", ""),
            "country": self.task.parent.country.lower().replace(" ", ""),
            "country_code": self.task.parent.country.lower().replace(" ", ""),
            "first_name": self.task.parent.first_name.lower().replace(" ", ""),
            "last_name": self.task.parent.last_name.lower().replace(" ", "")
        }
        if self.task.parent.line_2:
            blueprint["address2"] = self.task.parent.line_2.lower().replace(" ", "")

        for address in addresses:
            if self.task.parent.is_address_loaded:
                for key, value in blueprint.items():
                    if key not in address or address[key].lower().replace(" ", "") != value:
                        break
                else:
                    return address
            else:
                return address

    def get_payment_id(self, cards):
        blueprint = {
            "card_bin": self.task.parent.card_number[:6],
            "number": self.task.parent.card_number[-4:],
            "expiration_month": self.task.parent.card_month.removeprefix("0"),
            "expiration_year": self.task.parent.card_year
        }

        for card in cards:
            for key, value in blueprint.items():
                if card[key] != value:
                    break
            else:
                return card["payment_info_reference_id"]

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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/gw-api/v2/user/addresses",
                    headers={
                        "accept": "application/hal+json",
                        "x-device-info": f"app/CONFIRMED; os/iOS; os-version/{self.akamai_bmp.device_os_version}; app-version/{APP_VERSION}; buildnumber/{APP_BUILD_NUMBER}; type/{self.akamai_bmp.device_name}; fingerprint/{self.akamai_bmp.device_id}",
                        "x-market": self.task.parent.country,
                        "authorization": "Bearer " + self.data["accessToken"],
                        "x-signature": self.generate_signature(),
                        "accept-language": None,
                        "x-api-key": API_KEY,
                        "accept-encoding": "gzip, deflate, br",
                        "user-agent": None,
                        "x-app-info": f"platform/iOS version/{APP_VERSION}",
                        "x-forter-mobile-uid": self.akamai_bmp.device_id,
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["address"] = self.get_address(
                        response.json()["addresses"]
                    )
                    break
                except (JSONError, KeyError, TypeError):
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

        if not self.data["address"]:
            return self.add_address()
        else:
            return self.fetch_raffle()

    def add_address(self):
        self.logger.info("Adding address...")

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
                try:
                    self.data["address"] = response.json()
                    break
                except JSONError:
                    self.logger.error("Failed to add address"), self.delay()
                    error_count += 1
                    continue
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

        return self.fetch_raffle()

    def fetch_raffle(self):
        self.logger.info("Entering raffle...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/gw-api/v2/trilogy/products/{self.task.input.raffle['id']}",
                    params={
                        "experiment_product_data": "false"
                    },
                    headers={
                        "accept": "application/hal+json",
                        "x-device-info": f"app/CONFIRMED; os/iOS; os-version/{self.akamai_bmp.device_os_version}; app-version/{APP_VERSION}; buildnumber/{APP_BUILD_NUMBER}; type/{self.akamai_bmp.device_name}; fingerprint/{self.akamai_bmp.device_id}",
                        "x-market": self.task.parent.country,
                        "authorization": "Bearer " + self.data["accessToken"],
                        "x-signature": self.generate_signature(),
                        "accept-language": None,
                        "x-api-key": API_KEY,
                        "accept-encoding": "gzip, deflate, br",
                        "user-agent": None,
                        "x-app-info": f"platform/iOS version/{APP_VERSION}",
                        "x-forter-mobile-uid": self.akamai_bmp.device_id,
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    content = response.json()

                    self.product.name = f"{content['product_full_name']} {content['original_color']}"
                    self.product.price = f"{content['display_currency']} {content['original_price']}"
                    self.product.image = content["_links"]["image_large"]["href"]

                    if content.get("collection_event"):
                        self.data["eventType"] = "reservation"
                        self.data["eventId"] = content["collection_event"]["event_id"]
                        self.data["eventStartTime"] = datetime.strptime(
                            content["collection_event"]["registration_opens_at"], "%Y-%m-%dT%H:%M:%S.%f%z"
                        ).astimezone(timezone.utc)
                    elif content.get("queue_pro_event"):
                        self.data["eventType"] = "queue"
                        self.data["eventId"] = content["queue_pro_event"]["event_id"]
                        self.data["eventStartTime"] = datetime.strptime(
                            content["queue_pro_event"]["registration_opens_at"], "%Y-%m-%dT%H:%M:%S.%f%z"
                        ).astimezone(timezone.utc)
                    else:
                        self.data["eventType"] = "normal"
                        self.data["eventId"] = content["hype_event"]["event_id"]
                        self.data["eventStartTime"] = datetime.strptime(
                            content["hype_event"]["registration_opens_at"], "%Y-%m-%dT%H:%M:%S.%f%z"
                        ).astimezone(timezone.utc)
                    break
                except (JSONError, KeyError, ValueError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 404:
                self.logger.error("Failed to enter raffle: Raffle closed")
                return False
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

        self.wait_for_release()

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/gw-api/v2/hype/products/{self.task.input.raffle['id']}/availability",
                    params={
                        "experiment_product_data": "false"
                    },
                    headers={
                        "accept": "application/hal+json",
                        "x-device-info": f"app/CONFIRMED; os/iOS; os-version/{self.akamai_bmp.device_os_version}; app-version/{APP_VERSION}; buildnumber/{APP_BUILD_NUMBER}; type/{self.akamai_bmp.device_name}; fingerprint/{self.akamai_bmp.device_id}",
                        "x-market": self.task.parent.country,
                        "authorization": "Bearer " + self.data["accessToken"],
                        "x-signature": self.generate_signature(),
                        "accept-language": None,
                        "x-api-key": API_KEY,
                        "accept-encoding": "gzip, deflate, br",
                        "user-agent": None,
                        "x-app-info": f"platform/iOS version/{APP_VERSION}",
                        "x-forter-mobile-uid": self.akamai_bmp.device_id,
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.product.size, self.data["sizeId"] = self.get_size(
                        response.json()["_embedded"]["variations"]
                    )
                    break
                except (JSONError, KeyError, ValueError):
                    self.logger.error("Failed to enter raffle"), self.delay()
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

        if self.product.size:
            return self.enter_raffle()
        else:
            self.logger.error("Failed to enter raffle: No sizes in range")
            return False

    def enter_raffle(self):
        self.delay()

        if self.data["eventType"] == "reservation":
            error_count = 0
            while error_count < self.max_retries:
                try:
                    response = self.session.post(
                        f"https://{DOMAIN}/gw-api/v2/hype/reservations",
                        body={
                            "event_id": self.data["eventId"],
                            "product_id": self.task.input.raffle["id"],
                            "sku": self.data["sizeId"]
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
                    try:
                        if response.json()["state"] == "FULFILLED":
                            break
                        else:
                            raise KeyError
                    except (JSONError, KeyError):
                        self.logger.error("Failed to enter raffle"), self.delay()
                        error_count += 1
                        continue
                elif response.status in [400, 500]:
                    self.logger.error("Failed to enter raffle"), self.delay()
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
                    f"https://{DOMAIN}/gw-api/v2/hype/basket",
                    body={
                        "items": [{
                            "product_id": self.task.input.raffle["id"],
                            "variation_product_id": self.data["sizeId"],
                            "quantity": 1
                        }],
                        "event_id": self.data["eventId"]
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
                        "x-acf-sensor-data": self.data["sensorData"],
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
                try:
                    content = response.json()

                    self.data["cartId"] = content["basket_id"]
                    self.data["totalPrice"] = content["total_price"]
                    self.data["currency"] = content["currency"]
                    self.data["shippingMethod"] = content["selected_carrier_service"]["shipping_method_id"]

                    self.data["paymentId"] = self.get_payment_id(
                        content["available_payment_methods"][1].get("available_cards", [])
                    )
                    break
                except (JSONError, KeyError, IndexError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status in [400, 500]:
                try:
                    if response.json()["title"] == "HypeEventAlreadyParticipating":
                        self.logger.error("Failed to enter raffle: Already entered")
                        return False
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to enter raffle"), self.delay()
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
                response = self.session.put(
                    f"https://{DOMAIN}/gw-api/v2/hype/basket/{self.data['cartId']}",
                    body={
                        "items": [{
                            "product_id": self.task.input.raffle["id"],
                            "variation_product_id": self.data["sizeId"],
                            "quantity": 1
                        }],
                        "invoice_info": {
                            "type": "0"
                        },
                        "selected_shipping_type_id": "home_delivery",
                        "billing_info": {
                            "id": self.data["address"]["id"],
                            "personal_id": "",
                            "address1": self.data["address"]["address1"],
                            "address2": self.data["address"].get("address2", ""),
                            "type": "home",
                            "first_name": self.data["address"]["first_name"],
                            "city": self.data["address"]["city"],
                            "business_name": "",
                            "document_type_id": "",
                            "postal_code": self.data["address"]["postal_code"],
                            "last_name": self.data["address"]["last_name"],
                            "country_code": self.data["address"]["country_code"],
                            "tax_administration": ""
                        },
                        "selected_carrier_service_id": self.data["shippingMethod"],
                        "shipping_info": {
                            "address2": self.data["address"].get("address2", ""),
                            "postal_code": self.data["address"]["postal_code"],
                            "address1": self.data["address"]["address1"],
                            "id": self.data["address"]["id"],
                            "city": self.data["address"]["city"],
                            "last_name": self.data["address"]["last_name"],
                            "country_code": self.data["address"]["country_code"],
                            "type": "home",
                            "first_name": self.data["address"]["first_name"]
                        },
                        "prefix_payment_method": self.task.parent.card_number[:6],
                        "selected_invoice_type_id": "0",
                        "event_id": self.data["eventId"],
                        "selected_payment_method_id": "CREDIT_CARD"
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
                        "x-acf-sensor-data": self.data["sensorData"],
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
                self.logger.error("Failed to enter raffle"), self.delay()
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
                    f"https://{DOMAIN}/gw-api/v2/hype/basket/{self.data['cartId']}/order",
                    body={
                        "items": [{
                            "product_id": self.task.input.raffle["id"],
                            "variation_product_id": self.data["sizeId"],
                            "quantity": 1
                        }],
                        "invoice_info": {
                            "type": "0"
                        },
                        "selected_shipping_type_id": "home_delivery",
                        "billing_info": {
                            "id": self.data["address"]["id"],
                            "personal_id": "",
                            "address1": self.data["address"]["address1"],
                            "house_number": "",
                            "colony": "",
                            "address2": self.data["address"].get("address2", ""),
                            "middle_name": "",
                            "address3": "",
                            "first_name": self.data["address"]["first_name"],
                            "city": self.data["address"]["city"],
                            "document_type_id": "",
                            "district": "",
                            "postal_code": self.data["address"]["postal_code"],
                            "last_name": self.data["address"]["last_name"],
                            "country_code": self.data["address"]["country_code"],
                            "business_name": "",
                            "tax_administration": ""
                        },
                        "selected_carrier_service_id": self.data["shippingMethod"],
                        "shipping_info": {
                            "id": self.data["address"]["id"],
                            "personal_id": "",
                            "address1": self.data["address"]["address1"],
                            "house_number": "",
                            "colony": "",
                            "address2": self.data["address"].get("address2", ""),
                            "middle_name": "",
                            "address3": "",
                            "first_name": self.data["address"]["first_name"],
                            "city": self.data["address"]["city"],
                            "document_type_id": "",
                            "district": "",
                            "postal_code": self.data["address"]["postal_code"],
                            "last_name": self.data["address"]["last_name"],
                            "country_code": self.data["address"]["country_code"],
                            "business_name": "",
                            "tax_administration": ""
                        },
                        "prefix_payment_method": self.task.parent.card_number[:6],
                        "selected_invoice_type_id": "0",
                        "event_id": self.data["eventId"],
                        "payment_info": self.generate_payment_body(),
                        "selected_payment_method_id": "CREDIT_CARD"
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
                        "x-acf-sensor-data": self.data["sensorData"],
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
                try:
                    content = response.json()

                    if content.get("order_number"):
                        break
                    else:
                        content = base64.b64decode(
                            content["3d_secure"]["3d_secure_base64_html"]
                        ).decode()

                        self.data["3ds"] = {
                            "url": re.findall('action="(.*?)" id="3dform"', content)[0],
                            "md": re.findall('name="MD" value="(.*?)"', content)[0],
                            "paReq": re.findall('name="PaReq" value="(.*?)"', content)[0],
                            "termUrl": re.findall('name="TermUrl" value="(.*?)"', content)[0]
                        }
                        break
                except:
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status in [400, 500]:
                self.logger.error("Failed to enter raffle"), self.delay()
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
                    self.data["3ds"]["termUrl"],
                    body={
                        "MD": self.data["3ds"]["md"],
                        "PaRes": self.data["3ds"]["paRes"]
                    },
                    headers={
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "content-type": "application/x-www-form-urlencoded",
                        "origin": "https://checkoutshopper-live.adyen.com",
                        "content-length": None,
                        "accept-language": None,
                        "user-agent": None,
                        "referer": "https://checkoutshopper-live.adyen.com/",
                        "accept-encoding": "gzip, deflate, br"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    content = json.loads(base64.b64decode(
                        re.findall('name="order" type="hidden" value="(.*?)"', response.body)[0]
                    ).decode())

                    if content.get("order_number"):
                        break
                    else:
                        raise Exception
                except:
                    self.logger.error("Failed to enter raffle"), self.delay()
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

        self.logger.success("Successfully entered raffle")
        return True
