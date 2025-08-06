# -*- coding: utf-8 -*-
import random
import re
import json
import uuid
import secrets
import base64
from datetime import datetime, timezone
from common import http
from common.utils import sleep, size_to_float, current_ts
from tasks.common import webhooks, Logger, Browser
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, JSONError
from tasks.hooks import adyen, captcha
from .constants import NAME, RAFFLE_DOMAIN, ADYEN_VERSION, ADYEN_PUBLIC_KEY, HCAPTCHA_SITE_KEY, CARD_TYPES


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

        self.adyen = adyen.Encryptor(
            ADYEN_VERSION, ADYEN_PUBLIC_KEY
        )
        self.captcha = captcha.Solver(
            self.logger, "h", RAFFLE_DOMAIN, HCAPTCHA_SITE_KEY
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

    @staticmethod
    def is_raffle_closed(close_datetime):
        return datetime.strptime(
            close_datetime, "%Y-%m-%dT%H:%M:%S%z"
        ).astimezone(timezone.utc) < datetime.now(timezone.utc)

    @staticmethod
    def generate_attempt_id():
        return f"{uuid.uuid4()}{round(current_ts(exact=True) * 1000)}{secrets.token_hex(32).upper()}"

    def get_size(self, sizes):
        sizes_in_range = []
        for size_data in sizes:
            size = size_data["eur"]
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
                        "cache-control": "max-age=0",
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
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
                    content = json.loads(
                        re.findall('window\.__INITIAL_STATE__ = (.*?)</script>', response.body)[0]
                    )["raffleDetail"]["raffle"]

                    if self.is_raffle_closed(content["closeRegistrationAt"]):
                        self.logger.error("Failed to enter raffle: Raffle closed")
                        return False

                    self.product.name = f"{content['translations']['en']['title']} {content['translations']['en']['subtitle']}"
                    self.product.price = f"€ {content['prices']['EUR']['value']}"
                    self.product.image = "https://releases-static.footshop.com/images/raffle/" + content["imagesPortrait"][0]
                    self.product.size, self.data["sizeId"] = self.get_size(
                        content["sizeSets"][re.findall('name="sex" value="(.*?)"', response.body)[0]]["sizes"]
                    )

                    self.data["raffleId"] = content["id"]
                    self.data["checkoutUrl"] = f"https://{RAFFLE_DOMAIN}/register/{self.data['raffleId']}/Men/{self.data['sizeId']}"
                    self.data["closeTimestamp"] = round(datetime.strptime(content["closeRegistrationAt"], "%Y-%m-%dT%H:%M:%S%z").timestamp())
                    break
                except (JSONError, KeyError, IndexError, ValueError):
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
            return self.submit_order()
        else:
            self.logger.error("Failed to enter raffle: No sizes in range")
            return False

    def submit_order(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{RAFFLE_DOMAIN}/api/registrations/create/{self.data['raffleId']}",
                    body={
                        "id": None,
                        "sizerunId": self.data["sizeId"],
                        "account": "New Customer",
                        "email": self.task.parent.email,
                        "phone": self.task.parent.full_phone,
                        "gender": "Mrs" if self.task.parent.gender == "female" else "Mr",
                        "firstName": self.task.parent.first_name,
                        "lastName": self.task.parent.last_name,
                        "instagramUsername": self.task.parent.instagram,
                        "birthday": self.task.parent.format_date_of_birth("%Y-%m-%d"),
                        "deliveryAddress": {
                            "country": self.task.parent.country,
                            "state": "",
                            "county": "",
                            "city": self.task.parent.city,
                            "street": self.task.parent.street,
                            "houseNumber": self.task.parent.house_number,
                            "additional": self.task.parent.line_2,
                            "postalCode": self.task.parent.postcode
                        },
                        "consents": ["privacy-policy-101"],
                        "verification": {
                            "token": self.captcha.solve()
                        }
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "application/json, text/plain, */*",
                        "content-type": "application/json;charset=UTF-8",
                        "cache-control": "no-cache",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{RAFFLE_DOMAIN}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": self.data["checkoutUrl"],
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
                    self.data["registrationId"] = response.json()["registration"]["id"]
                    break
                except (JSONError, KeyError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 422:
                try:
                    if response.json()["errors"]["registration"][""] == "User is already registered":
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
                response = self.session.post(
                    f"https://{RAFFLE_DOMAIN}/api/payment/make/{self.data['registrationId']}",
                    body={
                        "riskData": {
                            "clientData": ""
                        },
                        "paymentMethod": {
                            "type": "scheme",
                            "holderName": self.task.parent.full_name,
                            "encryptedCardNumber": self.adyen.encrypt({"number": self.task.parent.card_number}),
                            "encryptedExpiryMonth": self.adyen.encrypt({"expiryMonth": self.task.parent.card_month}),
                            "encryptedExpiryYear": self.adyen.encrypt({"expiryYear": self.task.parent.card_year}),
                            "encryptedSecurityCode": self.adyen.encrypt({"cvc": self.task.parent.card_cvc}),
                            "brand": CARD_TYPES.get(self.task.parent.card_type),
                            "checkoutAttemptId": self.generate_attempt_id()
                        },
                        "browserInfo": {
                            "acceptHeader": "*/*",
                            "colorDepth": 24,
                            "language": "en",
                            "javaEnabled": False,
                            "screenHeight": 720,
                            "screenWidth": 1280,
                            "userAgent": self.session.headers.user_agent,
                            "timeZoneOffset": 0
                        },
                        "origin": f"https://{RAFFLE_DOMAIN}",
                        "clientStateDataIndicator": True
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "application/json, text/plain, */*",
                        "content-type": "application/json;charset=UTF-8",
                        "cache-control": "no-cache",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{RAFFLE_DOMAIN}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": self.data["checkoutUrl"],
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
                    content = response.json()["paymentDetail"]["action"]
                    challenge_content = json.loads(
                        base64.b64decode(content["token"]).decode()
                    )

                    if content["subtype"] == "fingerprint":
                        self.data["3ds"] = {
                            "type": "fingerprint",
                            "paymentData": content["paymentData"]
                        }
                        break
                    else:
                        self.data["3ds"] = {
                            "type": "challenge",
                            "url": challenge_content["acsURL"],
                            "acsTransID": challenge_content["acsTransID"],
                            "messageVersion": challenge_content["messageVersion"],
                            "threeDSServerTransID": challenge_content["threeDSServerTransID"],
                            "authToken": content["authorisationToken"]
                        }
                    break
                except:
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 422:
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
        if self.data["3ds"]["type"] == "fingerprint":
            error_count = 0
            while error_count < self.max_retries:
                try:
                    response = self.session.post(
                        "https://checkoutshopper-live.adyen.com/checkoutshopper/v1/submitThreeDS2Fingerprint",
                        params={
                            "token": "live_Y44FYNDGDNFBNKSYXDDP4H2LBQKOU4N3"
                        },
                        body={
                            "fingerprintResult": "",
                            "paymentData": self.data["3ds"]["paymentData"]
                        },
                        headers={
                            "Connection": "keep-alive",
                            "Content-Length": None,
                            "sec-ch-ua": None,
                            "Accept": "application/json, text/plain, */*",
                            "Content-Type": "application/json",
                            "sec-ch-ua-mobile": "?0",
                            "User-Agent": None,
                            "sec-ch-ua-platform": None,
                            "Origin": f"https://{RAFFLE_DOMAIN}",
                            "Sec-Fetch-Site": "cross-site",
                            "Sec-Fetch-Mode": "cors",
                            "Sec-Fetch-Dest": "empty",
                            "Referer": self.data["checkoutUrl"],
                            "Accept-Encoding": "gzip, deflate, br",
                            "Accept-Language": None
                        }
                    )
                except HTTPError as error:
                    self.logger.error(error.msg), self.delay()
                    self.switch_proxy()
                    continue

                if response.ok:
                    try:
                        content = response.json()

                        if content["type"] == "completed":
                            self.data["3ds"] = {
                                "type": "complete",
                                "result": content["details"]["threeDSResult"]
                            }
                        else:
                            challenge_content = json.loads(
                                base64.b64decode(content["action"]["token"]).decode()
                            )

                            self.data["3ds"] = {
                                "type": "challenge",
                                "url": challenge_content["acsURL"],
                                "acsTransID": challenge_content["acsTransID"],
                                "messageVersion": challenge_content["messageVersion"],
                                "threeDSServerTransID": challenge_content["threeDSServerTransID"],
                                "authToken": content["action"]["authorisationToken"]
                            }
                        break
                    except:
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

        if self.data["3ds"]["type"] == "complete":
            return self.submit_3ds()

        try:
            browser = Browser()
        except:
            self.logger.error("Failed to enter raffle: Browser error")
            return False

        try:
            browser.post(
                self.data["3ds"]["url"],
                body={
                    "creq": base64.b64encode(json.dumps({
                        "acsTransID": self.data["3ds"]["acsTransID"],
                        "messageVersion": self.data["3ds"]["messageVersion"],
                        "threeDSServerTransID": self.data["3ds"]["threeDSServerTransID"],
                        "messageType": "CReq",
                        "challengeWindowSize": "02"
                    }).encode()).decode()
                }
            )

            body = browser.await_response(re.compile(
                '<input type="hidden" name="transStatus" value="(.*?)"'
            ))

            self.data["3ds"]["transStatus"] = re.findall('name="transStatus" value="(.*?)"', body)[0]
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
                    f"https://{RAFFLE_DOMAIN}/api/payment/make/{self.data['registrationId']}",
                    body={
                        "details": {
                            "threeDSResult": self.data["3ds"].get("result") or base64.b64encode(json.dumps({
                                "transStatus": self.data["3ds"]["transStatus"],
                                "authorisationToken": self.data["3ds"]["authToken"]
                            }).encode()).decode()
                        }
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "application/json, text/plain, */*",
                        "content-type": "application/json;charset=UTF-8",
                        "cache-control": "no-cache",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{RAFFLE_DOMAIN}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": self.data["checkoutUrl"],
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                break
            elif response.status == 422:
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
                response = self.session.get(
                    f"https://{RAFFLE_DOMAIN}/registration/finish/{self.data['registrationId']}/guest/{self.data['closeTimestamp']}",
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
                        "referer": self.data["checkoutUrl"],
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                if "Thank you!" in response.body:
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
