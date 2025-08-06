# -*- coding: utf-8 -*-
import random
import threading
from constants import regexes
from constants.env import FILE_ENCODING, PROXIES_PATH
from common.utils import sleep, threaded
from tasks.common.classes import Proxy
from .files import FileManager


proxy_lock = threading.Lock()


class ProxyManager:
    def __init__(self, files=None, is_localhost=False):
        self.files = files
        self.is_localhost = is_localhost

        if not is_localhost:
            self.all_proxies = self.fetch_proxies(files)

            self.unused_proxies = self.all_proxies.copy()
            self.used_proxies = []

            self.monitor_files()
        else:
            self.all_proxies = [Proxy("localhost")]

    @staticmethod
    def fetch_loaded_files():
        proxies = []
        try:
            for file_path in PROXIES_PATH.iterdir():
                if ".txt" not in file_path.name:
                    continue

                if line_count := FileManager.fetch_line_count(file_path):
                    proxies.append({
                        "fileName": file_path.name,
                        "lineCount": line_count
                    })
        except (FileNotFoundError, PermissionError):
            return []

        return proxies

    @staticmethod
    def fetch_proxies(files):
        proxies = []
        for file_name in files:
            try:
                with open(PROXIES_PATH / file_name, encoding=FILE_ENCODING) as file:
                    proxies += [
                        Proxy(proxy.strip())
                        for proxy in file if regexes.PROXY.match(proxy.strip())
                    ]
            except (FileNotFoundError, PermissionError):
                continue

        random.shuffle(proxies)
        return proxies

    @threaded
    def monitor_files(self):
        while True:
            sleep(2)

            with proxy_lock:
                if proxies := self.fetch_proxies(self.files):
                    self.all_proxies = proxies

                    self.unused_proxies = [
                        proxy for proxy in proxies
                        if proxy not in self.used_proxies
                    ]

    def get(self):
        if not self.is_localhost:
            with proxy_lock:
                try:
                    proxy = random.choice(self.unused_proxies)
                except IndexError:
                    return random.choice(self.all_proxies)

                self.unused_proxies.remove(proxy)
                self.used_proxies.append(proxy)

                return proxy
        else:
            return self.all_proxies[0]
