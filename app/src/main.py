# -*- coding: utf-8 -*-
import traceback
from constants.env import OS, STAGE
from common import errors
from common.utils import close, is_update_available
from common.ui import logger
from managers import LogManager
from components import Auth, Boot, Hub, Update


def main():
    hub = Hub()

    Auth()
    if is_update_available() and STAGE.PROD:
        Update()
    Boot()

    hub.main_menu()


if STAGE.DEV or STAGE.PROD:
    if not (OS.Windows or OS.MacOS):
        print()
        logger.error("Unsupported operating system")
        close()

    try:
        main()
    except:
        print()
        logger.error(errors.DFLT_MSG.format(errors.IDS["unknown"]))
        LogManager.write("error", 1, traceback.format_exc().strip())
        close(delay=5)
