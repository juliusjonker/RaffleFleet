# -*- coding: utf-8 -*-
import threading
from constants import colors
from constants.env import FILE_ENCODING, LOGS_PATH
from common.utils import current_date, current_datetime, joins


file_lock = threading.Lock()
print_lock = threading.Lock()


class Logger:
    def __init__(self, module, task_id, parent_id=None):
        self.module = module
        self.task_id = task_id
        self.parent_id = parent_id

        self.file_path = LOGS_PATH / f"{module.lower().replace(' ', '_').strip('.?')}-{current_date()}.log"

    def log(self, status, msg, color):
        if isinstance(msg, tuple):
            msg, details = msg
        else:
            details = None

        with print_lock:
            datetime = current_datetime()

            print(joins(
                f" %s{datetime}%s" % colors.DARK_GREY, self.task_id, self.parent_id,
                f"%s{msg}%s" % color, f"%s{details}%s" % colors.GREY if details else None,
                sep=" %s|%s " % colors.GREY
            ))

        with file_lock:
            with open(self.file_path, "a", encoding=FILE_ENCODING) as file:
                file.write(
                    f"[{status}]".ljust(10) + joins(
                        datetime, self.task_id, self.parent_id, msg, details, sep=" | "
                    ) + "\n"
                )

    def info(self, msg):
        self.log("INFO", msg, colors.WHITE)

    def success(self, msg):
        self.log("SUCCESS", msg, colors.GREEN)

    def error(self, msg):
        self.log("ERROR", msg, colors.RED)
