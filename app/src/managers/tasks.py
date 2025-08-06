# -*- coding: utf-8 -*-
import threading
import traceback
import random
from constants import app, colors, modules
from constants.env import FILE_ENCODING, ILLEGAL_FILE_CHARS, RESULTS_PATH, SITES_PATH, TOOLS_PATH
from common.errors import FileError, TaskError
from common.utils import sleep, current_datetime, joins, hide_file, get_average_length, threaded
from common.ui import logger, set_console_title
from tasks.common.classes import Task, Input, SizeRange
from . import AnalyticsManager, FileManager, EntriesManager, LogManager, ProxyManager, SessionsManager


task_lock = threading.Lock()
file_lock = threading.Lock()
stats_lock = threading.Lock()


class TaskManager:
    parent_fields = [
        "profiles", "tasks"
    ]
    input_fields = [
        "storeLocation", "activeRaffle", "expiredRaffle", "maxEmailAge",
        "instagramAccount", "addressAmount", "emailAmount"
    ]

    def __init__(self, module, submodule, user_input, concurrency):
        self.module = module
        self.submodule = submodule

        self.config = modules.MODULES[module]["submodules"][submodule]
        self.is_site = module in modules.SITE_LIST

        self.module_cls = self.config["module"]
        self.thread_amount, self.thread_delay_range = concurrency

        if any(key in user_input for key in self.parent_fields):
            key = next(
                key for key in self.parent_fields
                if key in user_input
            )

            try:
                self.parents = [
                    self.config["parent"](
                        **{
                            "data": {
                                key.replace("*", ""): value.strip()
                                for key, value in parent.items()
                            }
                        } if "data" in self.config["parent"].fields() else {
                            key.lower().replace(" ", "_"): value.strip()
                            for key, value in parent.items()
                            if key.lower().replace(" ", "_") in self.config["parent"].fields(include_optional=True)
                        },
                        ctx={"module": module}
                    ) for parent in FileManager.fetch_csv_files(
                        (SITES_PATH if self.is_site else TOOLS_PATH) / module.translate(ILLEGAL_FILE_CHARS)
                        / (user_input["form"]["dirName"] if user_input.get("form") else ""),
                        user_input[key]
                    )
                ]
            except TypeError:
                self.parents = []

            if not self.parents:
                raise TaskError(f"No valid {key} found")

            self.parents_title = (
                user_input[key][0] + (", ..." if len(user_input[key]) > 1 else "")
            )
        else:
            self.parents = None
            self.parents_title = None

        if proxy_files := user_input.get("proxies"):
            if proxy_files == ["localhost"]:
                self.proxy_manager = ProxyManager(is_localhost=True)
                self.proxies_title = "localhost"
            else:
                self.proxy_manager = ProxyManager(files=proxy_files)
                if not self.proxy_manager.all_proxies:
                    raise TaskError("No valid proxies found")

                self.proxies_title = (
                    proxy_files[0] + (", ..." if len(proxy_files) > 1 else "")
                )
        else:
            self.proxy_manager = None
            self.proxies_title = None

        if any(key in user_input for key in self.input_fields):
            self.input = Input(**{
                key: value for keyword in self.input_fields
                if keyword in user_input for key, value in user_input[keyword].items()
            })
        elif module == "Google Forms" and submodule == "Enter form":
            try:
                self.input = Input(
                    form=FileManager.fetch_json_file(
                        SITES_PATH / module.translate(ILLEGAL_FILE_CHARS) /
                        user_input["form"]["dirName"] / ".configuration.json"
                    )
                )
            except FileError:
                raise TaskError("Invalid form template")
        else:
            self.input = None

        if size_range := user_input.get("sizeRange"):
            self.input.size_range = SizeRange(size_range)

        if cls := self.config.get("hook"):
            self.hook = cls(self)
        else:
            self.hook = None

        if self.config["subject"] in ["entries", "wins"]:
            self.analytics = AnalyticsManager(
                module, self.config["subject"]
            )
        else:
            self.analytics = None

        if self.config["subject"] == "entries":
            self.entries = EntriesManager(
                module, self.input.raffle.get("url") or self.input.raffle.get("id")
            )

            self.parents = self.entries.filter(self.parents)
            if not self.parents:
                raise TaskError("Tasks are already entered")
        else:
            self.entries = None

        self.sessions = SessionsManager(module)

        if self.parents:
            self.tasks = [
                Task(
                    id=self.format_task_id(index + 1),
                    manager=self,
                    parent=parent,
                    proxies=self.proxy_manager,
                    input=self.input
                ) for index, parent in enumerate(self.parents)
            ]
        elif module == "Google Forms" and submodule == "Scrape form":
            self.tasks = [
                Task(
                    id=self.format_task_id(1),
                    manager=self,
                    proxies=self.proxy_manager,
                    input=self.input
                )
            ]
        elif module == "Geocoding":
            self.tasks = [
                Task(
                    id=self.format_task_id(1),
                    manager=self,
                    parent=self.config["parent"](
                        **user_input["geoSeed"]
                    ),
                    proxies=self.proxy_manager,
                    input=self.input
                )
            ]
        else:
            self.tasks = []

        self.results_path = (
            (SITES_PATH if self.is_site else TOOLS_PATH) / module.translate(ILLEGAL_FILE_CHARS) /
            RESULTS_PATH / f"{submodule} ({current_datetime(filename_proof=True)})"
        )

        if self.config["output"]:
            self.results_files = {
                key: self.results_path / f"{key}.csv"
                for key in self.config["statuses"] if key != "pending"
            }
            self.results_fields = [
                key.capitalize().replace("_", " ").replace("Paypal", "PayPal")
                for key in self.config["output"]
            ]
        else:
            self.results_files = {}
            self.results_fields = []

        self.stats = {
            key: (
                0 if key != "pending" else
                self.input.amount if module in ["Geocoding", "iCloud"] else
                len(self.tasks)
            ) for key in self.config["statuses"]
        }

        if self.config["parent"]:
            self.avg_parent_length = get_average_length(
                self.tasks, lambda x: x.parent.id
            )
        else:
            self.avg_parent_length = None

        self.index = 0
        self.threads = []
        self.failed = []
        self.is_initial = True

    def __iter__(self):
        return self

    def __next__(self):
        with task_lock:
            self.index += 1
            try:
                return self.tasks[self.index - 1]
            except IndexError:
                raise StopIteration

    @staticmethod
    def print_seperator():
        pass

    @staticmethod
    def format_task_id(index):
        return str(index).rjust(4, "0")

    def format_parent_id(self, parent_id, length=None):
        length = length or self.avg_parent_length

        if len(parent_id) <= length:
            return parent_id.ljust(length)
        else:
            return parent_id[:length - 2] + ".."

    def calculate_delay(self):
        if self.thread_delay_range[0] == self.thread_delay_range[1]:
            return self.thread_delay_range[0]
        else:
            return random.randrange(*self.thread_delay_range)

    def refresh_vars(self):
        self.sessions = SessionsManager(self.module)

        self.stats = {
            key: (
                0 if key != "pending" else
                self.input.amount if self.module in ["Geocoding", "iCloud"] else
                len(self.tasks)
            ) for key in self.config["statuses"]
        }

        if self.config["parent"]:
            self.avg_parent_length = get_average_length(
                self.tasks, lambda x: x.parent.id
            )
        else:
            self.avg_parent_length = None

        self.index = 0
        self.failed = []

    def add_task(self, parent, **kwargs):
        with task_lock:
            self.tasks.append(
                Task(
                    id=self.format_task_id(len(self.tasks) + 1),
                    manager=self,
                    parent=parent,
                    proxies=self.proxy_manager,
                    input=kwargs.get("input") or self.input
                )
            )

    def launcher(self):
        for index, task in enumerate(self):
            if self.thread_amount == 1 and index > 0:
                print()
                if delay := self.calculate_delay():
                    logger.log(f"Waiting {delay} second{'s' if delay != 1 else ''}...", colors.GREY)
                    sleep(delay)
                    print()

            instance = self.module_cls(task)

            try:
                instance.execute()
            except:
                instance.logger.error("Unexpected error")
                LogManager.write("error", 5, traceback.format_exc().strip())
                self.increment("failed", task=task, write_result=False)

    def start(self):
        self.set_console_title()

        if self.is_initial:
            self.build_files()

            if self.hook:
                if self.hook.execute():
                    self.refresh_vars()
                    self.set_console_title()
                    self.print_seperator()
                else:
                    return

        self.threads = [
            threading.Thread(target=self.launcher)
            for _ in range(self.thread_amount)
        ]

        for thread in self.threads:
            thread.start()

    def join(self):
        for thread in self.threads:
            thread.join()

    @threaded
    def finish(self):
        if self.analytics:
            self.analytics.export()

    def rerun_failed(self):
        self.tasks = self.failed.copy()

        self.refresh_vars()
        self.is_initial = False

        self.start()

    def build_files(self):
        try:
            if not self.results_path.is_dir():
                self.results_path.mkdir()

            for file_path in self.results_files.values():
                with open(file_path, "w", encoding=FILE_ENCODING) as file:
                    file.write(",".join(self.results_fields) + "\n")
        except (FileNotFoundError, PermissionError):
            pass

    def set_console_title(self):
        set_console_title(
            app.NAME + "  •  " + joins(
                self.module, self.parents_title, self.proxies_title,
                " - ".join(f"{key.replace('_', ' ').capitalize()}: {value}" for key, value in self.stats.items()) or None,
                sep="  |  "
            )
        )

    def write_result(self, status, **kwargs):
        with file_lock:
            try:
                with open(self.results_files[status], "a", encoding=FILE_ENCODING) as file:
                    file.write(joins(
                        kwargs["location"] if "Location" in self.results_fields else None,
                        kwargs["product"].name if "Product" in self.results_fields else None,
                        kwargs["product"].size if "Size" in self.results_fields else None,
                        kwargs["raffle"] if "Raffle" in self.results_fields else None,
                        kwargs["message"].sender if "Sender" in self.results_fields else None,
                        kwargs["message"].text if "Message" in self.results_fields else None,
                        *(
                            kwargs["parent"].values() if isinstance(kwargs["parent"], dict) else
                            kwargs["parent"].json().values()
                        ),
                        kwargs["proxy"].line if "Proxy" in self.results_fields else None,
                        sep=",", modifier=lambda x: f'"{x}"' if "," in x else x
                    ) + "\n")
            except (FileNotFoundError, PermissionError):
                pass

    def write_custom_result(self, files, files_to_hide=None):
        try:
            for dir_name, files in files.items():
                path = self.results_path / dir_name.translate(ILLEGAL_FILE_CHARS)

                path.mkdir()
                for file_name, content in files.items():
                    with open(path / file_name, "w", encoding=FILE_ENCODING) as file:
                        if ".csv" in file_name:
                            file.write("\n".join((
                                joins(
                                    *content.keys(),
                                    sep=",", modifier=lambda x: f'"{x}"' if "," in x else x
                                ),
                                joins(
                                    *content.values(),
                                    sep=",", modifier=lambda x: f'"{x}"' if "," in x else x
                                )
                            )))
                        else:
                            file.write(content)

                    if files_to_hide and file_name in files_to_hide:
                        hide_file(path / file_name)
        except (FileNotFoundError, PermissionError):
            pass

    def increment(self, status, write_result=True, **kwargs):
        is_success = status == self.config["statuses"][1]

        with stats_lock:
            self.stats["pending"] -= 1
            self.stats[status] += 1

            if status == "failed":
                self.failed.append(kwargs["task"])

        self.set_console_title()
        if write_result and not (status == "failed" and not self.is_initial):
            self.write_result(status, **kwargs)

        if is_success and self.analytics and kwargs.get("product"):
            self.analytics.increment(kwargs["product"])
        if is_success and self.entries and kwargs.get("parent"):
            self.entries.save(kwargs["parent"])
