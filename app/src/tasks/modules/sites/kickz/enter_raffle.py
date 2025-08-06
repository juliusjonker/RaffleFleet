# -*- coding: utf-8 -*-
import random
import re
import json
import html
from common import http
from common.utils import sleep, size_to_float
from tasks.common import webhooks, Logger, Browser
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, ChallengeError, JSONError
from tasks.hooks import pow_challenge
from .constants import NAME, DOMAIN, REGIONS


class EnterRaffle:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = Logger(
            NAME, task.id, task.formatted_parent_id
        )

        self.session = http.Session(
            proxy=task.proxies.get(),
            hook=pow_challenge.hook
        )

        self.product = Product()
        self.data = {
            "regionUrl": (
                f"https://{DOMAIN}/{REGIONS.get(self.task.parent.country, 'en')}/" +
                "/".join(task.input.raffle["url"].split("/")[4:])
            ),
            "region": REGIONS.get(self.task.parent.country, "en")
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
            if not size_data["selectable"]:
                continue

            size = size_data["sizeMap"]["EU"]["title"]
            if self.task.input.size_range.fits(size_to_float(size)):
                sizes_in_range.append((
                    size, size_data["value"]
                ))

        if sizes_in_range:
            return random.choice(sizes_in_range)
        else:
            return "", ""

    def execute(self):
        status = "entered" if self.log_in() else "failed"

        if status == "entered":
            webhooks.Entry(
                NAME, self.product, self.task.parent, self.session.proxy,
                proxy_img=True
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
                    f"https://{DOMAIN}/{self.data['region']}/login/",
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
                        "referer": f"https://{DOMAIN}/",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, ChallengeError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["companyId"] = re.findall('data-company-id="(.*?)"', response.body)[0]
                    self.data["policyId"] = re.findall('data-login-policy-id="(.*?)"', response.body)[0]
                    self.data["apiKey"] = re.findall('data-api-key="(.*?)"', response.body)[0]
                    self.data["loginUrl"] = re.findall('data-login-action-url="(.*?)"', response.body)[0]
                    self.data["csrfToken"] = re.findall('data-token-name="csrf_token" data-token-value="(.*?)"', response.body)[0]
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
                response = self.session.get(
                    f"https://orchestrate-api.pingone.eu/v1/company/{self.data['companyId']}/sdktoken",
                    headers={
                        "sec-ch-ua": None,
                        "x-sk-api-key": self.data["apiKey"],
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "accept": "*/*",
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "cross-site",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{DOMAIN}/",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, ChallengeError) as error:
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
                    f"https://account.kickz.com/davinci/policy/{self.data['policyId']}/start",
                    body={
                        "lang": "en",
                        "locale": "en"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "content-type": "application/json",
                        "sec-ch-ua-mobile": "?0",
                        "authorization": "Bearer " + self.data["accessToken"],
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "accept": "*/*",
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-site",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{DOMAIN}/",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, ChallengeError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    content = response.json()

                    self.data["id"] = content["id"]
                    self.data["connectionId"] = content["connectionId"]
                    self.data["interactionId"] = content["interactionId"]
                    self.data["interactionToken"] = content["interactionToken"]
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://account.kickz.com/davinci/connections/{self.data['connectionId']}/capabilities/customHTMLTemplate",
                    body={
                        "id": self.data["id"],
                        "nextEvent": {
                            "constructType": "skEvent",
                            "eventName": "continue",
                            "params": [],
                            "eventType": "post",
                            "postProcess": {}
                        },
                        "parameters": {
                            "buttonType": "form-submit",
                            "buttonValue": "loginButton",
                            "username": self.task.parent.email,
                            "password": self.task.parent.password,
                            "inMail": "",
                            "mail": ""
                        },
                        "eventName": "continue"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "interactiontoken": self.data["interactionToken"],
                        "user-agent": None,
                        "content-type": "application/json",
                        "interactionid": self.data["interactionId"],
                        "sec-ch-ua-platform": None,
                        "accept": "*/*",
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-site",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{DOMAIN}/",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, ChallengeError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    content = response.json()

                    self.data["id"] = content["id"]
                    self.data["connectionId"] = content["connectionId"]
                    self.data["interactionId"] = content["interactionId"]
                    self.data["interactionToken"] = content["interactionToken"]
                    break
                except (JSONError, KeyError):
                    self.logger.error("Failed to log in"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 400:
                try:
                    if "your e-mail or password doesn't match our records" in response.json()["message"]:
                        self.logger.error("Failed to log in: Invalid credentials")
                        return False
                    else:
                        raise KeyError
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://account.kickz.com/davinci/connections/{self.data['connectionId']}/capabilities/setCookieWithoutUser",
                    body={
                        "eventName": "complete",
                        "parameters": {},
                        "id": self.data["id"]
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "interactiontoken": self.data["interactionToken"],
                        "user-agent": None,
                        "content-type": "application/json",
                        "interactionid": self.data["interactionId"],
                        "sec-ch-ua-platform": None,
                        "accept": "*/*",
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-site",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{DOMAIN}/",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, ChallengeError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    content = response.json()["additionalProperties"]

                    self.data["idToken"] = content["id_token"]
                    self.data["refreshToken"] = content["refresh_token"]
                    self.data["accessToken"] = content["access_token"]
                    break
                except (JSONError, KeyError):
                    self.logger.error("Failed to log in"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 400:
                try:
                    if "Capability not found" in response.json()["message"]:
                        self.logger.error("Failed to log in: Account isn't verified")
                        return False
                    else:
                        raise KeyError
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    self.data["loginUrl"],
                    body={
                        "id_token": self.data["idToken"],
                        "access_token": self.data["accessToken"],
                        "refresh_token": self.data["refreshToken"],
                        "csrf_token": self.data["csrfToken"]
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "application/json",
                        "content-type": "application/x-www-form-urlencoded",
                        "x-requested-with": "XMLHttpRequest",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "same-origin",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{DOMAIN}/{self.data['region']}/login/no-referrer",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, ChallengeError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    if response.json()["success"]:
                        break
                    else:
                        raise KeyError
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
                    self.data["regionUrl"],
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
            except (HTTPError, ChallengeError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    content = json.loads(html.unescape(
                        re.findall(r'data-content="([\s|\S]*?)">', response.body)[0]
                    ).replace("\n", ""))["productData"]

                    if content["raffle"]["isRaffleEnded"]:
                        self.logger.error("Failed to enter raffle: Raffle closed")
                        return False
                    elif '<div class="b-raffle-message">' in response.body:
                        self.logger.error("Failed to enter raffle: Already entered")
                        return False

                    self.product.name = content["productName"]
                    self.product.price = content["price"]["sales"]["formatted"]
                    self.product.image = content["images"]["large"][0]["url"]
                    self.product.size, self.data["sizeId"] = self.get_size(
                        content["variationAttributes"][1]["values"]
                    )

                    self.data["productId"] = content["itemID"]
                    self.data["raffleId"] = re.findall('data-raffleid="(.*?)"', response.body)[0]
                    self.data["entryPath"] = re.findall('<form action="(.*?)"', response.body)[0]
                    self.data["clearCartPath"] = re.findall('data-clear-basket-url="(.*?)"', response.body)[0]
                    self.data["finalizeEntryUrl"] = re.findall('submitPayment&quot;:&quot;(.*?)&quot;', response.body)[0]
                    self.data["paypalClientId"] = re.findall('client-id=(.*?)&', response.body)[0]
                    self.data["csrfToken"] = re.findall('data-token-name="csrf_token" data-token-value="(.*?)"', response.body)[0]
                    break
                except (JSONError, KeyError, IndexError, ValueError):
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
            return self.submit_order()
        else:
            self.logger.error("Failed to enter raffle: No sizes in range")
            return False

    def submit_order(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}{self.data['clearCartPath']}",
                    params={
                        "ajax": "true"
                    },
                    headers={
                        "sec-ch-ua": None,
                        "accept": "application/json",
                        "content-type": "application/x-www-form-urlencoded",
                        "x-requested-with": "XMLHttpRequest",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "same-origin",
                        "sec-fetch-dest": "empty",
                        "referer": self.data["regionUrl"],
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, ChallengeError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    if not response.json()["error"]:
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}{self.data['entryPath']}",
                    params={
                        "ajax": "true"
                    },
                    body={
                        "pid": self.data["productId"] + self.data["sizeId"],
                        "quantity": "1",
                        "options": "[]",
                        "childProducts": "[]",
                        "dwfrm_raffle_raffleSpecificFields_consentOnNewsletter": "",
                        "dwfrm_raffle_addressFields_salutation": "mrs" if self.task.parent.gender == "female" else "mr",
                        "dwfrm_raffle_addressFields_firstName": self.task.parent.first_name,
                        "dwfrm_raffle_addressFields_lastName": self.task.parent.last_name,
                        "dwfrm_raffle_addressFields_country": self.task.parent.country,
                        "dwfrm_raffle_addressFields_states_stateCode": "",
                        "dwfrm_raffle_addressFields_city": self.task.parent.city,
                        "dwfrm_raffle_addressFields_postalCode": self.task.parent.postcode,
                        "dwfrm_raffle_addressFields_address1": self.task.parent.street,
                        "dwfrm_raffle_addressFields_address2": self.task.parent.house_number,
                        "dwfrm_raffle_addressFields_doorCode": "",
                        "dwfrm_raffle_addressFields_additionalAddressInfo": self.task.parent.line_2,
                        "dwfrm_raffle_addressFields_companyName": "",
                        "dwfrm_raffle_contactInfoFields_phone": self.task.parent.full_phone,
                        "dwfrm_raffle_addressFields_saveAddress": "",
                        "dwfrm_raffle_raffleSpecificFields_instagramAccount": self.task.parent.instagram,
                        "dwfrm_raffle_raffleSpecificFields_consentOnConditions": "true",
                        "csrf_token": self.data["csrfToken"]
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "application/json",
                        "content-type": "application/x-www-form-urlencoded",
                        "x-requested-with": "XMLHttpRequest",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "same-origin",
                        "sec-fetch-dest": "empty",
                        "referer": self.data["regionUrl"],
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, ChallengeError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["paypalBody"] = response.json()["purchase_units"]
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
                response = self.session.get(
                    "https://www.paypal.com/smart/buttons",
                    params={
                        "clientID": self.data["paypalClientId"]
                    },
                    headers={
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                        "sec-fetch-site": "cross-site",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-dest": "iframe",
                        "referer": f"https://{DOMAIN}/",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, ChallengeError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["paypalAccessToken"] = re.findall('"facilitatorAccessToken":"(.*?)"', response.body)[0]
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
                    "https://www.paypal.com/v2/checkout/orders",
                    body={
                        "purchase_units": self.data["paypalBody"],
                        "payer": {
                            "name": {
                                "given_name": self.task.parent.first_name,
                                "surname": self.task.parent.last_name
                            },
                            "address": {
                                "address_line_1": self.task.parent.street,
                                "address_line_2": self.task.parent.house_number,
                                "admin_area_2": self.task.parent.city,
                                "admin_area_1": "",
                                "postal_code": self.task.parent.postcode,
                                "country_code": self.task.parent.country
                            },
                            "phone": {
                                "phone_number": {
                                    "national_number": self.task.parent.full_phone.removeprefix("+")
                                }
                            },
                            "email_address": self.task.parent.email
                        },
                        "application_context": {
                            "shipping_preference": "SET_PROVIDED_ADDRESS"
                        },
                        "intent": "AUTHORIZE"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "prefer": "return=representation",
                        "sec-ch-ua-mobile": "?0",
                        "authorization": "Bearer " + self.data["paypalAccessToken"],
                        "user-agent": None,
                        "content-type": "application/json",
                        "accept": "application/json",
                        "sec-ch-ua-platform": None,
                        "origin": "https://www.paypal.com",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, ChallengeError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["paypalTransactionId"] = response.json()["id"]
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
                    self.data["finalizeEntryUrl"],
                    params={
                        "ajax": "true"
                    },
                    body={
                        "accelerated": "false",
                        "orderID": self.data["paypalTransactionId"],
                        "payerID": self.data["paypalUserId"],
                        "paymentID": "null",
                        "billingToken": "null",
                        "facilitatorAccessToken": self.data["paypalAccessToken"],
                        "paymentSource": "paypal",
                        "rid": self.data["raffleId"],
                        "csrf_token": self.data["csrfToken"]
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "application/json",
                        "content-type": "application/x-www-form-urlencoded",
                        "x-requested-with": "XMLHttpRequest",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "same-origin",
                        "sec-fetch-dest": "empty",
                        "referer": self.data["regionUrl"],
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except (HTTPError, ChallengeError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    if not response.json()["error"]:
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
