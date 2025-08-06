# -*- coding: utf-8 -*-
import random
import re
from common import http
from common.utils import sleep
from tasks.common import Logger
from tasks.common.classes import Task
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME, DOMAIN, COUNTRY_IDS


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

        self.data = {}

    @staticmethod
    def delay():
        sleep(random.randint(1000, 2000) / 1000)

    def switch_proxy(self):
        self.session.set_proxy(
            self.task.proxies.get()
        )

    def handle_queue(self):
        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/waitingroom?redirect=http://{DOMAIN}/register",
                    headers={
                        "upgrade-insecure-requests": "1",
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "sec-fetch-site": "none",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": None,
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
                response = self.session.get(
                    f"https://{DOMAIN}/waitingroom/redeem",
                    headers={
                        "sec-ch-ua": None,
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "sec-ch-ua-platform": None,
                        "accept": "*/*",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": f"https://{DOMAIN}/waitingroom?redirect=http://{DOMAIN}/",
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
                    if response.json()["status"] == "ok":
                        break
                    else:
                        self.logger.info("Waiting in queue..."), self.delay()
                        continue
                except (JSONError, KeyError):
                    self.logger.error("Failed to handle queue"), self.delay()
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
                    f"https://{DOMAIN}/register",
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
                    },
                    allow_redirects=False
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    if "/waitingroom" not in response.headers.get("location", ""):
                        self.data["csrfToken"] = re.findall('name="_csrfToken" .*? value="(.*?)"', response.body)[0]
                        self.data["tokenFields"] = re.findall(r'name="_Token\[fields]" .*? value="(.*?)"', response.body)[0]
                        self.data["tokenUnlocked"] = re.findall(r'name="_Token\[unlocked]" .*? value="(.*?)"', response.body)[0]
                        break
                    else:
                        self.handle_queue()
                        continue
                except IndexError:
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
                    f"https://{DOMAIN}/register",
                    body={
                        "_method": "POST",
                        "_csrfToken": self.data["csrfToken"],
                        "active": "1",
                        "role": "customer",
                        "first_name": self.task.parent.first_name,
                        "last_name": self.task.parent.last_name,
                        "email": self.task.parent.email,
                        "cellphone": self.task.parent.full_phone,
                        "password": self.task.parent.password,
                        "addresses[0][title]": "Residential",
                        "addresses[0][country_id]": COUNTRY_IDS.get(self.task.parent.country),
                        "address_search": "",
                        "addresses[0][street_address_1]": self.task.parent.address,
                        "addresses[0][building_details]": "",
                        "addresses[0][street_address_2]": self.task.parent.line_2,
                        "addresses[0][city]": self.task.parent.city,
                        "addresses[0][state]": self.task.parent.province,
                        "addresses[0][postal_code]": self.task.parent.postcode,
                        "addresses[0][recipient_name]": self.task.parent.full_name,
                        "addresses[0][contact_number]": self.task.parent.full_phone,
                        "addresses[0][is_default]": "1",
                        "agree_terms": "",
                        "subscription": "0",
                        "hp": "",
                        "_Token[fields]": self.data["tokenFields"],
                        "_Token[unlocked]": self.data["tokenUnlocked"]
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
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-user": "?1",
                        "sec-fetch-dest": "document",
                        "referer": f"https://{DOMAIN}/register",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                if "account has been created" in response.body:
                    break
                elif "email address is already in use" in response.body:
                    self.logger.error("Failed to generate account: Email already in use")
                    return False
                elif "cellphone number is already in use" in response.body:
                    self.logger.error("Failed to generate account: Phone number already in use")
                    return False
                else:
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
