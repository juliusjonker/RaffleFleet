# -*- coding: utf-8 -*-
import json
import psutil
import shutil
import asyncio
from pypresence import Presence
from constants import app, env
from constants.apis import API_DOMAIN
from common import data, errors, http, utils
from common.security import generate_bearer, verify_response
from common.ui import LoadingBar, logger
from managers import AnalyticsManager, FileManager, LogManager, ModuleManager, ProxyManager


class Boot:
    def __init__(self):
        self.loading_bar = LoadingBar("Setting up", min_duration=.7)

        self.verify_storage_dir()
        self.verify_user_files()

        self.clear_files()
        self.fetch_files_on_interval()
        self.validate_license_on_interval()
        self.set_rich_presence(asyncio.get_event_loop())
        if env.STAGE.PROD:
            self.monitor_threats()

        self.loading_bar.success()

    @staticmethod
    def verify_storage_dir():
        if not env.STORAGE_PATH.is_dir():
            env.STORAGE_PATH.mkdir()

        if not env.ENTRIES_PATH.is_dir():
            env.ENTRIES_PATH.mkdir()

        if not env.LOGS_PATH.is_dir():
            env.LOGS_PATH.mkdir()

        if not env.SESSIONS_PATH.is_dir():
            env.SESSIONS_PATH.mkdir()

        if not env.TEMP_PATH.is_dir():
            env.TEMP_PATH.mkdir()

    @staticmethod
    def verify_user_files():
        site_list, tool_list = ModuleManager.get_modules()

        if not env.SITES_PATH.is_dir():
            env.SITES_PATH.mkdir()

        if not env.TOOLS_PATH.is_dir():
            env.TOOLS_PATH.mkdir()

        if not env.PROXIES_PATH.is_dir():
            env.PROXIES_PATH.mkdir()

            with open(env.PROXIES_PATH / "proxies.txt", "w", encoding=env.FILE_ENCODING) as file:
                file.write("ip:port\nip:port:user:pass")

        for site in site_list:
            path = env.SITES_PATH / site.translate(env.ILLEGAL_FILE_CHARS)
            if not path.is_dir():
                path.mkdir()

                if file_data := env.SITE_FILES.get(site):
                    with open(path / file_data["placeholder"], "w", encoding=env.FILE_ENCODING) as file:
                        file.writelines([
                            ",".join(file_data["fields"].keys()) + "\n",
                            ",".join(file_data["fields"].values())
                        ])

            if not (path / env.RESULTS_PATH).is_dir():
                (path / env.RESULTS_PATH).mkdir()

        for tool in tool_list:
            path = env.TOOLS_PATH / tool.translate(env.ILLEGAL_FILE_CHARS)
            if not path.is_dir():
                path.mkdir()

                if file_data := env.TOOL_FILES.get(tool):
                    with open(path / file_data["placeholder"], "w", encoding=env.FILE_ENCODING) as file:
                        file.writelines([
                            ",".join(file_data["fields"].keys()) + "\n",
                            ",".join(file_data["fields"].values())
                        ])

            if not (path / env.RESULTS_PATH).is_dir():
                (path / env.RESULTS_PATH).mkdir()

        for site in site_list:
            file_path = env.ENTRIES_PATH / f"{site.lower().replace(' ', '_').strip('.?')}.json"
            if not file_path.exists():
                with open(file_path, "w", encoding=env.FILE_ENCODING) as file:
                    file.write("{}")

        for module in site_list + tool_list:
            file_path = env.SESSIONS_PATH / f"{module.lower().replace(' ', '_').strip('.?')}.json"
            if not file_path.exists():
                with open(file_path, "w", encoding=env.FILE_ENCODING) as file:
                    file.write("{}")

        if env.SETTINGS_PATH.is_file():
            settings = FileManager.fetch_json_file(env.SETTINGS_PATH)
            if not utils.is_dict_complete(settings, env.SETTINGS_FIELDS):
                settings = utils.deep_update(
                    env.SETTINGS_FIELDS, settings
                )
        else:
            settings = env.SETTINGS_FIELDS.copy()

        settings["license-key"] = data.USER["licenseKey"]
        with open(env.SETTINGS_PATH, "w", encoding=env.FILE_ENCODING) as file:
            file.write(json.dumps(
                settings, indent=4
            ))

        if not env.MASTERS_PATH.is_file():
            with open(env.MASTERS_PATH, "w", encoding=env.FILE_ENCODING) as file:
                file.write("Email,Password\n,")

    @staticmethod
    @utils.threaded
    def clear_files():
        site_list, tool_list = ModuleManager.get_modules()
        for module in site_list + tool_list:
            path = (
                (env.SITES_PATH if module in site_list else env.TOOLS_PATH) /
                module.translate(env.ILLEGAL_FILE_CHARS) / env.RESULTS_PATH
            )
            for path in path.iterdir():
                if path.is_dir():
                    if files := list(path.iterdir()):
                        timestamp = max(x.stat().st_mtime for x in files)
                        if utils.calc_ts_delta(timestamp) > 7:
                            shutil.rmtree(path)
                    else:
                        shutil.rmtree(path)

        for site in site_list:
            file_path = env.ENTRIES_PATH / f"{site.lower().replace(' ', '_').strip('.?')}.json"
            with open(file_path, encoding=env.FILE_ENCODING) as file:
                content = json.load(file)

            for key, value in list(content.items()):
                if utils.calc_ts_delta(value["timestamp"]) > 21:
                    del content[key]

            with open(file_path, "w", encoding=env.FILE_ENCODING) as file:
                file.write(json.dumps(
                    content, indent=4
                ))

        for file_path in env.LOGS_PATH.iterdir():
            if utils.calc_ts_delta(file_path.stat().st_mtime) > 21:
                file_path.unlink()

        for file_path in env.TEMP_PATH.iterdir():
            if file_path.name.startswith("analytics") and file_path.name.endswith(".json"):
                timestamp = (
                    file_path.stat().st_ctime if env.OS.Windows else
                    file_path.stat().st_birthtime
                )
                AnalyticsManager.export(
                    file_path, keep_file=utils.calc_ts_delta(timestamp) < 7
                )
            elif utils.calc_ts_delta(file_path.stat().st_mtime) > 0:
                if file_path.is_dir():
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()

    @staticmethod
    @utils.threaded
    def fetch_files_on_interval():
        sites, tools = ModuleManager.get_modules(include_config=True)

        while True:
            for site, config in sites.items():
                path = env.SITES_PATH / site.translate(env.ILLEGAL_FILE_CHARS)
                if config["input"].get("fileType") == "dir":
                    data.SITE_FILES[site] = FileManager.fetch_loaded_dirs(path)
                else:
                    data.SITE_FILES[site] = FileManager.fetch_loaded_csv_files(path)

            for tool, config in tools.items():
                path = env.TOOLS_PATH / tool.translate(env.ILLEGAL_FILE_CHARS)
                if config["input"].get("fileType") == "dir":
                    data.TOOL_FILES[tool] = FileManager.fetch_loaded_dirs(path)
                else:
                    data.TOOL_FILES[tool] = FileManager.fetch_loaded_csv_files(path)

            data.PROXY_FILES = ProxyManager.fetch_loaded_files()

            try:
                data.SETTINGS = utils.deep_update(
                    data.SETTINGS, FileManager.fetch_json_file(env.SETTINGS_PATH)
                )
            except errors.FileError:
                pass

            utils.sleep(2)

    @staticmethod
    @utils.threaded
    def validate_license_on_interval():
        while True:
            utils.sleep(300)

            try:
                response = http.post(
                    f"https://{API_DOMAIN}/auth/{data.USER['licenseKey']}",
                    body={
                        "deviceId": utils.fetch_device_id()
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
                elif response.status == 403:
                    print()
                    logger.error(content["message"])
                    LogManager.write("error", 2, content["message"])
                    utils.close(delay=5)
            except errors.SecurityError as error:
                print()
                logger.error(error.msg)
                LogManager.write("error", 3, error.msg)
                utils.close(delay=5)
            except (errors.HTTPError, errors.JSONError, KeyError):
                continue

    @staticmethod
    @utils.threaded
    def monitor_threats():
        threats = [
            "charles", "fiddler", "wireshark", "postman", "xdbg32", "ghidra", "immunitydebugger",
            "httpdebuggerui", "dnspy", "httpdebuggerpro", "ilspy", "justdecompile", "ida", "ida64",
            "ollydbg", "megadumper", "processhacker", "cheatengine", "codebrowser", "scylla"
        ]

        while True:
            utils.sleep(2)

            try:
                for process in psutil.process_iter():
                    if process.name().lower().split(".")[0].replace(" ", "") in threats:
                        LogManager.write("error", 4, f"possible threat: {process.name()}")
                        utils.close(delay=0)
            except:
                continue

    @staticmethod
    @utils.threaded
    def set_rich_presence(event_loop):
        asyncio.set_event_loop(event_loop)

        try:
            client = Presence(app.DISCORD_ID)
            client.connect()

            client.update(
                large_text=app.NAME,
                large_image="logo_square",
                details=app.MAXIM,
                buttons=[{
                    "label": "Twitter",
                    "url": app.TWITTER_URL
                }],
                start=utils.current_ts()
            )
        except:
            pass
