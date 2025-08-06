# -*- coding: utf-8 -*-
from common import data
from common.utils import sleep
from tasks.common.errors import CaptchaError
from .providers import AntiCaptcha, AutoSolve, CapMonster, CapSolver, TwoCaptcha


class Solver:
    max_retries = 3

    def __init__(self, logger, variant, domain, site_key=None, metadata=None):
        self.logger = logger

        self.variant = variant
        self.variant_name = "hCaptcha" if self.variant == "h" else "reCaptcha"

        self.domain = domain
        self.site_key = site_key
        self.metadata = metadata or {}

    def set_site_key(self, site_key):
        self.site_key = site_key

    @property
    def provider(self):
        provider = data.SETTINGS["captcha-solver"]["provider"].lower().replace(" ", "")

        if provider in ["2captcha", "2cap", "2"]:
            module = TwoCaptcha
        elif provider in ["anticaptcha", "anticap", "anti"]:
            module = AntiCaptcha
        elif provider in ["autosolve", "autosolver", "aycd", "aycdautosolve"]:
            module = AutoSolve
        elif provider in ["capmonster", "captchamonster", "monster"]:
            module = CapMonster
        elif provider in ["capsolver", "captchasolver", "captchaai", "capai"]:
            module = CapSolver
        else:
            raise CaptchaError(1, self.variant_name, "INVALID_PROVIDER")

        return module(
            self.variant_name, self.variant, self.domain, self.site_key, self.metadata
        )

    def solve(self):
        error_count = 0
        while error_count < self.max_retries:
            self.logger.info(f"Solving {self.variant_name}...")

            try:
                return self.provider.fetch_token(
                    data.SETTINGS["captcha-solver"]["key"]
                )
            except CaptchaError as error:
                self.logger.error(error.msg), sleep(error.delay)
                if error.id in ["API_ERROR", "ERROR_CAPTCHA_UNSOLVABLE"]:
                    error_count += 1
