# -*- coding: utf-8 -*-
from itertools import cycle
from threading import Thread
from constants import colors
from common.utils import sleep, current_ts
from . import logger


class LoadingBar:
    states = [
        "%s●%s○○" % colors.MAIN,
        "○%s●%s○" % colors.MAIN,
        "○○%s●%s" % colors.MAIN,
        "○%s●%s○" % colors.MAIN
    ]

    def __init__(self, msg, short=False, min_duration=0):
        self.msg = msg

        self.short = short
        self.min_duration = min_duration

        self.in_progress = True

        self.thread = Thread(target=self.animation)
        self.thread.start()

        self.start_ts = current_ts(exact=True)

    def animation(self):
        for state in cycle(self.states):
            if not self.in_progress:
                break

            print(
                (" " if self.short else "  ") +
                f"{state} {self.msg}", end="\r"
            )
            sleep(.15)

    def success(self, msg=None):
        if (delta := self.min_duration - (current_ts(exact=True) - self.start_ts)) > 0:
            sleep(delta)

        self.in_progress = False
        self.thread.join()

        if msg:
            logger.success(
                msg.ljust(len(self.msg) + 2), short=self.short
            )

    def error(self, msg):
        self.in_progress = False
        self.thread.join()

        logger.error(
            msg.ljust(len(self.msg) + 2), short=self.short
        )
