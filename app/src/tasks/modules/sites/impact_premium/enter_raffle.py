# -*- coding: utf-8 -*-
import random
import re
import json
import html
from common import http
from common.utils import sleep, size_to_float
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Product
from tasks.common.errors import HTTPError, CloudflareError, JSONError
from tasks.hooks import cloudflare, captcha
from .constants import NAME, DOMAIN, RECAPTCHA_SITE_KEY, COUNTRY_IDS


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

        self.captcha = captcha.Solver(
            self.logger, "v2", DOMAIN, RECAPTCHA_SITE_KEY
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
        for size_id, size_data in sizes:
            size = size_data.split(" EU")[0].replace(",", ".")
            if self.task.input.size_range.fits(size_to_float(size)):
                sizes_in_range.append((
                    size, f"{size_id}|{size_data}"
                ))

        if sizes_in_range:
            return random.choice(sizes_in_range)
        else:
            return "", ""

    def get_address_id(self, addresses):
        if not addresses:
            return None

        blueprint = {
            "firstname": self.task.parent.first_name.lower().replace(" ", ""),
            "lastname": self.task.parent.last_name.lower().replace(" ", ""),
            "address1": self.task.parent.address.lower().replace(" ", ""),
            "address2": self.task.parent.line_2.lower().replace(" ", ""),
            "postcode": self.task.parent.postcode.lower().replace(" ", ""),
            "city": self.task.parent.city.lower().replace(" ", ""),
            "id_country": COUNTRY_IDS.get(self.task.parent.country),
            "phone": self.task.parent.full_phone.lower().replace(" ", "")
        }

        for address_id, address in addresses.items():
            if self.task.parent.is_address_loaded:
                for key, value in blueprint.items():
                    if address[key].lower().replace(" ", "") != value:
                        break
                else:
                    return address_id
            else:
                return address_id

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
                    f"https://{DOMAIN}/connexion",
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
            except (HTTPError, CloudflareError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                break
            else:
                self.logger.error((
                    f"Request failed: {response.status} - {response.reason}",
                    "switching proxy" if response.status in [401, 403, 429] else None
                )), self.delay()
                if response.status in [401, 403, 429]:
                    self.switch_proxy()
                error_count += 1
                continue
        else:
            return False

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}/connexion",
                    body={
                        "back": "",
                        "email": self.task.parent.email,
                        "password": self.task.parent.password,
                        "submitLogin": "1"
                    },
                    headers={
                        "content-length": None,
                        "cache-control": "max-age=0",
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "origin": f"https://{DOMAIN}",
                        "content-type": "application/x-www-form-urlencoded",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
                        "referer": f"https://{DOMAIN}/connexion",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    },
                    allow_redirects=False
                )
            except (HTTPError, CloudflareError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                if response.headers.get("location", "").endswith(f"{DOMAIN}/"):
                    break
                elif "Échec d'authentification" in response.body:
                    self.logger.error("Failed to log in: Invalid credentials")
                    return False
                else:
                    self.logger.error("Failed to log in"), self.delay()
                    error_count += 1
                    continue
            else:
                self.logger.error((
                    f"Request failed: {response.status} - {response.reason}",
                    "switching proxy" if response.status in [401, 403, 429] else None
                )), self.delay()
                if response.status in [401, 403, 429]:
                    self.switch_proxy()
                error_count += 1
                continue
        else:
            return False

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/mon-compte",
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
            except (HTTPError, CloudflareError) as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["customerId"] = re.findall('psgdpr_id_customer = "(.*?)"', response.body)[0]
                    self.data["customer"] = json.loads(re.findall('"customer":(.*?),"language"', response.body)[0])
                    self.data["addressId"] = self.get_address_id(
                       self.data["customer"]["addresses"]
                    )
                    break
                except (JSONError, IndexError, KeyError):
                    self.logger.error("Failed to log in"), self.delay()
                    error_count += 1
                    continue
            else:
                self.logger.error((
                    f"Request failed: {response.status} - {response.reason}",
                    "switching proxy" if response.status in [401, 403, 429] else None
                )), self.delay()
                if response.status in [401, 403, 429]:
                    self.switch_proxy()
                error_count += 1
                continue
        else:
            return False

        self.logger.success("Successfully logged in")

        if self.data["addressId"]:
            return self.fetch_raffle()
        else:
            return self.add_address()

    def add_address(self):
        self.logger.info("Adding address...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/adresse",
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
                        "referer": f"https://{DOMAIN}/mon-compte",
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
                    self.data["token"] = re.findall('name="token" value="(.*?)"', response.body)[0]
                    break
                except IndexError:
                    self.logger.error("Failed to add address"), self.delay()
                    error_count += 1
                    continue
            else:
                self.logger.error((
                    f"Request failed: {response.status} - {response.reason}",
                    "switching proxy" if response.status in [401, 403, 429] else None
                )), self.delay()
                if response.status in [401, 403, 429]:
                    self.switch_proxy()
                error_count += 1
                continue
        else:
            return False

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}/adresse?id_address=0",
                    body={
                        "back": "",
                        "token": self.data["token"],
                        "alias": "",
                        "firstname": self.task.parent.first_name,
                        "lastname": self.task.parent.last_name,
                        "company": "",
                        "vat_number": "",
                        "address1": self.task.parent.address,
                        "address2": self.task.parent.line_2,
                        "postcode": self.task.parent.postcode,
                        "city": self.task.parent.city,
                        "id_country": COUNTRY_IDS.get(self.task.parent.country),
                        "phone": self.task.parent.full_phone,
                        "submitAddress": "1"
                    },
                    headers={
                        "content-length": None,
                        "cache-control": "max-age=0",
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "origin": f"https://{DOMAIN}",
                        "content-type": "application/x-www-form-urlencoded",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
                        "referer": f"https://{DOMAIN}/adresse",
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
                    if "Vos adresses" in response.body:
                        self.data["addressId"] = re.findall('class="address" data-id-address="(.*?)"', response.body)[-1]
                        break
                    else:
                        raise IndexError
                except IndexError:
                    self.logger.error("Failed to add address"), self.delay()
                    error_count += 1
                    continue
            else:
                self.logger.error((
                    f"Request failed: {response.status} - {response.reason}",
                    "switching proxy" if response.status in [401, 403, 429] else None
                )), self.delay()
                if response.status in [401, 403, 429]:
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
                        "sec-fetch-site": "same-origin",
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
                    self.product.name = html.unescape(re.findall('<h1 style="text-align: center; background-color: #ffffff;"><strong>(.*?) <br', response.body)[0])
                    self.product.price = re.findall('<h3 style="text-align: center; background-color: #ffffff;">(.*?)</h3>', response.body)[0]
                    self.product.image = re.findall('data-eosrc="(.*?)" alt="concours"', response.body)[0]
                    self.product.size, self.data["sizeId"] = self.get_size(
                        json.loads(re.findall(r"CForm_pointures = JSON\.parse\('(.*?)'\)", response.body)[0])
                    )

                    self.data["productId"] = re.findall('type="hidden" value="(.*?)" name="fid"', response.body)[0]
                    break
                except (JSONError, IndexError, ValueError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 404:
                self.logger.error("Failed to enter raffle: Raffle closed")
                return False
            else:
                self.logger.error((
                    f"Request failed: {response.status} - {response.reason}",
                    "switching proxy" if response.status in [401, 403, 429] else None
                )), self.delay()
                if response.status in [401, 403, 429]:
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
                    self.task.input.raffle["url"],
                    body={
                        "c_c_pointure": self.data["sizeId"],
                        "c_c_name": self.task.parent.last_name or self.data["customer"]["lastname"],
                        "c_c_prenom": self.task.parent.first_name or self.data["customer"]["firstname"],
                        "c_c_instagram": self.task.parent.instagram,
                        "c_c_adresse": self.data["addressId"],
                        "c_c_myemail": self.task.parent.email,
                        "c_c_livraison": "Envoi Postal",
                        "g-recaptcha-response": self.captcha.solve(),
                        "submitform": "Valider mon inscription",
                        "c_c_user_id": self.data["customerId"],
                        "fid": self.data["productId"]
                    },
                    headers={
                        "content-length": None,
                        "cache-control": "max-age=0",
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
                        "upgrade-insecure-requests": "1",
                        "origin": f"https://{DOMAIN}",
                        "content-type": "multipart/form-data",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
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
                if "raffle-confirmation" in response.url:
                    break
                else:
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            else:
                self.logger.error((
                    f"Request failed: {response.status} - {response.reason}",
                    "switching proxy" if response.status in [401, 403, 429] else None
                )), self.delay()
                if response.status in [401, 403, 429]:
                    self.switch_proxy()
                error_count += 1
                continue
        else:
            return False

        self.logger.success("Successfully entered raffle")
        return True
