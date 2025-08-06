# -*- coding: utf-8 -*-
import re
from datetime import date, timedelta
from common.errors import TaskError
from managers import TaskManager
from tasks.hooks import imap
from tasks.common.classes import Email, Input


class FetchEmails(imap.Manager):
    def __init__(self, manager: TaskManager):
        self.manager = manager

        super().__init__(manager)
        if not self.credentials:
            raise TaskError("No valid masters found")

    def execute(self):
        results = self.fetch_emails(
            subject="Confirm your PayPal account",
            sender=re.compile("noreply.*?afew.store.com"),
            max_date=date.today() - timedelta(days=self.manager.input.emails["maxAge"]),
            regex=re.compile(r'"(https://www\.paypal\.com/cgi-bin/webscr\?cmd=_express-checkout&token=.*?)"')
        )

        for email, url in results.items():
            self.manager.add_task(
                parent=Email(email),
                input=Input(
                    verification={
                        "url": url
                    }
                )
            )

        return bool(results)
