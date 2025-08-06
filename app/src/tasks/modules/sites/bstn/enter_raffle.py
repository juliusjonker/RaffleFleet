# -*- coding: utf-8 -*-
import random
import re
import json
import html
from common import http
from common.utils import sleep, size_to_float
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, CloudflareError, TurnstileError, JSONError
from tasks.hooks import cloudflare
from .constants import NAME, DOMAIN, RAFFLE_DOMAIN, TURNSTILE_SITE_KEY


class EnterRaffle:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = Logger(
            NAME, task.id, task.formatted_parent_id
        )

        self.session = http.Session(
            proxy=task.proxies.get(),
            hook=cloudflare.get_hook(self.logger)
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

    def get_size(self, sizes):
        sizes_in_range = []
        for size_data in sizes:
            if not size_data["attributes"]:
                continue

            size = size_data["attributes"][0]["label"].replace(",", ".")
            if self.task.input.size_range.fits(size_to_float(size)):
                sizes_in_range.append((
                    size, size_data["product"]["id"]
                ))

        if sizes_in_range:
            return random.choice(sizes_in_range)
        else:
            return "", ""

    def get_address_id(self, addresses):
        blueprint = {
            "firstname": self.task.parent.first_name.lower().replace(" ", ""),
            "lastname": self.task.parent.last_name.lower().replace(" ", ""),
            "street": list(filter(None, [
                self.task.parent.street.lower().replace(" ", ""),
                self.task.parent.house_number.lower().replace(" ", ""),
                self.task.parent.line_2.lower().replace(" ", "")
            ])),
            "city": self.task.parent.city.lower().replace(" ", ""),
            "postcode": self.task.parent.postcode.lower().replace(" ", ""),
            "country_code": self.task.parent.country.lower().replace(" ", ""),
            "telephone": self.task.parent.full_phone.lower().replace(" ", ""),
        }

        for address in addresses:
            if self.task.parent.is_address_loaded:
                for key, value in blueprint.items():
                    if isinstance(value, str) and address[key].lower().replace(" ", "") != value:
                        break
                    elif isinstance(value, list) and [x.lower().replace(" ", "") for x in address[key]] != value:
                        break
                else:
                    return address["id"]
            else:
                return address["id"]

    def solve_turnstile(self, response):
        while True:
            try:
                return cloudflare.Solver(
                    self.session, self.logger, response
                ).solve_turnstile(response.url, TURNSTILE_SITE_KEY)
            except (HTTPError, TurnstileError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

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
                    f"https://{DOMAIN}/eu_en/",
                    headers={
                        "cache-control": "max-age=0",
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
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
                response = self.session.post(
                    f"https://{DOMAIN}/eu_en/sociallogin/popup/login/",
                    body={
                        "username": self.task.parent.email,
                        "password": self.task.parent.password
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "*/*",
                        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "x-requested-with": "XMLHttpRequest",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{DOMAIN}/eu_en/",
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
                    content = response.json()

                    if content.get("success"):
                        break
                    elif "Invalid login" in content["message"]:
                        self.logger.error("Failed to log in: Invalid credentials")
                        return False
                    elif "This account isn't confirmed" in content["message"]:
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
                    f"https://{RAFFLE_DOMAIN}/graphql",
                    body={
                        "operationName": "Customer",
                        "variables": {},
                        "query": "query Customer {\n  customer {\n    firstname\n    lastname\n    suffix\n    email\n    registered_raffles\n    instagram_name\n    addresses {\n      id\n      firstname\n      lastname\n      street\n      city\n      region {\n        region_id\n        region_code\n        region\n        __typename\n      }\n      postcode\n      country_code\n      country_name\n      telephone\n      __typename\n    }\n    __typename\n  }\n}"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "*/*",
                        "content-type": "application/json",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{RAFFLE_DOMAIN}",
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
                    content = response.json()["data"]["customer"]

                    self.data["customer"] = content
                    self.data["addressId"] = self.get_address_id(
                        content["addresses"]
                    )
                    break
                except (JSONError, KeyError, TypeError):
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

        if not self.data["addressId"]:
            return self.add_address()
        elif not self.data["customer"]["instagram_name"]:
            return self.add_instagram()
        else:
            return self.fetch_raffle()

    def add_address(self):
        self.logger.info("Adding address...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{RAFFLE_DOMAIN}/graphql",
                    body={
                        "operationName": "CreateCustomerAddress",
                        "variables": {
                            "firstname": self.task.parent.first_name,
                            "lastname": self.task.parent.last_name,
                            "street": list(filter(None, [self.task.parent.street, self.task.parent.house_number, self.task.parent.line_2])),
                            "postcode": self.task.parent.postcode,
                            "city": self.task.parent.city,
                            "country_code": self.task.parent.country,
                            "telephone": self.task.parent.full_phone
                        },
                        "query": "mutation CreateCustomerAddress($country_code: CountryCodeEnum!, $street: [String]!, $telephone: String, $postcode: String!, $city: String!, $firstname: String!, $lastname: String!, $company: String, $default_shipping: Boolean, $default_billing: Boolean, $region_id: Int) {\n  createCustomerAddress(\n    input: {country_code: $country_code, street: $street, telephone: $telephone, postcode: $postcode, city: $city, firstname: $firstname, lastname: $lastname, company: $company, default_shipping: $default_shipping, default_billing: $default_billing, region: {region_id: $region_id}}\n  ) {\n    id\n    region {\n      region\n      region_id\n      __typename\n    }\n    firstname\n    lastname\n    country_code\n    country_name\n    company\n    street\n    telephone\n    postcode\n    city\n    __typename\n  }\n}"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "*/*",
                        "content-type": "application/json",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{RAFFLE_DOMAIN}",
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
                    content = response.json()

                    if not content.get("errors"):
                        self.data["addressId"] = content["data"]["createCustomerAddress"]["id"]
                        break
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to add address"), self.delay()
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

        if not self.data["customer"]["instagram_name"]:
            return self.add_instagram()
        else:
            return self.fetch_raffle()

    def add_instagram(self):
        self.logger.info("Adding Instagram tag...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{RAFFLE_DOMAIN}/graphql",
                    body={
                        "operationName": "UpdateCustomer",
                        "variables": {
                            "firstname": self.task.parent.first_name or self.data["customer"]["firstname"],
                            "email": self.task.parent.email,
                            "instagram_name": self.task.parent.instagram
                        },
                        "query": "mutation UpdateCustomer($firstname: String!, $email: String!, $instagram_name: String!) {\n  updateCustomer(\n    input: {firstname: $firstname, email: $email, instagram_name: $instagram_name}\n  ) {\n    customer {\n      firstname\n      email\n      instagram_name\n      __typename\n    }\n    __typename\n  }\n}"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "*/*",
                        "content-type": "application/json",
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{RAFFLE_DOMAIN}",
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
                    content = response.json()

                    if not content.get("errors"):
                        break
                    elif "instagram_name isn't unique" in content["errors"][0]["message"]:
                        self.logger.error("Failed to add Instagram tag: Already in use")
                        return False
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to add Instagram tag"), self.delay()
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

        return self.fetch_raffle()

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
                    self.product.name = html.unescape(re.findall('"name":"(.*?)",', response.body)[0])
                    self.product.price = re.findall('"formatted_raffle_price":"(.*?)"', response.body)[0]
                    self.product.image = re.findall('"medium_image_url":"(.*?)"', response.body)[0]
                    self.product.size, self.data["sizeId"] = self.get_size(json.loads(
                        re.findall(r'"variants":(\[.*]),"configurable_options"', response.body)[0]
                    ))

                    self.data["turnstileToken"] = self.solve_turnstile(response)
                    break
                except (JSONError, IndexError, KeyError, ValueError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 500:
                self.logger.error("Failed to enter raffle: Raffle pulled"), self.delay()
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
                response = self.session.post(
                    f"https://{RAFFLE_DOMAIN}/graphql",
                    body={
                        "operationName": "RegisterCustomerForProductRaffle",
                        "variables": {
                            "customer_address_id": self.data["addressId"],
                            "product_id": self.data["sizeId"],
                            "hash": self.data["turnstileToken"]
                        },
                        "query": "mutation RegisterCustomerForProductRaffle($customer_address_id: Int!, $product_id: Int!, $hash: String!) {\n  registerCustomerForProductRaffle(\n    customer_address_id: $customer_address_id\n    product_id: $product_id\n    hash: $hash\n  )\n}"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "*/*",
                        "store": "eu_en",
                        "sec-ch-ua-mobile": "?0",
                        "content-type": "application/json",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "origin": f"https://{RAFFLE_DOMAIN}",
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
                    content = response.json()

                    if not content.get("errors"):
                        if content["data"]["registerCustomerForProductRaffle"]:
                            break
                        else:
                            raise KeyError
                    elif "already registered" in content["errors"][0]["message"]:
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

        self.logger.success("Successfully entered raffle")
        return True
