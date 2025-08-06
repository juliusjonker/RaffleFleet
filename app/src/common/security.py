# -*- coding: utf-8 -*-
import jwt
from constants.apis import APP_JWT_KEY, WEB_JWT_KEY
from .errors import SecurityError
from .utils import current_ts


def generate_bearer():
    return "Bearer " + jwt.encode(
        {"exp": current_ts() + 60},
        APP_JWT_KEY, algorithm="HS256"
    )


def verify_response(headers):
    try:
        jwt.decode(
            headers["Authorization"].split()[1],
            WEB_JWT_KEY, algorithms="HS256"
        )
    except:
        raise SecurityError
