# -*- coding: utf-8 -*-
import random
import uuid
from common import http
from common.utils import sleep
from tasks.common import Logger
from tasks.common.classes import Task
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME, SHOPIFY_DOMAIN, SHOPIFY_KEY, API_DOMAIN, API_KEY, USER_AGENT


class GenerateAccount:
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

        self.data = {
            "deviceId": str(uuid.uuid4()).upper()
        }

    @staticmethod
    def delay():
        sleep(random.randint(1000, 2000) / 1000)

    def switch_proxy(self):
        self.session.set_proxy(
            self.task.proxies.get()
        )

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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{SHOPIFY_DOMAIN}/api/2021-10/graphql.json",
                    body={
                        "query": "mutation customerCreate($input: CustomerCreateInput!, $includeCustomerTags: Boolean!) {\n  customerCreate(input: $input) {\n    userErrors {\n      field\n      message\n    }\n    customer {\n      ...Customer\n    }\n    customerUserErrors {\n      field\n      message\n    }\n  }\n}\n\nfragment Customer on Customer {\n  ...SavedAddresses\n  metafields(first: 250) {\n    edges {\n      node {\n        ...Metafield\n      }\n    }\n  }\n  acceptsMarketing\n  createdAt\n  displayName\n  email\n  firstName\n  id\n  lastName\n  phone\n  tags @include(if: $includeCustomerTags)\n  updatedAt\n}\n\nfragment SavedAddresses on Customer {\n  addresses(first: 100) {\n    edges {\n      node {\n        ...Address\n      }\n    }\n  }\n  defaultAddress {\n    id\n  }\n}\n\nfragment Address on MailingAddress {\n  address1\n  address2\n  city\n  company\n  country\n  countryCodeV2\n  firstName\n  formatted(withCompany: true, withName: true)\n  formattedArea\n  id\n  lastName\n  latitude\n  longitude\n  name\n  phone\n  province\n  provinceCode\n  zip\n}\n\nfragment Metafield on Metafield {\n  createdAt\n  description\n  id\n  key\n  namespace\n  type\n  updatedAt\n  value\n}\n",
                        "variables": {
                            "input": {
                                "email": self.task.parent.email,
                                "firstName": self.task.parent.first_name,
                                "lastName": self.task.parent.last_name,
                                "password": self.task.parent.password,
                                "acceptsMarketing": False
                            },
                            "includeCustomerTags": True
                        },
                        "operationName": "customerCreate"
                    },
                    headers={
                        "accept": "application/json, text/plain, */*",
                        "content-type": "application/json",
                        "user-agent": None,
                        "x-shopify-storefront-access-token": SHOPIFY_KEY,
                        "accept-language": None,
                        "content-length": None,
                        "accept-encoding": "gzip, deflate, br"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    content = response.json()["data"]["customerCreate"]

                    if content["customer"]:
                        self.data["customerId"] = content["customer"]["id"]
                        break
                    elif content["userErrors"][0]["message"] == "Email has already been taken":
                        self.logger.error("Failed to generate account: Email already in use")
                        return False
                    else:
                        raise KeyError
                except (JSONError, KeyError, TypeError, IndexError):
                    self.logger.error("Failed to generate account"), self.delay()
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

        return self.log_in()

    def log_in(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{SHOPIFY_DOMAIN}/api/2021-10/graphql.json",
                    body={
                        "query": "mutation customerAccessTokenCreate($input: CustomerAccessTokenCreateInput!) {\n  customerAccessTokenCreate(input: $input) {\n    customerAccessToken {\n      accessToken\n      expiresAt\n    }\n    customerUserErrors {\n      code\n      field\n      message\n    }\n  }\n}\n",
                        "variables": {
                            "input": {
                                "email": self.task.parent.email,
                                "password": self.task.parent.password
                            }
                        },
                        "operationName": "customerAccessTokenCreate"
                    },
                    headers={
                        "accept": "application/json, text/plain, */*",
                        "content-type": "application/json",
                        "user-agent": None,
                        "x-shopify-storefront-access-token": SHOPIFY_KEY,
                        "accept-language": None,
                        "content-length": None,
                        "accept-encoding": "gzip, deflate, br"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["customerAccessToken"] = response.json()["data"]["customerAccessTokenCreate"]["customerAccessToken"]["accessToken"]
                    break
                except (JSONError, KeyError, TypeError):
                    self.logger.error("Failed to generate account"), self.delay()
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
                    f"https://{API_DOMAIN}/api/graphql",
                    body={
                        "query": "\n      mutation {\n        accessTokenCreate(input: {\n          shopifyCustomerId: \"%s\",\n          shopifyCustomerAccessToken: \"%s\"\n        }) {\n          accessToken {\n            accessToken\n            expiresAt\n          }\n        }\n      }" % (
                            self.data["customerId"], self.data["customerAccessToken"]
                        )
                    },
                    headers={
                        "content-type": "application/json",
                        "accept": "application/json, text/plain, */*",
                        "kith-shop-domain": SHOPIFY_DOMAIN,
                        "device-id": self.data["deviceId"],
                        "accept-language": None,
                        "accept-encoding": "gzip, deflate, br",
                        "origin": f"https://{API_DOMAIN}/api",
                        "content-length": None,
                        "user-agent": None,
                        "kith-api-key": API_KEY
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["accessToken"] = response.json()["data"]["accessTokenCreate"]["accessToken"]["accessToken"]
                    break
                except (JSONError, KeyError, TypeError):
                    self.logger.error("Failed to generate account"), self.delay()
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

        return self.add_date_of_birth()

    def add_date_of_birth(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{API_DOMAIN}/api/graphql",
                    body={
                        "query": "\n        mutation customerUpdate($input: CustomerUpdateInput!) {\n          customerUpdate(input: $input) {\n            customer {\n              \n  id\n  firstName\n  lastName\n  email\n  totalLoyaltyPoints\n  clothingLines\n  preferredApparelSize\n  preferredBrands\n  preferredCategories\n  preferredPantsSize\n  preferredShoesSize\n  loyaltyEnrolledAt\n  birthdate\n\n            }\n          }\n        }\n      ",
                        "variables": {
                            "input": {
                                "birthdate": self.task.parent.format_date_of_birth("%Y-%m-%d") + "T22:00:00.000Z"
                            }
                        }
                    },
                    headers={
                        "content-type": "application/json",
                        "accept": "application/json, text/plain, */*",
                        "kith-shop-domain": SHOPIFY_DOMAIN,
                        "longitude": "",
                        "device-id": self.data["deviceId"],
                        "latitude": "",
                        "accept-language": None,
                        "accept-encoding": "gzip, deflate, br",
                        "origin": f"https://{API_DOMAIN}/api",
                        "access-token": self.data["accessToken"],
                        "content-length": None,
                        "user-agent": None,
                        "kith-api-key": API_KEY
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    if not response.json().get("errors"):
                        break
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to generate account"), self.delay()
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

        if self.task.parent.is_address_loaded:
            return self.add_address()
        else:
            self.logger.success("Successfully generated account")
            return True

    def add_address(self):
        self.logger.info("Adding address...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{SHOPIFY_DOMAIN}/api/2021-10/graphql.json",
                    body={
                        "query": "mutation customerAddressCreate($customerAccessToken: String!, $address: MailingAddressInput!) {\n  customerAddressCreate(\n    customerAccessToken: $customerAccessToken\n    address: $address\n  ) {\n    customerAddress {\n      ...Address\n    }\n    customerUserErrors {\n      code\n      field\n      message\n    }\n  }\n}\n\nfragment Address on MailingAddress {\n  address1\n  address2\n  city\n  company\n  country\n  countryCodeV2\n  firstName\n  formatted(withCompany: true, withName: true)\n  formattedArea\n  id\n  lastName\n  latitude\n  longitude\n  name\n  phone\n  province\n  provinceCode\n  zip\n}\n",
                        "variables": {
                            "customerAccessToken": self.data["customerAccessToken"],
                            "address": {
                                "address1": self.task.parent.address,
                                "address2": self.task.parent.line_2,
                                "city": self.task.parent.city,
                                "country": self.task.parent.country,
                                "firstName": self.task.parent.first_name,
                                "lastName": self.task.parent.last_name,
                                "phone": self.task.parent.full_phone,
                                "province": self.task.parent.province,
                                "zip": self.task.parent.postcode
                            }
                        },
                        "operationName": "customerAddressCreate"
                    },
                    headers={
                        "accept": "application/json, text/plain, */*",
                        "content-type": "application/json",
                        "user-agent": None,
                        "x-shopify-storefront-access-token": SHOPIFY_KEY,
                        "accept-language": None,
                        "content-length": None,
                        "accept-encoding": "gzip, deflate, br"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    if response.json()["data"]["customerAddressCreate"]["customerAddress"]:
                        break
                    else:
                        raise KeyError
                except (JSONError, KeyError, TypeError):
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

        self.logger.success("Successfully generated account")
        return True
