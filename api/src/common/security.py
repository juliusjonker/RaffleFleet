# -*- coding: utf-8 -*-
import time
import jwt
from flask import request, jsonify
from .constants import WEB_JWT_KEY, APP_JWT_KEY


def generate_bearer():
    return "Bearer " + jwt.encode(
        {"exp": round(time.time()) + 60},
        WEB_JWT_KEY, algorithm="HS256"
    )


def auth_required(function):
    def wrapper(*args, **kwargs):
        try:
            jwt.decode(
                request.headers["authorization"].split()[1],
                APP_JWT_KEY, algorithms="HS256"
            )
        except:
            return jsonify(
                success=False,
                message="Access denied"
            ), 403

        return (
            function(*args, **kwargs) +
            ({"authorization": generate_bearer()},)
        )

    return wrapper
