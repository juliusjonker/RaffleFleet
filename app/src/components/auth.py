# -*- coding: utf-8 -*-
from constants.apis import API_DOMAIN
from constants.env import SETTINGS_PATH
from common import data, errors, http, ui
from common.security import generate_bearer, verify_response
from common.utils import close, sleep, fetch_device_id
from managers import FileManager


class Auth:
    def __init__(self):
        license_key = self.fetch_license_key()

        self.validate_license(license_key)

    @staticmethod
    def fetch_license_key():
        license_key = None
        try:
            license_key = FileManager.fetch_json_file(
                SETTINGS_PATH
            )["license-key"]
        except errors.FileError as error:
            if error.reason == "malformed":
                ui.logger.error(error.msg)
                close()
        except KeyError:
            pass

        while not license_key:
            license_key = ui.fetch_input(
                "License key", loading_bar=True
            )

            if license_key:
                ui.recede_cursor(1)
            else:
                ui.logger.error("That's an invalid license key")
                sleep(2), ui.recede_cursor(2)

        return license_key

    @staticmethod
    def validate_license(license_key):
        loading_bar = ui.LoadingBar("Validating license")

        try:
            response = http.post(
                f"https://{API_DOMAIN}/auth/{license_key}",
                body={
                    "deviceId": fetch_device_id()
                },
                headers={
                    "content-type": "application/json",
                    "authorization": generate_bearer()
                }
            )
            content = response.json()

            if content["success"]:
                verify_response(response.headers)

                data.APP = content["data"]["app"]
                data.USER = content["data"]["user"]
                data.RAFFLES = content["data"]["raffles"]

                loading_bar.success("Welcome, " + data.USER["name"])
            else:
                loading_bar.error(content["message"])
                close()
        except (errors.HTTPError, errors.JSONError, errors.SecurityError) as error:
            loading_bar.error(error.msg)
            close()
        except KeyError:
            loading_bar.error(errors.DFLT_MSG.format(errors.IDS["keyError"]))
            close()
