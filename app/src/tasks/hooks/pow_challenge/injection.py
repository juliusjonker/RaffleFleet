# -*- coding: utf-8 -*-
from .solver import Solver


def is_challenge(body):
    return "/_sec/verify" in body and "bm-verify" in body


def hook(function):
    session = function.__self__

    def wrapper(*args, **kwargs):
        response = function(*args, **kwargs)

        if is_challenge(response.body):
            Solver(session, response).solve()
            return function(*args, **kwargs)
        else:
            return response

    return wrapper
