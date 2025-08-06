# -*- coding: utf-8 -*-
import random
from common import http, data
from common.utils import sleep, generate_coordinate
from tasks.common import Logger
from tasks.common.classes import Task
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME


class GenerateAddresses:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = Logger(NAME, NAME)

        self.session = http.Session()

    @staticmethod
    def delay():
        sleep(random.randint(1000, 2000) / 1000)

    def execute(self):
        self.logger.info("Generating addresses...")

        addresses = []
        while len(addresses) < self.task.input.amount:
            address = self.generate_address()
            if address and address not in addresses:
                addresses.append(address)

                self.task.manager.increment(
                    "generated",
                    task=self.task,
                    parent=address
                )

            sleep(.05)

        self.logger.success("Successfully generated addresses")

    def generate_address(self):
        lat, long = generate_coordinate(
            self.task.parent.coordinate,
            self.task.parent.radius
        )

        try:
            response = self.session.get(
                f"https://api.mapbox.com/geocoding/v5/mapbox.places/{long},{lat}.json",
                params={
                    "access_token": data.SETTINGS["mapbox-key"],
                    "types": "address",
                    "country": self.task.parent.country,
                    "limit": 5
                }
            )

            if response.ok:
                for address in response.json()["features"]:
                    if address["properties"]["accuracy"] == "intersection":
                        continue

                    address.update({
                        x["id"].split(".")[0]: x for x in address["context"]
                    })
                    return {
                        "street": address["text"],
                        "house_number": address.get("address") or str(random.randint(1, 30)),
                        "line_2": "",
                        "city": address["place"]["text"],
                        "postcode": address["postcode"]["text"],
                        "province": address.get("region", {}).get("short_code", ""),
                        "country": address["country"]["short_code"].upper()
                    }
            elif response.status == 401:
                self.logger.error((
                    "Failed to generate addresses: Invalid key loaded", "waiting 30s"
                )), sleep(30)
            else:
                self.logger.error(
                    f"Request failed: {response.status} - {response.reason}"
                ), self.delay()
        except (HTTPError, JSONError, KeyError):
            return None
