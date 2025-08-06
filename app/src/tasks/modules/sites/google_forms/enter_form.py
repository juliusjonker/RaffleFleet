# -*- coding: utf-8 -*-
import random
import re
import html
import json
from common import http
from common.utils import sleep, current_ts
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, Form
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME, DOMAIN


class EnterForm:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = Logger(
            NAME, task.id, task.formatted_parent_id or NAME
        )

        self.session = http.Session(
            proxy=task.proxies.get(),
            clienthello="HelloRandomizedNoALPN"
        )

        self.form = Form()
        self.data = {}

    @staticmethod
    def delay():
        sleep(random.randint(1000, 2000) / 1000)

    def switch_proxy(self):
        self.session.set_proxy(
            self.task.proxies.get()
        )

    def is_last_page(self, page_index):
        return page_index + 1 == len(self.task.input.form["pages"])

    def generate_body(self, page_index, questions):
        body = {
            "dlut": round(current_ts(exact=True) * 1000),
            "fvv": "1",
            "partialResponse": self.data["partialResponse"],
            "pageHistory": ",".join(str(x) for x in range(page_index + 1)),
            "fbzx": self.data["responseId"]
        }
        if not self.is_last_page(page_index):
            body["continue"] = "1"

        for question in questions:
            if question["type"] == "email":
                body["emailAddress"] = self.task.parent.data[question["title"]]
            elif question["type"] == "date":
                body[f"entry.{question['id']}_day"] = self.task.parent.data[question["title"]]
                body[f"entry.{question['id']}_month"] = self.task.parent.data[question["title"]]

                if "Year" in question["data"]:
                    body[f"entry.{question['id']}_year"] = self.task.parent.data[question["title"]]
                if "Time" in question["data"]:
                    body[f"entry.{question['id']}_hour"] = self.task.parent.data[question["title"]]
                    body[f"entry.{question['id']}_minute"] = self.task.parent.data[question["title"]]
            elif question["type"] == "time":
                body[f"entry.{question['id']}_hour"] = self.task.parent.data[question["title"]]
                body[f"entry.{question['id']}_minute"] = self.task.parent.data[question["title"]]

                if "Seconds" in question["data"]:
                    body[f"entry.{question['id']}_second"] = self.task.parent.data[question["title"]]
            else:
                body[f"entry.{question['id']}"] = self.task.parent.data[question["title"]]

                if question["type"] in ["multipleChoice", "checkbox"]:
                    body[f"entry.{question['id']}_sentinel"] = ""

        return body

    def execute(self):
        status = "entered" if self.fetch_form() else "failed"

        if status == "entered":
            webhooks.Entry(
                NAME, self.form, self.task.parent, self.session.proxy
            ).send()

        self.task.manager.increment(
            status,
            task=self.task,
            #product=self.product,
            parent=self.task.parent,
            proxy=self.session.proxy
        )

    def fetch_form(self):
        self.logger.info("Entering form...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/forms/d/e/{self.task.input.form['id']}/viewform",
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
                    if "var FB_PUBLIC_LOAD_DATA_" not in response.body:
                        self.logger.error("Failed to enter form: Form closed")
                        return False

                    content = json.loads(re.findall(
                        "var FB_PUBLIC_LOAD_DATA_ = (.*?);</script>", response.body
                    )[0])[1]

                    if content[10][6] == 2:
                        self.logger.error("Failed to enter form: Login required")
                        return False

                    self.data["referer"] = response.url
                    self.data["partialResponse"] = html.unescape(re.findall('name="partialResponse" value="(.*?)"', response.body)[0])
                    self.data["responseId"] = re.findall('name="fbzx" value="(.*?)"', response.body)[0]
                    break
                except (JSONError, IndexError):
                    self.logger.error("Failed to enter form"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 404:
                self.logger.error("Failed to enter form: Form closed")
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

        return self.enter_form()

    def enter_form(self):
        for page_index, questions in enumerate(self.task.input.form["pages"]):
            error_count = 0
            while error_count < self.max_retries:
                try:
                    response = self.session.post(
                        f"https://{DOMAIN}/forms/u/0/d/e/{self.task.input.form['id']}/formResponse",
                        body=self.generate_body(
                            page_index, questions
                        ),
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
                            "referer": self.data["referer"],
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
                        if self.is_last_page(page_index):
                            if '<div class="vHW8K">' in response.body:
                                break
                            else:
                                raise IndexError
                        else:
                            self.data["referer"] = response.url
                            self.data["partialResponse"] = html.unescape(re.findall('name="partialResponse" value="(.*?)"', response.body)[0])
                            break
                    except IndexError:
                        self.logger.error("Failed to enter form"), self.delay()
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

        self.logger.success("Successfully entered form")
        return True
