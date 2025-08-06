# -*- coding: utf-8 -*-
import random
from common import http
from common.utils import sleep
from tasks.common import Logger
from tasks.common.classes import Task
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME, DOMAIN


class GenerateAccount:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = Logger(
            NAME, task.id, task.formatted_parent_id
        )

        self.session = http.Session(
            proxy=task.proxies.get()
        )

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
                response = self.session.get(
                    f"https://{DOMAIN}/en/",
                    headers={
                        "cache-control": "max-age=0",
                        "sec-ch-ua": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "sec-ch-ua-mobile": "?0",
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-dest": "empty",
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
                    f"https://{DOMAIN}/en/graphql/",
                    body={
                        "operationName": "Registration",
                        "variables": {
                            "input": {
                                "email": self.task.parent.email,
                                "password": self.task.parent.password,
                                "firstName": self.task.parent.first_name,
                                "lastName": self.task.parent.last_name,
                                "consents": [{
                                    "name": "privacy-policy-101",
                                    "value": True
                                }],
                                "externalLogin": None
                            },
                            "isCheckout": False
                        },
                        "query": "mutation Registration($input: CreateCustomerInput!, $isCheckout: Boolean!) {\n  response: CustomerOps {\n    create(input: $input) {\n      viewer {\n        ...ViewerFields\n        __typename\n      }\n      viewerEcommerce {\n        ...ViewerEcommerceFields\n        __typename\n      }\n      checkout @include(if: $isCheckout) {\n        contactForm {\n          ...ContactFormFields\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment ViewerFields on Customer {\n  id\n  email\n  phone\n  firstName\n  lastName\n  nickName\n  picture\n  customerLists {\n    ...CustomerListFields\n    __typename\n  }\n  registered\n  isVip\n  gender\n  age\n  loyaltyVouchers {\n    code\n    reductionAmount {\n      ...MoneyFields\n      __typename\n    }\n    minimalPrice {\n      ...MoneyFields\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment CustomerListFields on CustomerList {\n  id\n  uuid\n  name\n  text\n  isPublic\n  picture\n  votes\n  didViewerVote\n  productIds\n  tags {\n    ...CustomerListTagFields\n    __typename\n  }\n  __typename\n}\n\nfragment CustomerListTagFields on CustomerListTag {\n  id\n  name\n  __typename\n}\n\nfragment MoneyFields on Money {\n  amount\n  currency\n  __typename\n}\n\nfragment ViewerEcommerceFields on CustomerEcommerce {\n  address {\n    ...AddressFields\n    __typename\n  }\n  revenue\n  revenueCzk\n  revenueLastYear\n  revenueLastYearCzk\n  orders\n  ordersSuccessful\n  lastOrder\n  lastOrderSite\n  activeVouchers\n  customerType\n  __typename\n}\n\nfragment AddressFields on Address {\n  id\n  originId\n  alias\n  firstName\n  lastName\n  country {\n    ...CountryFields\n    __typename\n  }\n  city\n  street\n  streetNumber\n  postcode\n  phone\n  company\n  note\n  __typename\n}\n\nfragment CountryFields on Country {\n  isoCode\n  name\n  customFees\n  __typename\n}\n\nfragment ContactFormFields on ContactForm {\n  schema\n  type\n  redirectUrl\n  __typename\n}\n"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "*/*",
                        "sec-ch-ua-platform": None,
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "content-type": "application/json",
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{DOMAIN}/en/",
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

                    if not content.get("errors"):
                        break
                    elif content["errors"][0]["message"] == "Email is already registered":
                        self.logger.error("Failed to generate account: Email already in use")
                        return False
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}/en/graphql/",
                    body={
                        "operationName": "UpdateRegistration",
                        "variables": {
                            "input": {
                                "gender": "FEMALE" if self.task.parent.gender == "female" else "MALE",
                                "birthdate": {
                                    "day": self.task.parent.format_date_of_birth("%d"),
                                    "month": self.task.parent.format_date_of_birth("%m"),
                                    "year": self.task.parent.format_date_of_birth("%Y")
                                }
                            }
                        },
                        "query": "mutation UpdateRegistration($input: UpdateCustomerInput!) {\n  response: CustomerOps {\n    update(input: $input) {\n      viewer {\n        ...ViewerFields\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment ViewerFields on Customer {\n  id\n  email\n  phone\n  firstName\n  lastName\n  nickName\n  picture\n  customerLists {\n    ...CustomerListFields\n    __typename\n  }\n  registered\n  isVip\n  gender\n  age\n  loyaltyVouchers {\n    code\n    reductionAmount {\n      ...MoneyFields\n      __typename\n    }\n    minimalPrice {\n      ...MoneyFields\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment CustomerListFields on CustomerList {\n  id\n  uuid\n  name\n  text\n  isPublic\n  picture\n  votes\n  didViewerVote\n  productIds\n  tags {\n    ...CustomerListTagFields\n    __typename\n  }\n  __typename\n}\n\nfragment CustomerListTagFields on CustomerListTag {\n  id\n  name\n  __typename\n}\n\nfragment MoneyFields on Money {\n  amount\n  currency\n  __typename\n}\n"
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "accept": "*/*",
                        "sec-ch-ua-platform": None,
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "content-type": "application/json",
                        "origin": f"https://{DOMAIN}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{DOMAIN}/en/",
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

        self.logger.success("Successfully generated account")
        return True
