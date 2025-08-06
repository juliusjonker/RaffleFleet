# -*- coding: utf-8 -*-
import re
from managers import TaskManager
from tasks.common import Logger, Browser
from tasks.common.classes import Email, Input
from .constants import NAME, DOMAIN


class GetSession:
    def __init__(self, manager: TaskManager):
        self.manager = manager

        self.logger = Logger(NAME, NAME)

    def execute(self):
        self.logger.info("Log in trough the browser")

        try:
            browser = Browser()
        except:
            self.logger.error("Failed to log in: Browser error")
            return False

        try:
            browser.get(f"https://{DOMAIN}/")

            body = browser.await_response(re.compile(
                '<div class="email">(.*?)</div>'
            ))

            if "iCloud+" not in body:
                self.logger.error("Failed to log in: No iCloud+ subscription")
                return False

            self.manager.add_task(
                parent=Email(re.findall(
                    '<div class="email">(.*?)</div>', body
                )[0]),
                input=Input(
                    amount=self.manager.input.amount,
                    cookies=browser.cookies
                )
            )
        except:
            self.logger.error("Failed to log in")
            return False
        finally:
            browser.close()

        self.logger.success("Successfully logged in")
        return True
