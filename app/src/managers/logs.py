# -*- coding: utf-8 -*-
import threading
from constants.apis import API_DOMAIN
from constants.env import FILE_ENCODING, LOGS_PATH
from common import data, http
from common.errors import HTTPError
from common.security import generate_bearer
from common.ui import logger
from common.utils import current_datetime


file_lock = threading.Lock()


class LogManager:
    @staticmethod
    def is_export_command(command):
        return command.lower().startswith(".export logs ")

    @staticmethod
    def write(category, caller_id, info):
        with file_lock:
            with open(LOGS_PATH / f"{category}.log", "a", encoding=FILE_ENCODING) as file:
                file.write(
                    f"{current_datetime()}\n\ncall id: {caller_id}\ninfo: {info}\n{'=' * 30}\n"
                )

    @staticmethod
    def export(command):
        components = command.split()
        if len(components) == 4:
            category = "task"
            file_path = LOGS_PATH / f"{components[2].lower().strip('.?')}-{components[3].replace('/', '-')}.log"
        else:
            category = components[-1].lower()
            file_path = LOGS_PATH / f"{category}.log"

        if file_path.exists():
            with open(file_path, encoding=FILE_ENCODING) as file:
                logs = file.read()
        else:
            logger.error("No logs to export")
            return

        max_upload = 4_000_000
        if len(logs) > max_upload:
            slices = [
                logs[x:x+max_upload]
                for x in range(0, len(logs), max_upload)
            ]
        else:
            slices = [logs]

        try:
            for index, logs_slice in enumerate(slices):
                response = http.post(
                    f"https://{API_DOMAIN}/logs/{data.USER['id']}",
                    body={
                        "category": category,
                        "logfile": (
                            f"{index + 1}/{len(slices)} {file_path.name}" if len(slices) > 1 else file_path.name,
                            "text/plain", logs_slice,
                        )
                    },
                    headers={
                        "content-type": "multipart/form-data",
                        "authorization": generate_bearer()
                    }
                )

                if response.status != 200:
                    logger.error("Failed to export logs")
                    break
            else:
                file_path.unlink()
                logger.success("Exported logs")
        except HTTPError:
            logger.error("Failed to export logs")
