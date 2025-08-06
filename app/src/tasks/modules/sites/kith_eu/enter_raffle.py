# -*- coding: utf-8 -*-
import random
import re
import uuid
import secrets
from datetime import datetime, timezone
from common import http
from common.utils import sleep, size_to_float
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, JSONError
from tasks.hooks import captcha
from .constants import NAME, SHOPIFY_DOMAIN, SHOPIFY_KEY, SHOPIFY_RAFFLE_DOMAIN, SHOPIFY_RAFFLE_KEY, API_DOMAIN, API_KEY, USER_AGENT, HCAPTCHA_SITE_KEY, COUNTRY_IDS


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

        self.captcha = captcha.Solver(
            self.logger, "h", SHOPIFY_RAFFLE_DOMAIN, HCAPTCHA_SITE_KEY
        )

        self.product = Product()
        self.data = {
            "deviceId": str(uuid.uuid4()).upper(),
            "googleClientId": f"{random.randint(10000000, 1000000000)}.{random.randint(10000000, 1000000000)}.{random.randint(100, 999)}"
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
            close_datetime, "%Y-%m-%dT%H:%M:%S%z"
        ).astimezone(timezone.utc) < datetime.now(timezone.utc)

    @staticmethod
    def get_address(default_address, addresses):
        if not default_address:
            return {}

        for address in addresses:
            if address["node"]["id"] == default_address["id"]:
                return address["node"]
        else:
            return {}

    def get_size(self, sizes):
        sizes_in_range = []
        for size_data in sizes:
            size = size_data["title"]
            if self.task.input.size_range.fits(size_to_float(size)):
                sizes_in_range.append((
                    size, size_data["id"]
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
                    content = response.json()["data"]["customer"]

                    self.data["customerId"] = content["id"]
                    self.data["address"] = self.get_address(
                        content["defaultAddress"], content["addresses"]["edges"]
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
        return self.fetch_raffle()

    def fetch_raffle(self):
        self.logger.info("Entering raffle...")

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
                    content = response.json()

                    if content["data"]:
                        content = content["data"]["drawing"]

                        if self.is_raffle_closed(content["endAt"]):
                            self.logger.error("Failed to enter raffle: Raffle closed")
                            return False
                        elif content["drawingEntry"]:
                            self.logger.error("Failed to enter raffle: Already entered")
                            return False

                        self.product.name = content["product"]["title"]
                        self.product.price = "€ " + content["product"]["variants"]["nodes"][0]["price"]["amount"]
                        self.product.image = content["product"]["image"]["src"]
                        self.product.size, self.data["sizeId"] = self.get_size(
                            content["product"]["variants"]["nodes"]
                        )
                        break
                    else:
                        self.logger.error("Failed to enter raffle: Raffle closed")
                        return False
                except (JSONError, KeyError, IndexError, ValueError, TypeError):
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
            return self.initiate_checkout()
        else:
            self.logger.error("Failed to enter raffle: No sizes in range")
            return False

    def initiate_checkout(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{SHOPIFY_RAFFLE_DOMAIN}/api/unstable/graphql.json",
                    body={
                        "query": "\n        mutation cartCreate($input: CartInput!) {\n          cartCreate(input: $input) {\n            cart {\n              id\n              checkoutUrl\n            }\n          }\n        }\n      ",
                        "variables": {
                            "input": {
                                "buyerIdentity": {
                                    "email": self.task.parent.email
                                },
                                "lines": [{
                                    "attributes": [{
                                        "key": "_mac_hash",
                                        "value": secrets.token_hex(32)
                                    }, {
                                        "key": "email",
                                        "value": self.task.parent.email
                                    }, {
                                        "key": "title",
                                        "value": self.product.name.split(" -")[0]
                                    }],
                                    "merchandiseId": self.data["sizeId"],
                                    "quantity": 1
                                }]
                            }
                        }
                    },
                    headers={
                        "accept": "application/json, text/plain, */*",
                        "content-type": "application/json",
                        "user-agent": None,
                        "x-shopify-storefront-access-token": SHOPIFY_RAFFLE_KEY,
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
                    self.data["checkoutUrl"] = response.json()["data"]["cartCreate"]["cart"]["checkoutUrl"].replace(r"\/", "/")
                    break
                except (JSONError, KeyError, TypeError):
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
                    self.data["checkoutUrl"],
                    headers={
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "user-agent": None,
                        "accept-language": None,
                        "accept-encoding": "gzip, deflate, br"
                    },
                    allow_redirects=False
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["merchantCartToken"] = response.headers["location"].split("/")[-1]
                    break
                except KeyError:
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
                    f"https://{SHOPIFY_RAFFLE_DOMAIN}/cart/update.js",
                    body={
                        "attributes[lang]": "en",
                        "attributes[Invoice Language]": "en"
                    },
                    headers={
                        "accept": "*/*",
                        "content-type": "application/x-www-form-urlencoded",
                        "origin": f"https://{SHOPIFY_RAFFLE_DOMAIN}",
                        "content-length": None,
                        "accept-language": None,
                        "user-agent": None,
                        "accept-encoding": "gzip, deflate, br"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                self.data["cartData"] = response.body
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
                    "https://gem-fs.global-e.com/1/Checkout/GetCartToken",
                    params={
                        "merchantUniqueId": "708"
                    },
                    body={
                        "MerchantCartToken": self.data["merchantCartToken"],
                        "CountryCode": self.task.parent.country if self.task.parent.is_address_loaded else self.data["address"].get("countryCodeV2"),
                        "CurrencyCode": "EUR",
                        "CultureCode": "en-GB",
                        "MerchantId": "708",
                        "WebStoreCode": "kith-eu-drawings",
                        "GetCartTokenUrl": "https://gem-fs.global-e.com/1",
                        "ClientCartContent": self.data["cartData"],
                        "AdditionalCartData": "%5B%5D",
                        "CaptchaResponseToken": self.captcha.solve()
                    },
                    headers={
                        "accept": "*/*",
                        "content-type": "application/x-www-form-urlencoded",
                        "origin": f"https://{SHOPIFY_RAFFLE_DOMAIN}",
                        "content-length": None,
                        "accept-language": None,
                        "user-agent": None,
                        "referer": f"https://{SHOPIFY_RAFFLE_DOMAIN}/",
                        "accept-encoding": "gzip, deflate, br"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["cartToken"] = response.json()["CartToken"]
                    break
                except (JSONError, KeyError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 500:
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

        return self.fetch_checkout()

    def fetch_checkout(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://fs708.global-e.com/Checkout/v2/8rxx/{self.data['cartToken']}",
                    params={
                        "checkoutId": self.data["merchantCartToken"],
                        "glCountry": self.task.parent.country if self.task.parent.is_address_loaded else self.data["address"].get("countryCodeV2"),
                        "glCurrency": "EUR",
                        "webStoreCode": "kith-eu-drawings",
                        "gaSesID": self.data["googleClientId"],
                        "chkcuid": str(uuid.uuid4()),
                        "isNECAllowed": "true",
                        "applepay": "true",
                        "_vwo_store": "",
                        "vph": "721",
                        "ift": "244"
                    },
                    headers={
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "accept-encoding": "gzip, deflate, br",
                        "user-agent": None,
                        "accept-language": None,
                        "referer": f"https://{SHOPIFY_RAFFLE_DOMAIN}/"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["cultureId"] = re.findall('cultureID: "(.*?)"', response.body)[0]
                    self.data["gatewayId"] = re.findall('id="gatewayId" value="(.*?)"', response.body)[0]
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
                response = self.session.get(
                    f"https://secure-fs.global-e.com/payments/CreditCardForm/{self.data['cartToken']}/{self.data['gatewayId']}",
                    headers={
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "accept-encoding": "gzip, deflate, br",
                        "user-agent": None,
                        "accept-language": None,
                        "referer": "https://fs708.global-e.com/"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["paymentMode"] = re.findall(r'\?mode=(.*?)"', response.body)[0]
                    self.data["paymentToken"] = re.findall('id="UrlStructureTokenEncoded" value="(.*?)"', response.body)[0]
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

        return self.submit_order()

    def submit_order(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://fs708.global-e.com/checkoutv2/save/8rxx/{self.data['cartToken']}",
                    body={
                        "CheckoutData.CartToken": self.data["cartToken"],
                        "CheckoutData.CultureID": self.data["cultureId"],
                        "CheckoutData.GASessionsID": self.data["googleClientId"],
                        "CheckoutData.IsVirtualOrder": "False",
                        "CheckoutData.ExternalData.CurrentGatewayId": self.data["gatewayId"],
                        "CheckoutData.ForterToken": uuid.uuid4().hex + "___undefined43__tt",
                        "CheckoutData.ExternalData.AllowedCharsRegex": r"""^[A-Za-z0-9,""'`\s@+&%$#\*\(\)\[\]._\-\s\\/]*$""",
                        "CheckoutData.ExternalData.UnsupportedCharactersErrorTipTimeout": "15000",
                        "CheckoutData.EnableUnsupportedCharactersValidation": "True",
                        "CheckoutData.BillingFirstName": self.task.parent.first_name or self.data["address"].get("firstName"),
                        "CheckoutData.BillingLastName": self.task.parent.last_name or self.data["address"].get("lastName"),
                        "CheckoutData.Email": self.task.parent.email,
                        "CheckoutData.BillingCountryID": COUNTRY_IDS.get(self.task.parent.country if self.task.parent.is_address_loaded else self.data["address"].get("countryCodeV2")),
                        "CheckoutData.BillingAddress1": self.task.parent.address if self.task.parent.is_address_loaded else self.data["address"].get("address1"),
                        "CheckoutData.BillingAddress2": self.task.parent.line_2 if self.task.parent.is_address_loaded else self.data["address"].get("address2"),
                        "CheckoutData.BillingCity": self.task.parent.city if self.task.parent.is_address_loaded else self.data["address"].get("city"),
                        "CheckoutData.BillingCountyID": "",
                        "CheckoutData.BillingZIP": self.task.parent.postcode if self.task.parent.is_address_loaded else self.data["address"].get("zip"),
                        "CheckoutData.BillingStateID": "",
                        "CheckoutData.BillingPhone": self.task.parent.full_phone or self.data["address"].get("phone"),
                        "CheckoutData.OffersFromMerchant": "false",
                        "CheckoutData.ShippingType": "ShippingSameAsBilling",
                        "CheckoutData.ShippingFirstName": "",
                        "CheckoutData.ShippingLastName": "",
                        "CheckoutData.ShippingCountryID": COUNTRY_IDS.get(self.task.parent.country if self.task.parent.is_address_loaded else self.data["address"].get("countryCodeV2")),
                        "CheckoutData.ShippingAddress1": "",
                        "CheckoutData.ShippingAddress2": "",
                        "CheckoutData.ShippingCity": "",
                        "CheckoutData.ShippingCountyID": "",
                        "CheckoutData.ShippingZIP": "",
                        "CheckoutData.ShippingStateID": "",
                        "CheckoutData.ShippingPhone": "",
                        "CheckoutData.SelectedShippingOptionID": "2728",
                        "CheckoutData.SelectedTaxOption": "3",
                        "ioBlackBox": "",
                        "CheckoutData.StoreID": "0",
                        "CheckoutData.AddressVerified": "true",
                        "CheckoutData.SelectedPaymentMethodID": "2",
                        "CheckoutData.CurrentPaymentGayewayID": self.data["gatewayId"],
                        "CheckoutData.MerchantID": "708",
                        "CheckoutData.MerchantSupportsAddressName": "false",
                        "CheckoutData.MultipleAddressesMode": "true",
                        "CheckoutData.CollectionPointZip": "",
                        "CheckoutData.UseAvalara": "false",
                        "CheckoutData.IsAvalaraLoaded": "false",
                        "CheckoutData.IsUnsupportedRegion": "",
                        "CheckoutData.IsShowTitle": "false",
                        "CheckoutData.IsBillingSavedAddressUsed": "false",
                        "CheckoutData.IsShippingSavedAddressUsed": "false",
                        "CheckoutData.SaveBillingCountryOnChange": "false",
                        "CheckoutData.DisplayInternatioanlPrefixInCheckout": "false",
                        "CheckoutData.IsValidationMessagesV2": "false",
                        "CheckoutData.IgnoreBillingCityRegionValidation": "false",
                        "CheckoutData.IgnoreShippingCityRegionValidation": "false",
                        "CheckoutData.DoLightSave": "false"
                        },
                    headers={
                        "accept": "*/*",
                        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "origin": "https://fs708.global-e.com",
                        "referer": "https://fs708.global-e.com/",
                        "content-length": None,
                        "x-requested-with": "XMLHttpRequest",
                        "accept-language": None,
                        "user-agent": None,
                        "accept-encoding": "gzip, deflate, br"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    if response.json()["Success"]:
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
                    f"https://secure-fs.global-e.com/1/Payments/HandleCreditCardRequestV2/8rxx/{self.data['cartToken']}",
                    params={
                        "mode": self.data["paymentMode"]
                    },
                    body={
                        "PaymentData.cardNum": self.task.parent.card_number,
                        "PaymentData.cardExpiryMonth": self.task.parent.card_month,
                        "PaymentData.cardExpiryYear": self.task.parent.card_year,
                        "PaymentData.cvdNumber": self.task.parent.card_cvc,
                        "PaymentData.checkoutV2": "true",
                        "PaymentData.cartToken": self.data["cartToken"],
                        "PaymentData.gatewayId": self.data["gatewayId"],
                        "PaymentData.paymentMethodId": "2",
                        "PaymentData.machineId": "04005uUg2XpweF4Xk1Rjuv1iJgWxIe7xNABi4fWLoKuCjDO1I7X1XkVbR56yHWIulRE2G351wfp+MZWAa+qm7VSS+5sZhQDshHSvL1nHQLC7Q6NpxQ17D0VyS32SOzubmcBOVtcqUhwQqm2+q1yRomE8gdJgJwx6DJQN6MhdxXFjNMONtzQkYkqXLxENFx9zvRxsZ3l9B48egwmA/Z2/3sxVoIz8/yX9hyTE1qBH7CuG2cYMgog1WtCs0txF6Ft8Ea5XAHtlrOPcolu5kVyEZ5Un1A1zM3XireXLCHex/Y96FFfSctR6oPvoc/HBQm916StCCqyk8Swyp3swoIZX8wsVy6BdqpuIf1GUQWKoyaXf6ez3bcvkLpMW3hLrEFkneaGzTEVdGJlxBwBigDt9U/mISLb8/k+2x38WV6i8/tb5alAK/XRNo3H5dMWXon2LwGQs2gTNO8dhxZkwx2tcx5lGRWLQVG6Wu5dBA/z8Qi7K1AaNm0URxgdANnwB7SaH85JmyAfUMZ5LKFqFl81CC76WZKXakoCa7XCW4IhJrOz08Pzf+x4pw6W9esbGEpq7CoRYvFQ3SxgXyvTx/y4JwLTE4Nxv4KowoTq9ZHvy+/OUGsT6WhmJ6uI+FEzI+mPNi65XSGFq0WvDIDWnFBXTiQwVA5aGaf80/3iSPOYe85lXFCR4CjSd/Iq56FG3EcsazU/5If+SxsuUFwyKCknSJs1HLUgFh/6610IF77A/AHthzIQI07p4tGGHBe8mR20/oWqfLQ/2q0KAoA7AqvQx/6iBZvdaZ+9WVICZ0gTRe5N7ohatv344o3LTxtT16TeM5diEHf7WUtiodkTjCCAKQfEFHFRukDiyEjh0DtPq/jlyS0syYsf4CdEBhoVWXukFPEWMqlr028/3Pq++K9chwFYF5/rJz/fklocMPdBNTYCwBLgpGhIgQd5Se6NraJ8f05ZbpY8zgvKx3yMYBe+MfSZLUP8V8c+YhydhouMC+WQLqLHkbAxyEijNfQl2Y1Y/iacvDms3kIW/qtFnEbyxrf+VHGg48BAA46MBNTqbLPtogM+/Nx52mfwOuxkwfCqvl92YR6kKmB7k4E5HkpM/NABtMh0mQH/S4Yh6tQzpGfcm0cR8X2Fd1ngNFHkcp1KVtDAZPEk1yzjtuf9+QzWUBYfzUDKx4PQbX9OHEQi+wlGoZ8X2ykV3stOnGIBUY5+4temb2HYF5oyZHJfDms1GGMwW+VLB6M5fl2EoZiuy7XetzhEJuvK70bwBpFnpZHcFvk9KV608jXt72GQLzEygEgAdKRmFnPAJmrzwgK2zovlvW7fSZWSyVUZTjmSzxi/BlHaoVcDfh/1hjpTauZbXWwKF2KO8Uw58cTAJSBUfNzCegNAH8667QusvUt6Z4CZwGXTFnEaTBokTnEweRdifL779yInUPcpWx6102Nl9AN2bpEu7BT/PmONpaovNztgRLjrNn8QSmwEAUevDseOU8OruqwFC6lzi8d1j",
                        "PaymentData.createTransaction": "true",
                        "PaymentData.checkoutCDNEnabled": "value",
                        "PaymentData.recapchaToken": "",
                        "PaymentData.recapchaTime": "",
                        "PaymentData.customerScreenColorDepth": "32",
                        "PaymentData.customerScreenWidth": "414",
                        "PaymentData.customerScreenHeight": "896",
                        "PaymentData.customerTimeZoneOffset": "0",
                        "PaymentData.customerLanguage": "en-GB",
                        "PaymentData.UrlStructureTokenEncoded": self.data["paymentToken"],
                        "PaymentData.IsValidationMessagesV2": "false",
                        "PaymentData.HCaptchaEKey": "",
                        "PaymentData.HCaptchaResponse": ""
                    },
                    headers={
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "content-type": "application/x-www-form-urlencoded",
                        "origin": "https://secure-fs.global-e.com",
                        "content-length": None,
                        "accept-language": None,
                        "user-agent": None,
                        "referer": "https://secure-fs.global-e.com/",
                        "accept-encoding": "gzip, deflate, br"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                if "finalizeProcess = true" in response.body:
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    "https://fs708.global-e.com/checkoutv2/complete",
                    body={
                        "CartToken": self.data["cartToken"],
                        "trxStatus": "Authorized",
                        "isFrd": False
                    },
                    headers={
                        "content-type": "application/json; charset=utf-8",
                        "accept": "text/html, */*; q=0.01",
                        "x-requested-with": "XMLHttpRequest",
                        "accept-language": None,
                        "accept-encoding": "gzip, deflate, br",
                        "origin": "https://fs708.global-e.com",
                        "user-agent": None,
                        "referer": "https://fs708.global-e.com/",
                        "cultureid": self.data["cultureId"],
                        "content-length": None
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    if response.json()["IsSuccess"]:
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
