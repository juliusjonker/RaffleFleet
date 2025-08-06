# -*- coding: utf-8 -*-
import json
import threading
from constants.env import FILE_ENCODING, ENTRIES_PATH
from common.utils import current_ts
from common.ui import logger
from tasks.common.classes import CaseInsensitiveDict


file_lock = threading.Lock()


class EntriesManager:
    def __init__(self, site, product):
        self.site = site
        self.product = product

        self.file_path = ENTRIES_PATH / f"{site.lower().replace(' ', '_').strip('.?')}.json"
        with open(self.file_path, encoding=FILE_ENCODING) as file:
            content = CaseInsensitiveDict(json.load(file))

        if self.product in content:
            self.entries = content[self.product]["entries"]
        else:
            self.entries = []
            content[self.product] = {
                "timestamp": current_ts(),
                "entries": []
            }

        with open(self.file_path, "w", encoding=FILE_ENCODING) as file:
            file.write(json.dumps(
                content, indent=4
            ))

    @staticmethod
    def is_clear_command(command):
        return command.lower().startswith(".clear entries ") and command.count(" ") == 3

    @staticmethod
    def clear(command):
        components = command.split()

        file_path = ENTRIES_PATH / f"{components[2].lower().strip('.?')}.json"
        product = components[3]

        try:
            with open(file_path, encoding=FILE_ENCODING) as file:
                content = CaseInsensitiveDict(json.load(file))

            del content[product]

            with open(file_path, "w", encoding=FILE_ENCODING) as file:
                file.write(json.dumps(
                    content, indent=4
                ))

            logger.success("Cleared entries")
        except (FileNotFoundError, KeyError):
            logger.error("No entries to clear")

    def filter(self, parents):
        return [
            parent for parent in parents
            if parent.id.lower() not in self.entries
        ]

    def save(self, parent):
        with file_lock:
            with open(self.file_path, encoding=FILE_ENCODING) as file:
                content = CaseInsensitiveDict(json.load(file))

            content[self.product]["entries"].append(parent.id.lower())

            with open(self.file_path, "w", encoding=FILE_ENCODING) as file:
                file.write(json.dumps(
                    content, indent=4
                ))
