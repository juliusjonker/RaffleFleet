# -*- coding: utf-8 -*-
import random
import re
import html
import secrets
from urllib.parse import quote_plus
from common import http
from common.utils import sleep
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME, DOMAIN, COUNTRY_NAMES


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

        self.product = Product()
        self.data = {
            "trackerId": "64" + secrets.token_hex(11)
        }

    @staticmethod
    def delay():
        sleep(random.randint(1000, 2000) / 1000)

    def switch_proxy(self):
        self.session.set_proxy(
            self.task.proxies.get()
        )

    def get_size(self):
        sizes_in_range = [
            size for size in [
                4, 4.5, 5, 5.5,
                6, 6.5, 7, 7.5,
                8, 8.5, 9, 9.5,
                10, 10.5, 11, 11.5,
                12, 12.5, 13, 14
            ] if self.task.input.size_range.fits(size)
        ]

        if sizes_in_range:
            return str(random.choice(sizes_in_range))
        else:
            return ""

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
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "sec-fetch-site": "none",
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
                    self.product.name = html.unescape(re.findall('<meta property="og:title" content="(.*?) I', response.body)[0])
                    self.product.price = re.findall('<span itemprop="price" content=".*?">(.*?)</span>', response.body)[0]
                    self.product.image = re.findall('<meta property="og:image" content="(.*?)">', response.body)[0]
                    self.product.size = self.get_size()

                    self.data["clientId"] = re.findall("/eu6/client-script/' \+ '(.*?)'", response.body)[0]
                    break
                except IndexError:
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
            return self.enter_raffle()
        else:
            self.logger.error("Failed to enter raffle: No sizes in range")
            return False

    def enter_raffle(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://eu6-api.connectif.cloud/integration-type/system/scrippet-notification/{self.data['clientId']}",
                    body={
                        "entityInfo": {
                            "trackerId": self.data["trackerId"]
                        },
                        "events": [{
                            "type": "page-visit"
                        }],
                        "bannerPlaceholders": [],
                        "pageInfo": {
                            "categories": [],
                            "title": f"{self.product.name} I",
                            "keywords": [],
                            "tags": []
                        },
                        "browserInfo": {
                            "windowWidth": 1280,
                            "windowHeight": 672,
                            "screenHeight": 720,
                            "screenWidth": 1280,
                            "colorDepth": 24,
                            "cookieEnabled": True,
                            "language": "en",
                            "platform": "Win32",
                            "url": quote_plus(self.task.input.raffle["url"]),
                            "device": "desktop"
                        }
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "sec-ch-ua-platform": None,
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "content-type": "text/plain",
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
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    content = response.json()

                    self.data["formId"] = content["webContents"][1]["webContent"]["form"]["formId"]
                    self.data["contentId"] = content["webContents"][1]["webContent"]["id"]
                    self.data["workflowDefinitionId"] = content["webContents"][1]["workflowDefinitionId"]
                    self.data["sendUuid"] = content["webContents"][1]["sendUuid"]
                    break
                except (JSONError, KeyError, IndexError):
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
                    f"https://eu6-api.connectif.cloud/integration-type/system/scrippet-notification/{self.data['clientId']}",
                    body={
                        "entityInfo": {
                            "primaryKey": "",
                            "_name": "",
                            "_surname": "",
                            "_birthdate": "",
                            "_newsletterSubscriptionStatus": "",
                            "trackerId": self.data["trackerId"]
                        },
                        "events": [{
                            "type": "form-submitted",
                            "formId": self.data["formId"],
                            "contentId": self.data["contentId"],
                            "workflowDefinitionId": self.data["workflowDefinitionId"],
                            "payload": {
                                "submit": ""
                            },
                            "sendUuid": self.data["sendUuid"]
                        }],
                        "bannerPlaceholders": [],
                        "pageInfo": {
                            "categories": [],
                            "title": f"{self.product.name} I",
                            "keywords": [],
                            "tags": []
                        },
                        "browserInfo": {
                            "windowWidth": 1280,
                            "windowHeight": 672,
                            "screenHeight": 720,
                            "screenWidth": 1280,
                            "colorDepth": 24,
                            "cookieEnabled": True,
                            "language": "en",
                            "platform": "Win32",
                            "url": quote_plus(self.task.input.raffle["url"]),
                            "device": "desktop"
                        }
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "sec-ch-ua-platform": None,
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "content-type": "text/plain",
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
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    content = response.json()

                    self.data["formId"] = content["webContents"][0]["webContent"]["form"]["formId"]
                    self.data["contentId"] = content["webContents"][0]["webContent"]["id"]
                    self.data["workflowDefinitionId"] = content["webContents"][0]["workflowDefinitionId"]
                    self.data["sendUuid"] = content["webContents"][0]["sendUuid"]
                    break
                except (JSONError, KeyError, IndexError):
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
                    f"https://eu6-api.connectif.cloud/integration-type/system/scrippet-notification/{self.data['clientId']}",
                    body={
                        "entityInfo": {
                            "primaryKey": self.task.parent.email,
                            "_name": "",
                            "_surname": "",
                            "_birthdate": "",
                            "_newsletterSubscriptionStatus": "",
                            "trackerId": self.data["trackerId"]
                        },
                        "events": [{
                            "type": "form-submitted",
                            "formId": self.data["formId"],
                            "contentId": self.data["contentId"],
                            "workflowDefinitionId": self.data["workflowDefinitionId"],
                            "payload": {
                                "email": self.task.parent.email,
                                "Nombre": self.task.parent.full_name,
                                "Direccion": self.task.parent.address,
                                "Ciudad": self.task.parent.city,
                                "Provincia": self.task.parent.province,
                                "CP": self.task.parent.postcode,
                                "Pais": COUNTRY_NAMES.get(self.task.parent.country, "otro"),
                                "Telefono": self.task.parent.full_phone,
                                "cumple": self.task.parent.format_date_of_birth("%Y-%d-%m") + "T17:00:00.000Z",
                                "Instagram": self.task.parent.instagram,
                                "Talla": self.product.size,
                                "sexo": "mujer" if self.task.parent.gender == "female" else "hombre",
                                "privacidad": "si",
                                "idioma": "ingles",
                                "acepta_suscripcion": "si",
                                "submit": ""
                            },
                            "sendUuid": self.data["sendUuid"]
                        }],
                        "bannerPlaceholders": [],
                        "pageInfo": {
                            "categories": [],
                            "title": f"{self.product.name} I",
                            "keywords": [],
                            "tags": []
                        },
                        "browserInfo": {
                            "windowWidth": 1280,
                            "windowHeight": 672,
                            "screenHeight": 720,
                            "screenWidth": 1280,
                            "colorDepth": 24,
                            "cookieEnabled": True,
                            "language": "en",
                            "platform": "Win32",
                            "url": quote_plus(self.task.input.raffle["url"]),
                            "referer": "",
                            "device": "desktop"
                        }
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "sec-ch-ua-platform": None,
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "content-type": "text/plain",
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
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    if not response.json()["errors"]:
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
