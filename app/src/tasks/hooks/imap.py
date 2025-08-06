# -*- coding: utf-8 -*-
import csv
import html
from threading import Thread
from imap_tools import MailBox, AND
from constants.env import FILE_ENCODING, MASTERS_PATH
from common.utils import get_average_length
from tasks.common import Logger
from tasks.common.classes import CaseInsensitiveDict


class Manager:
    domains = {
        "gmail": "imap.gmail.com",
        "outlook": "outlook.office365.com",
        "live": "outlook.office365.com",
        "hotmail": "outlook.office365.com",
        "yahoo": "imap.mail.yahoo.com",
        "icloud": "imap.mail.me.com",
        "me": "imap.mail.me.com",
        "aol": "imap.aol.com",
        "mail": "imap.mail.com",
        "web": "imap.web.de"
    }
    folders = ["inbox", "spam", "junk"]
    max_size = 1500

    def __init__(self, manager):
        self.manager = manager

        self.credentials = self.fetch_credentials()

        self.results = CaseInsensitiveDict()
        self.avg_parent_length = get_average_length(
            self.credentials, lambda x: x["username"]
        )

    def fetch_credentials(self):
        credentials = []
        try:
            with open(MASTERS_PATH, encoding=FILE_ENCODING) as file:
                for email in csv.DictReader(file):
                    try:
                        credentials.append({
                            "username": email["Email"].strip(),
                            "password": email["Password"].strip(),
                            "server": self.domains[email["Email"].split("@")[1].split(".")[0]]
                        })
                    except (KeyError, AttributeError, IndexError):
                        continue
        except (FileNotFoundError, PermissionError):
            return []

        return credentials

    def fetch_emails(self, **kwargs):
        threads = [
            Thread(
                target=self.fetch_emails_from_inbox,
                args=(email["username"], email["password"], email["server"]),
                kwargs=kwargs
            ) for email in self.credentials
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        return self.results

    def fetch_emails_from_inbox(self, username, password, server, **kwargs):
        logger = Logger(
            "IMAP", "IMAP",
            self.manager.format_parent_id(
                username, length=self.avg_parent_length
            )
        )

        subject = kwargs["subject"]
        sender = kwargs["sender"]
        max_date = kwargs["max_date"]
        regex = kwargs["regex"]
        results = CaseInsensitiveDict()

        logger.info("Logging in...")
        try:
            inbox = MailBox(server).login(username, password)
        except:
            logger.error("Failed to log in: Invalid credentials")
            return
        logger.success("Successfully logged in")

        logger.info("Loading emails...")
        for folder in inbox.folder.list():
            if not any(name in folder.name.lower() for name in self.folders):
                continue

            try:
                inbox.folder.set(folder.name)

                index = 0
                while emails := list(inbox.fetch(
                    criteria=AND(subject=subject, sent_date_gte=max_date),
                    limit=slice(index, index + self.max_size), bulk=True
                )):
                    index += self.max_size

                    for email in emails:
                        username = email.to[0] if sender.match(email.from_) else email.from_
                        if result := regex.findall(email.html):
                            results[username] = html.unescape(result[0])
            except:
                continue

        if results:
            self.results.update(results)
            logger.success("Successfully loaded emails")
        else:
            logger.error("Failed to load emails: No emails found")
