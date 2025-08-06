# -*- coding: utf-8 -*-
from functools import partial
from constants import colors, modules, regexes
from common import data, ui, utils
from common.errors import TaskError
from managers import ModuleManager, TaskManager


class ModuleInit:
    def __init__(self, module, submodule):
        self.module = module
        self.submodule = submodule

        self.module_config = modules.MODULES[module]["submodules"][submodule]
        self.input_config = modules.MODULES[module]["input"]
        self.is_site = module in modules.SITE_LIST

        self.input = {}

        self.functions = {
            "storeLocation": self.fetch_store_location_input,
            "activeRaffle": partial(self.fetch_raffle_input, "active"),
            "expiredRaffle": partial(self.fetch_raffle_input, "expired"),
            "sizeRange": self.fetch_size_range_input,
            "form": partial(self.fetch_dir_input, "form"),
            "maxEmailAge": self.fetch_max_email_age_input,
            "instagramAccount": self.fetch_instagram_account_input,
            "geoSeed": self.fetch_geo_seed_input,
            "addressAmount": partial(self.fetch_amount_input, "addresses"),
            "emailAmount": partial(self.fetch_amount_input, "emails"),
            "profiles": partial(self.fetch_file_input, "profiles"),
            "tasks": partial(self.fetch_file_input, "tasks"),
            "proxies": partial(self.fetch_file_input, "proxies")
        }

        self.initialize()

    @staticmethod
    def print_seperator():
        pass

    def initialize(self):
        for key in self.module_config["input"]:
            self.input[key] = self.functions[key]()

        if self.module_config["isMultiThreaded"]:
            concurrency = self.fetch_concurrency_input()
        else:
            concurrency = 1, (0, 0)

        print(), ui.enter()
        loading_bar = ui.LoadingBar(
            "Preparing tasks", short=True, min_duration=.75
        )

        try:
            tasks = TaskManager(
                self.module, self.submodule, self.input, concurrency
            )
        except TaskError as error:
            loading_bar.error(error.msg)
            utils.sleep(2)
            return

        loading_bar.success("Prepared tasks")
        self.print_seperator()

        tasks.start()

        while True:
            tasks.join()

            self.print_seperator()
            ui.logger.success("Completed tasks", short=True)
            print()

            if tasks.failed:
                if self.fetch_retry_tasks_input(len(tasks.failed)):
                    self.print_seperator()
                    tasks.rerun_failed()
                else:
                    break
            else:
                ui.fetch_input(
                    "Press ENTER to go back to Hub", color=colors.GREY
                )
                break

        tasks.finish()

    def fetch_store_location_input(self):
        print()

        locations = self.input_config["location"]["options"]

        lines = []
        for index, location in enumerate(locations):
            lines.append(
                f"%s{index + 1}.%s ".rjust(9) % colors.GREY +
                location["name"]
            )

        print(
            "\n".join(lines),
            end="\n\n"
        )

        while True:
            choice = ui.fetch_input(
                "Select an option", color=colors.GREY
            )

            if location := utils.get_choice(choice, locations, digit_only=True):
                break
            else:
                ui.logger.error("That's not an option")
                utils.sleep(2), ui.recede_cursor(2)

        print()
        ui.logger.success(
            "Selected location: " + location["name"],
            short=True
        )

        return {
            "location": location
        }

    def fetch_raffle_input(self, status):
        loaded_raffles = ModuleManager.get_raffles(self.module, status)
        if not loaded_raffles:
            return self.fetch_manual_raffle_input()

        print()

        allow_manual_input = status != "expired"
        final_index = len(loaded_raffles) + 1
        raffle_length = len(max(loaded_raffles, key=len)) + 3

        try:
            expiry_length = len(max([
                utils.prettify_ts_delta(raffle["expiry"])
                for raffle in loaded_raffles.values() if raffle["expiry"]
            ], key=len)) + 2
        except ValueError:
            expiry_length = -2

        lines = []
        for index, (product_name, raffle) in enumerate(loaded_raffles.items()):
            entries = ModuleManager.get_raffle_entries(self.module, product_name)

            lines.append(
                f"%s{index + 1}.%s ".rjust(9) % colors.GREY +
                product_name.ljust(raffle_length) + (
                    f"%s│ {utils.prettify_ts_delta(raffle['expiry'])}%s".ljust(expiry_length + 6) % colors.MAIN
                    if raffle["expiry"] and status == "active" else
                    " " * (expiry_length + 2) if status == "active" else ""
                ) + (f"%s│ Entries: {entries}%s" % colors.DARK_GREY if entries else "")
            )

        if allow_manual_input:
            lines.append(
                (f"%s{final_index}. ".rjust(7) + "Other%s") % colors.GREY
            )

        print(
            "\n".join(lines),
            end="\n\n"
        )

        while True:
            choice = ui.fetch_input(
                "Select an option", color=colors.GREY
            )

            if product_name := utils.get_choice(choice, [*loaded_raffles], digit_only=True):
                break
            elif choice.lower().replace(" ", "") in [str(final_index), "other"] and allow_manual_input:
                return self.fetch_manual_raffle_input()
            else:
                ui.logger.error("That's not an option")
                utils.sleep(2), ui.recede_cursor(2)

        print()
        ui.logger.success(
            f"Selected raffle: {product_name}", short=True
        )

        return {
            "raffle": {
                "productName": product_name,
                **loaded_raffles[product_name]["input"]
            }
        }

    def fetch_manual_raffle_input(self):
        print()

        raffle_type = self.input_config["raffle"]["type"]
        raffle_regex = self.input_config["raffle"]["regex"]

        while True:
            choice = ui.fetch_input(
                f"Raffle {raffle_type}", color=colors.GREY
            )

            if raffle_regex.match(choice):
                raffle = choice
                break
            else:
                ui.logger.error(f"That's an invalid {raffle_type}")
                utils.sleep(2), ui.recede_cursor(2)

        print()
        ui.logger.success(
            f"Selected raffle: {raffle.removeprefix('https://')}", short=True
        )

        return {
            "raffle": {
                raffle_type: raffle
            }
        }

    def fetch_size_range_input(self):
        print()

        size_chart = self.input_config["size"]["chart"]
        size_regex = self.input_config["size"]["regex"]

        while True:
            choice = ui.fetch_input(
                f"Minimum size ({size_chart})" if size_chart else "Minimum size",
                color=colors.GREY
            )

            if size_regex.match(choice):
                minimum_size = choice.lower().replace("eu", "").replace("uk", "").replace("us", "").strip()
                break
            elif choice.lower().replace(" ", "") in ["0", "all", "allsizes", "full", "fullrange"]:
                print()
                ui.logger.success(
                    "Selected size range: All sizes", short=True
                )
                return 0, 100
            else:
                ui.logger.error(
                    f"That's an invalid {size_chart} size" if size_chart else
                    "That's an invalid size"
                )
                utils.sleep(2), ui.recede_cursor(2)

        while True:
            choice = ui.fetch_input(
                f"Maximum size ({size_chart})" if size_chart else "Maximum size",
                color=colors.GREY
            )

            if size_regex.match(choice):
                maximum_size = choice.lower().replace("eu", "").replace("uk", "").replace("us", "").strip()
                break
            else:
                ui.logger.error(
                    f"That's an invalid {size_chart} size" if size_chart else
                    "That's an invalid size"
                )
                utils.sleep(2), ui.recede_cursor(2)

        print()
        ui.logger.success(
            f"Selected size range: {minimum_size} - {maximum_size}", short=True
        )

        return tuple(sorted((
            utils.size_to_float(minimum_size),
            utils.size_to_float(maximum_size)
        )))

    @staticmethod
    def fetch_max_email_age_input():
        print()

        while True:
            choice = ui.fetch_input(
                "Maximum age of emails (days)", color=colors.GREY
            )

            if choice.isdigit() and int(choice) >= 0:
                max_age = int(choice)
                break
            else:
                ui.logger.error("That's an invalid age")
                utils.sleep(2), ui.recede_cursor(2)

        print()
        ui.logger.success(
            f"Selected maximum age: {max_age} day{'s' if max_age != 1 else ''}",
            short=True
        )

        return {
            "emails": {
                "maxAge": max_age
            }
        }

    @staticmethod
    def fetch_instagram_account_input():
        print()

        while True:
            choice = ui.fetch_input(
                "Sender username", color=colors.GREY
            )

            if choice:
                username = ("@" if not choice.startswith("@") else "") + choice.lower()
                break
            else:
                ui.logger.error("That's an invalid username")
                utils.sleep(2), ui.recede_cursor(2)

        print()
        ui.logger.success(
            f"Selected username: {username}", short=True
        )

        return {
            "instagram": {
                "account": username
            }
        }

    @staticmethod
    def fetch_geo_seed_input():
        print()

        while True:
            choice = ui.fetch_input(
                "Country", color=colors.GREY
            )

            if choice.upper().replace(".", "") in data.COUNTRY_DATA:
                country = choice.upper().replace(".", "")
                break
            elif choice.lower().replace(" ", "").replace("-", "").replace("'", "") in data.COUNTRY_IDS:
                country = data.COUNTRY_IDS[
                    choice.lower().replace(" ", "").replace("-", "").replace("'", "")
                ]
                break
            else:
                ui.logger.error("That's an invalid country")
                utils.sleep(2), ui.recede_cursor(2)

        while True:
            choice = ui.fetch_input(
                "City, postcode or coordinate", color=colors.GREY
            )

            if regexes.COORDINATE.match(choice):
                coordinate = (
                    float(choice.split(",")[0]),
                    float(choice.split(",")[1].strip())
                )
                address = None
                break
            elif coordinate := utils.fetch_coordinate(country, choice):
                address = choice
                break
            else:
                ui.logger.error("That's an invalid city, postcode or coordinate")
                utils.sleep(2), ui.recede_cursor(2)

        print()

        while True:
            choice = ui.fetch_input(
                "Maximum radius (km)", color=colors.GREY
            ).replace(",", ".")

            if choice.replace(".", "", 1).isdigit() and float(choice) > 0:
                radius = float(choice)
                break
            else:
                ui.logger.error("That's an invalid radius")
                utils.sleep(2), ui.recede_cursor(2)

        print()
        ui.logger.success(
            f"Selected seed: Within {radius} km around " + (
                f"{address}, {country}" if address else ", ".join(str(x) for x in coordinate)
            ), short=True
        )

        return {
            "country": country,
            "coordinate": coordinate,
            "radius": radius
        }

    @staticmethod
    def fetch_amount_input(category):
        print()

        while True:
            choice = ui.fetch_input(
                f"Amount of {category}", color=colors.GREY
            )

            if choice.isdigit() and int(choice) > 0:
                amount = int(choice)
                break
            else:
                ui.logger.error("That's an invalid amount")
                utils.sleep(2), ui.recede_cursor(2)

        print()
        ui.logger.success(
            f"Selected amount: {amount} {category}",
            short=True
        )

        return {
            "amount": amount
        }

    def fetch_file_input(self, category):
        print()

        loaded_files = (
            self.input["form"]["files"] if self.input.get("form") and category == "profiles" else
            data.PROXY_FILES if category == "proxies" else
            data.SITE_FILES[self.module] if self.is_site else
            data.TOOL_FILES[self.module]
        )
        final_index = len(loaded_files) + 1
        file_length = len(max(
            loaded_files, key=lambda x: len(x["fileName"])
        )["fileName"]) + 3

        if len(loaded_files) == 1 and category != "proxies":
            files = [loaded_files[0]["fileName"]]
            ui.logger.success(f"Loaded {category}: {files[0]}", short=True)
            return files

        lines = []
        if category == "proxies":
            lines.append(
                "  %s0. localhost%s" % colors.GREY
            )

        for index, file in enumerate(loaded_files):
            lines.append(
                f"%s{index + 1}.%s ".rjust(9) % colors.GREY +
                file["fileName"].ljust(file_length) +
                f"%s│ {category.capitalize()}: {file['lineCount']}%s" % colors.DARK_GREY
            )

        if len(loaded_files) > 1:
            lines.append(
                (f"%s{final_index}. ".rjust(7) + "Select all%s") % colors.GREY
            )

        print(
            "\n".join(lines),
            end="\n\n"
        )

        while True:
            choice = ui.fetch_input(
                "Select one or more options" if len(loaded_files) > 1 else "Select an option",
                color=colors.GREY
            )

            if files := utils.get_choices(choice, loaded_files):
                files = [file["fileName"] for file in files]
                break
            elif choice.lower().replace(" ", "") in [str(final_index), "all", "selectall"] and len(loaded_files) > 1:
                files = [file["fileName"] for file in loaded_files]
                break
            elif choice.lower().replace(" ", "") in ["0", "localhost", "local"] and category == "proxies":
                files = ["localhost"]
                break
            else:
                ui.logger.error("That's not an option")
                utils.sleep(2), ui.recede_cursor(2)

        print()
        ui.logger.success(
            f"Selected {category}: {files[0]}" +
            (f", {len(files) - 1} more..." if len(files) > 1 else ""),
            short=True
        )

        return files

    def fetch_dir_input(self, category):
        print()

        loaded_dirs = (
            data.SITE_FILES[self.module] if self.is_site else
            data.TOOL_FILES[self.module]
        )
        dir_length = len(max(
            loaded_dirs, key=lambda x: len(x["dirName"])
        )["dirName"]) + 3

        lines = []
        for index, directory in enumerate(loaded_dirs):
            lines.append(
                f"%s{index + 1}.%s ".rjust(9) % colors.GREY +
                directory["dirName"].ljust(dir_length) +
                f"%s│ Files: {directory['fileCount']}%s" % colors.DARK_GREY
            )

        print(
            "\n".join(lines),
            end="\n\n"
        )

        while True:
            choice = ui.fetch_input(
                "Select an option", color=colors.GREY
            )

            if directory := utils.get_choice(choice, loaded_dirs, digit_only=True):
                break
            else:
                ui.logger.error("That's not an option")
                utils.sleep(2), ui.recede_cursor(2)

        print()
        ui.logger.success(
            f"Selected {category}: {directory['dirName']}", short=True
        )

        return directory

    @staticmethod
    def fetch_concurrency_input():
        print()

        while True:
            choice = ui.fetch_input(
                "Amount of threads (simultaneous tasks)", color=colors.GREY
            )

            if choice.isdigit() and int(choice) > 0:
                thread_amount = int(choice)
                break
            else:
                ui.logger.error("That's an invalid amount")
                utils.sleep(2), ui.recede_cursor(2)

        if thread_amount > 1:
            print()
            ui.logger.success(
                f"Selected concurrency: {thread_amount} threads",
                short=True
            )
            return thread_amount, (0, 0)

        print()

        while True:
            choice = ui.fetch_input(
                "Minimum task delay (seconds)", color=colors.GREY
            )

            if choice.isdigit() and int(choice) >= 0:
                minimum_delay = int(choice)
                break
            else:
                ui.logger.error("That's an invalid delay")
                utils.sleep(2), ui.recede_cursor(2)

        while True:
            choice = ui.fetch_input(
                "Maximum task delay (seconds)", color=colors.GREY
            )

            if choice.isdigit() and int(choice) >= 0:
                maximum_delay = int(choice)
                break
            else:
                ui.logger.error("That's an invalid delay")
                utils.sleep(2), ui.recede_cursor(2)

        print()

        ui.logger.success(
            f"Selected concurrency: 1 thread with " + (
                f"{minimum_delay}s delay" if minimum_delay == maximum_delay else
                f"{minimum_delay}-{maximum_delay}s delay"
            ), short=True
        )

        return 1, tuple(sorted((
            minimum_delay, maximum_delay
        )))

    @staticmethod
    def fetch_retry_tasks_input(failed_count):
        while True:
            choice = ui.fetch_input(
                f"Retry {failed_count} failed task{'s' if failed_count > 1 else ''}? (Yes/No)",
                color=colors.GREY
            )

            formatted_choice = choice.lower().replace(" ", "")
            if formatted_choice in ["yes", "y", "yeah"]:
                retry_failed = True
                break
            elif formatted_choice in ["no", "n", "nope"]:
                retry_failed = False
                break
            else:
                ui.logger.error("That's not an option")
                utils.sleep(2), ui.recede_cursor(2)

        if retry_failed:
            print()
            ui.logger.success(
                f"Selected option: Retry failed tasks", short=True
            )

        return retry_failed
