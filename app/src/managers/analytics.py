# -*- coding: utf-8 -*-
import json
import threading
from functools import partial
from constants.env import FILE_ENCODING
from constants.apis import API_DOMAIN
from common import data, http
from common.utils import generate_temp_path
from common.errors import HTTPError
from common.security import generate_bearer


file_lock = threading.Lock()


class AnalyticsManager:
    def __init__(self, site, category):
        self.category = category

        self.file_path = generate_temp_path("analytics", ".json")
        with open(self.file_path, "w", encoding=FILE_ENCODING) as file:
            file.write(json.dumps({
                "site": site,
                "productName": None,
                category: 0
            }, indent=4))

        self.export = partial(self.export, self.file_path)

    @staticmethod
    def export(file_path, keep_file=False):
        with file_lock:
            with open(file_path, encoding=FILE_ENCODING) as file:
                content = json.load(file)

            entries = content.get("entries", 0)
            wins = content.get("wins", 0)
            site = content["site"]
            product_name = content["productName"]

            if keep_file:
                content["entries"] = 0
                content["wins"] = 0

                with open(file_path, "w", encoding=FILE_ENCODING) as file:
                    file.write(json.dumps(
                        content, indent=4
                    ))
            else:
                file_path.unlink()

        if not (entries or wins):
            return

        if site in data.USER["analytics"]:
            if product_name in data.USER["analytics"][site]:
                data.USER["analytics"][site][product_name]["entries"] += entries
                data.USER["analytics"][site][product_name]["wins"] += wins
            else:
                data.USER["analytics"][site][product_name] = {
                    "entries": entries,
                    "wins": wins
                }
        else:
            data.USER["analytics"][site] = {
                product_name: {
                    "entries": entries,
                    "wins": wins
                }
            }

        try:
            http.post(
                f"https://{API_DOMAIN}/analytics/{data.USER['id']}",
                body={
                    "site": site,
                    "productName": product_name,
                    "entries": entries,
                    "wins": wins
                },
                headers={
                    "content-type": "application/json",
                    "authorization": generate_bearer()
                }
            )
        except HTTPError:
            pass

    def increment(self, product):
        with file_lock:
            with open(self.file_path, encoding=FILE_ENCODING) as file:
                content = json.load(file)

            content[self.category] += 1
            if not content["productName"]:
                content["productName"] = product.name

            with open(self.file_path, "w", encoding=FILE_ENCODING) as file:
                file.write(json.dumps(
                    content, indent=4
                ))
