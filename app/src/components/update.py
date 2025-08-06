# -*- coding: utf-8 -*-
import os
import shutil
import subprocess
from constants import app
from constants.apis import WEBSITE_DOMAIN
from constants.env import OS, FILE_PATH
from common.errors import DownloadError
from common.utils import sleep, close, generate_temp_path, download_file
from common.ui import LoadingBar
from .boot import Boot


class Update:
    def __init__(self):
        self.loading_bar = LoadingBar("Installing update")

        Boot.verify_storage_dir()
        self.new_file_path = generate_temp_path("app", OS.app_ext)

        self.download_file()
        self.finish_update()

    def download_file(self):
        try:
            download_file(
                f"https://{WEBSITE_DOMAIN}/download/{OS.name.replace('_', '-')}/{app.NAME}{OS.app_ext}",
                self.new_file_path
            )
        except DownloadError as error:
            self.loading_bar.error(error.msg)
            close()

    def finish_update(self):
        self.loading_bar.success("Update complete")
        sleep(1)

        shutil.move(FILE_PATH, generate_temp_path("app", OS.app_ext))
        shutil.move(self.new_file_path, FILE_PATH)

        if OS.Windows:
            os.startfile(FILE_PATH)
        else:
            subprocess.call(["open", FILE_PATH])

        close(delay=0)
