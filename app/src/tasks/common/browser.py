# -*- coding: utf-8 -*-
import json
import base64
from zipfile import ZipFile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from urllib.parse import urlencode
from constants.env import OS, DEPS_PATH
from common.utils import sleep, threaded, generate_temp_path
from common.http.constants import ACCEPT_LANGUAGE


class Browser(webdriver.Chrome):
    def __init__(self, proxy=None, size=(450, 600)):
        self.proxy = proxy
        self.size = size

        self.get = self.get_hook(self.get)
        self.read_logs = []

        options = webdriver.ChromeOptions()

        options.add_argument(f"--window-size={size[0]},{size[1]}")
        options.add_experimental_option("prefs", {"intl.accept_languages": ACCEPT_LANGUAGE.split(";")[0]})

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        if proxy and proxy.type != "localhost":
            if proxy.type == "authorized":
                options.add_extension(
                    self.build_proxy_extension(proxy)
                )
            else:
                options.add_argument(f"--proxy-server={proxy.line}")

        super().__init__(
            service=Service(
                DEPS_PATH / OS.name / f"chromedriver{OS.app_ext}"
            ),
            options=options
        )

    @threaded
    def close(self):
        self.quit()

    @property
    def cookies(self):
        return {
            cookie["name"]: cookie["value"]
            for cookie in self.get_cookies()
        }

    @property
    def requests(self):
        logs = [
            log for log in self.get_log("performance")
            if log not in self.read_logs
        ]

        requests = []
        for log in logs:
            log = json.loads(log["message"])["message"]
            if log["method"] == "Network.responseReceived" and log["params"]["type"] in ["Document", "Fetch", "XHR"]:
                try:
                    requests.append({
                        "url": log["params"]["response"]["url"],
                        "body": self.execute_cdp_cmd(
                            "Network.getResponseBody", {
                                "requestId": log["params"]["requestId"]
                            }
                        )["body"]
                    })
                except:
                    continue

        self.read_logs += logs
        return requests

    @staticmethod
    def get_hook(function):
        def wrapper(url, params=None):
            if params:
                url += f"?{urlencode(params)}"

            return function(url)

        return wrapper

    @staticmethod
    def build_proxy_extension(proxy):
        with open(DEPS_PATH / "chrome_proxy" / "manifest.json") as file:
            manifest = file.read()

        with open(DEPS_PATH / "chrome_proxy" / "background.js") as file:
            background_script = file.read() % (
                proxy.host, proxy.port, proxy.username, proxy.password
            )

        path = generate_temp_path("ext", ".zip")
        with ZipFile(path, "w") as file:
            file.writestr("manifest.json", manifest)
            file.writestr("background.js", background_script)

        return path

    def post(self, url, params=None, body=None):
        self.get("data:text/html;base64, " + base64.b64encode(f"""
            <form id="form" action="{url}" method="post">
                {"".join([
                    f'<input type="hidden" name="{key}" value="{value}"/>' 
                    for key, value in body.items()
                ]) if body else ""}
            </form>
            <script>
                document.getElementById("form").submit();
            </script>""".encode()).decode(),
            params=params
        )

    def get_html(self, html_code):
        self.get("data:text/html;base64, " + base64.b64encode(
            html_code.encode()
        ).decode())

    def await_response(self, regex, advanced=False):
        while True:
            if advanced:
                for request in self.requests:
                    if regex.findall(request["body"]):
                        return request["body"]
            else:
                body = self.page_source
                if regex.findall(body):
                    return body

            sleep(.25)
