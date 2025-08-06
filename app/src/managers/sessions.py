# -*- coding: utf-8 -*-
import json
import threading
from constants.env import FILE_ENCODING, SESSIONS_PATH
from common.ui import logger
from tasks.common.classes import CaseInsensitiveDict


file_lock = threading.Lock()


class SessionsManager:
    def __init__(self, module):
        self.module = module

        self.file_path = SESSIONS_PATH / f"{module.lower().replace(' ', '_').strip('.?')}.json"
        with open(self.file_path, encoding=FILE_ENCODING) as file:
            self.sessions = CaseInsensitiveDict(json.load(file))

    @staticmethod
    def is_clear_command(command):
        return command.lower().startswith(".clear sessions ")

    @staticmethod
    def clear(command):
        file_path = SESSIONS_PATH / f"{command.split()[2].lower().strip('.?')}.json"

        if file_path.exists():
            with open(file_path, "w", encoding=FILE_ENCODING) as file:
                file.write("{}")

            logger.success("Cleared sessions")
        else:
            logger.error("No sessions to clear")

    def get(self, parent):
        return self.sessions.get(parent.id)

    def save(self, parent, data):
        with file_lock:
            with open(self.file_path, encoding=FILE_ENCODING) as file:
                content = CaseInsensitiveDict(json.load(file))

            content[parent.id] = data

            with open(self.file_path, "w", encoding=FILE_ENCODING) as file:
                file.write(json.dumps(
                    content, indent=4
                ))
