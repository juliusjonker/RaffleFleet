# -*- coding: utf-8 -*-
import random
import uuid
from common import http
from common.utils import sleep
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME, SHOPIFY_DOMAIN, SHOPIFY_KEY, API_DOMAIN, API_KEY, USER_AGENT, LOCATIONS


class CheckRaffleResult:
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

        self.product = Product(
            name=task.input.raffle["productName"]
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

    def get_raffle_result(self, content):
        if not content["drawingEntry"]:
            return None

        self.product.price = "€ " + content["drawingEntry"]["variant"]["price"]["amount"]
        self.product.image = content["product"]["image"]["src"]
        self.product.size = content["drawingEntry"]["variant"]["title"]

        if content["drawingEntry"]["store"]:
            self.data["location"] = self.get_location(
                content["drawingEntry"]["store"]["id"]
            )

        if content["drawingEntry"]["status"] == "WON":
            return "won"
        elif content["drawingEntry"]["status"] == "LOST":
            return "lost"
        else:
            return "pending"

    @staticmethod
    def get_location(location_id):
        for location in LOCATIONS:
            if location["id"] == location_id:
                return location

    def execute(self):
        status = self.data["status"] if self.log_in() else "failed"

        if status == "won":
            webhooks.Win(
                NAME, self.product, self.task.parent, self.session.proxy,
                location=self.data.get("location", {}).get("formattedName")
            ).send()

        self.task.manager.increment(
            status,
            task=self.task,
            location=self.data.get("location", {}).get("name", ""),
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
                    content = response.json()["data"]["customerAccessTokenCreate"]

                    if content["customerAccessToken"]:
                        self.data["customerAccessToken"] = content["customerAccessToken"]["accessToken"]
                        break
                    elif content["customerUserErrors"][0]["message"] == "Unidentified customer":
                        self.logger.error("Failed to log in: Invalid credentials")
                        return False
                    else:
                        raise KeyError
                except (JSONError, KeyError, IndexError, TypeError):
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
                    f"https://{SHOPIFY_DOMAIN}/api/2021-10/graphql.json",
                    body={
                        "query": "query customer($customerAccessToken: String!, $includeCustomerTags: Boolean!) {\n  customer(customerAccessToken: $customerAccessToken) {\n    ...Customer\n  }\n}\n\nfragment Customer on Customer {\n  ...SavedAddresses\n  metafields(first: 250) {\n    edges {\n      node {\n        ...Metafield\n      }\n    }\n  }\n  acceptsMarketing\n  createdAt\n  displayName\n  email\n  firstName\n  id\n  lastName\n  phone\n  tags @include(if: $includeCustomerTags)\n  updatedAt\n}\n\nfragment SavedAddresses on Customer {\n  addresses(first: 100) {\n    edges {\n      node {\n        ...Address\n      }\n    }\n  }\n  defaultAddress {\n    id\n  }\n}\n\nfragment Address on MailingAddress {\n  address1\n  address2\n  city\n  company\n  country\n  countryCodeV2\n  firstName\n  formatted(withCompany: true, withName: true)\n  formattedArea\n  id\n  lastName\n  latitude\n  longitude\n  name\n  phone\n  province\n  provinceCode\n  zip\n}\n\nfragment Metafield on Metafield {\n  createdAt\n  description\n  id\n  key\n  namespace\n  type\n  updatedAt\n  value\n}\n",
                        "variables": {
                            "customerAccessToken": self.data["customerAccessToken"],
                            "includeCustomerTags": True
                        },
                        "operationName": "customer"
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
                    self.data["customerId"] = response.json()["data"]["customer"]["id"]
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
        return self.fetch_raffle_result()

    def fetch_raffle_result(self):
        self.logger.info("Checking raffle result...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{API_DOMAIN}/api/graphql",
                    body={
                        "query": "\n        query {\n          drawing(id: \"%s\") {\n            \n  id\n  title\n  availabilityType\n  drawingEntry {\n    \n  id\n  status\n  store {\n    \n  id\n  address {\n    \n  city\n  countryCode\n  latitude\n  lineOne\n  lineTwo\n  longitude\n  phone\n  stateCode\n  zip\n\n  }\n  name\n  type\n  winningRadius\n\n  }\n  variant {\n    \n  id\n  option1\n  price {\n    \n  amount\n\n  }\n  sku\n  title\n\n  }\n\n  }\n  product {\n    \n  id\n  bodyHtml\n  handle\n  image {\n    \n  src\n\n  }\n  images {\n    \n  src\n\n  }\n  title\n  variants {\n    nodes {\n      \n  id\n  option1\n  price {\n    \n  amount\n\n  }\n  title\n\n    }\n  }\n\n  }\n  startAt\n  endAt\n  sellingPlan {\n    \n  id\n\n  }\n  stores {\n    edges {\n      \n  pickupInstructions\n  node {\n    \n  id\n  address {\n    \n  city\n  latitude\n  lineOne\n  longitude\n  stateCode\n  zip\n\n  }\n  name\n  type\n  winningRadius\n\n  }\n\n    }\n  }\n\n          }\n        }" % (
                            self.task.input.raffle["id"]
                        ),
                        "variables": {}
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
                    self.data["status"] = self.get_raffle_result(
                        response.json()["data"]["drawing"]
                    )
                    break
                except (JSONError, KeyError, TypeError):
                    self.logger.error("Failed to check raffle result"), self.delay()
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

        if self.data["status"] == "won":
            self.logger.success("Checked raffle result: Won")
            return True
        elif self.data["status"] == "lost":
            self.logger.info("Checked raffle result: Lost")
            return True
        elif self.data["status"] == "pending":
            self.logger.error("Failed to check raffle result: Awaiting draw")
            return False
        else:
            self.logger.error("Failed to check raffle result: No entry found")
            return False
