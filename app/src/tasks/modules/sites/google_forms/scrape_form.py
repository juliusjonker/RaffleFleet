# -*- coding: utf-8 -*-
import random
import re
import json
from common import http
from common.utils import sleep
from tasks.common import Logger
from tasks.common.classes import Task
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME, FIELD_IDS, FIELD_TYPES


class ScrapeForm:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = Logger(NAME, NAME)

        self.session = http.Session(
            clienthello="HelloRandomizedNoALPN"
        )

        self.data = {}

    @staticmethod
    def delay():
        sleep(random.randint(1000, 2000) / 1000)

    @staticmethod
    def get_data(field_type, field):
        if field_type == "date":
            if field[4][0][7][0] == 1 and field[4][0][7][1] == 1:
                return "withYearAndTime"
            elif field[4][0][7][1] == 1:
                return "withYear"
            elif field[4][0][7][0] == 1:
                return "withTime"
            else:
                return "basic"
        elif field_type == "time":
            if field[4][0][6][0] == 1:
                return "withSeconds"
            else:
                return "basic"
        else:
            return None

    @staticmethod
    def get_placeholder(question):
        if question["type"] in ["date", "time"]:
            return FIELD_TYPES[question["type"]]["placeholder"][question["data"]]
        else:
            return FIELD_TYPES[question["type"]]["placeholder"]

    def execute(self):
        status = "scraped" if self.fetch_form() else "failed"

        self.task.manager.increment(
            status,
            task=self.task,
            write_result=False
        )

    def fetch_form(self):
        self.logger.info("Scraping form...")

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
                continue

            if response.ok:
                try:
                    if "var FB_PUBLIC_LOAD_DATA_" not in response.body:
                        self.logger.error("Failed to scrape form: Form closed")
                        return False

                    content = json.loads(re.findall(
                        "var FB_PUBLIC_LOAD_DATA_ = (.*?);</script>", response.body
                    )[0])[1]

                    if content[10][6] == 2:
                        self.logger.error("Failed to scrape form: Login required")
                        return False

                    self.data["id"] = response.url.split("/")[6]
                    self.data["title"] = content[8]
                    self.data["pages"] = [[]]

                    if content[10][6] == 3:
                        self.data["pages"][-1].append({
                            "id": "emailAddress",
                            "type": "email",
                            "title": "Email",
                            "data": None,
                            "isRequired": True
                        })

                    for field in content[1]:
                        field_type = FIELD_IDS[field[3]]
                        if field_type == "newPage":
                            self.data["pages"].append([])
                            continue
                        elif field_type == "image":
                            continue

                        self.data["pages"][-1].append({
                            "id": field[4][0][0],
                            "type": field_type,
                            "title": field[1] or "No title",
                            "data": self.get_data(field_type, field),
                            "isRequired": True if field[4][0][2] else False
                        })
                    break
                except KeyError:
                    self.logger.error("Failed to scrape form: Unsupported field")
                    return False
                except (JSONError, IndexError):
                    self.logger.error("Failed to scrape form"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 404:
                self.logger.error("Failed to scrape form: Form closed")
                return False
            else:
                self.logger.error(
                    f"Request failed: {response.status} - {response.reason}"
                ), self.delay()
                error_count += 1
                continue
        else:
            return False

        self.task.manager.write_custom_result({
            self.data["title"]: {
                ".configuration.json": json.dumps(self.data, indent=4),
                "profiles.csv": {
                    question["title"] + ("*" if question["isRequired"] else ""): self.get_placeholder(question)
                    for page in self.data["pages"] for question in page
                }
            }
        }, files_to_hide=[".configuration.json"])

        self.logger.success("Successfully scraped form")
        return True
