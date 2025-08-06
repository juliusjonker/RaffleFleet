# -*- coding: utf-8 -*-
import random
import uuid
from common import http
from common.utils import sleep
from managers import TaskManager
from tasks.common import Logger
from tasks.common.classes import Task
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME, DOMAIN, HME_DOMAIN


class GenerateEmails:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.session = http.Session()
        for name, value in task.input.cookies.items():
            self.session.cookies.set(
                name, value, HME_DOMAIN
            )

        self.params = {
            "clientBuildNumber": "2304Project37",
            "clientMasteringNumber": "2304B26",
            "clientId": str(uuid.uuid4()),
            "dsId": task.input.cookies.get("X-APPLE-WEBAUTH-USER", "").split("d=")[-1].split('"')[0]
        }

    @staticmethod
    def delay():
        sleep(random.randint(1000, 2000) / 1000)

    def execute(self):
        for index in range(self.task.input.amount):
            if index > 0:
                print()

            while True:
                if email := self.generate_email(index + 1):
                    self.task.manager.increment(
                        "generated",
                        task=self.task,
                        parent={
                            "master": self.task.parent.email,
                            "email": email
                        }
                    )
                    break
                else:
                    print()

    def generate_email(self, index):
        logger = Logger(
            NAME, NAME, TaskManager.format_task_id(index)
        )

        logger.info("Generating email...")

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{HME_DOMAIN}/v1/hme/generate",
                    params=self.params,
                    body={
                        "langCode": "en-gb"
                    },
                    headers={
                        "Connection": "keep-alive",
                        "Content-Length": None,
                        "sec-ch-ua": None,
                        "sec-ch-ua-platform": None,
                        "sec-ch-ua-mobile": "?0",
                        "User-Agent": None,
                        "Content-Type": "text/plain",
                        "Accept": "*/*",
                        "Origin": f"https://{DOMAIN}",
                        "Sec-Fetch-Site": "same-site",
                        "Sec-Fetch-Mode": "cors",
                        "Sec-Fetch-Dest": "empty",
                        "Referer": f"https://{DOMAIN}/",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Accept-Language": None
                    }
                )
            except HTTPError as error:
                logger.error(error.msg), self.delay()
                continue

            if response.ok:
                try:
                    email = response.json()["result"]["hme"]
                    break
                except (JSONError, KeyError):
                    logger.error("Failed to generate email"), self.delay()
                    error_count += 1
                    continue
            else:
                logger.error(
                    f"Request failed: {response.status} - {response.reason}"
                ), self.delay()
                error_count += 1
                continue
        else:
            return False

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{HME_DOMAIN}/v1/hme/reserve",
                    params=self.params,
                    body={
                        "hme": email,
                        "label": "Email",
                        "note": ""
                    },
                    headers={
                        "Connection": "keep-alive",
                        "Content-Length": None,
                        "sec-ch-ua": None,
                        "sec-ch-ua-platform": None,
                        "sec-ch-ua-mobile": "?0",
                        "User-Agent": None,
                        "Content-Type": "text/plain",
                        "Accept": "*/*",
                        "Origin": f"https://{DOMAIN}",
                        "Sec-Fetch-Site": "same-site",
                        "Sec-Fetch-Mode": "cors",
                        "Sec-Fetch-Dest": "empty",
                        "Referer": f"https://{DOMAIN}/",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Accept-Language": None
                    }
                )
            except HTTPError as error:
                logger.error(error.msg), self.delay()
                continue

            if response.ok:
                try:
                    content = response.json()

                    if content["success"]:
                        break
                    elif "You have reached the limit" in content["error"]["errorMessage"]:
                        logger.error((
                            "Failed to generate email: Reached hourly limit", "waiting 1h"
                        )), sleep(3600)
                        return False
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    logger.error("Failed to generate email"), self.delay()
                    error_count += 1
                    continue
            else:
                logger.error(
                    f"Request failed: {response.status} - {response.reason}"
                ), self.delay()
                error_count += 1
                continue
        else:
            return False

        logger.success("Successfully generated email")
        return email
