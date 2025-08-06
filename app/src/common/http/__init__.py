# -*- coding: utf-8 -*-
from .session import Session
from . import classes, client, constants


SESSION = Session(in_hub=True)

get = SESSION.get
post = SESSION.post
head = SESSION.head
patch = SESSION.patch
put = SESSION.put
delete = SESSION.delete
