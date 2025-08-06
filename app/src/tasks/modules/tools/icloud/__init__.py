# -*- coding: utf-8 -*-
from tasks.common.classes import Email
from .constants import NAME
from .generate_emails import GenerateEmails
from .get_session import GetSession


SUBMODULES = {
    "Generate emails": {
        "module": GenerateEmails,
        "parent": Email,
        "hook": GetSession,
        "subject": "emails",
        "input": ["emailAmount"],
        "output": ["master", "email"],
        "statuses": ["pending", "generated"],
        "isMultiThreaded": False
    }
}
