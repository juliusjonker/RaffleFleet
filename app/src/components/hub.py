# -*- coding: utf-8 -*-
from constants import app, colors
from constants.modules import SITE_LIST
from common import ui
from common.utils import get_choice, sleep
from managers import EntriesManager, LogManager, ModuleManager, SessionsManager, TaskManager
from .module_init import ModuleInit


class Hub:
    header_indent = " " * 10
    header_width, header_height = 50, 9
    menu_width, menu_height = 20, 8

    def __init__(self):
        ui.clear()
        ui.set_console_title(app.NAME)

        self.print_header()

        ModuleInit.print_seperator = self.print_seperator
        TaskManager.print_seperator = self.print_seperator

    def print_header(self):
        print(rf"""%s
{self.header_indent} ____        __  __ _       _____ _           _   
{self.header_indent}│  _ \ __ _ / _│/ _│ │ ___ │  ___│ │ ___  ___│ │_ 
{self.header_indent}│ │_) / _` │ │_│ │_│ │/ _ \│ │_  │ │/ _ \/ _ \ __│
{self.header_indent}│  _ < (_│ │  _│  _│ │  __/│  _│ │ │  __/  __/ │_ 
{self.header_indent}│_│ \_\__,_│_│ │_│ │_│\___││_│   │_│\___│\___│\__│
        %s""" % colors.MAIN)

        self.print_seperator(enter=False)

    def print_seperator(self, enter=True):
        print(
            f"\n %s{'─' * (self.header_width + 2 * (len(self.header_indent) - 1))}%s" % colors.MAIN,
            end="\n\n" if enter else "\n"
        )

    def print_header_title(self, title):
        print(
            f"\033[{self.header_height};3H %s{title} {'─' * 25}%s" % colors.MAIN
        )

    def main_menu(self):
        ui.clear(limit=self.header_height + 1)
        self.print_header_title("Menu")
        print()

        site_list = ModuleManager.get_sites()
        final_index = len(site_list) + 1

        lines = [
            " " for _ in range(self.menu_height)
        ]
        for index, site in enumerate(site_list):
            lines[index % self.menu_height] += (
                f"%s{index + 1}.%s ".rjust(8) % colors.GREY +
                site.ljust(self.menu_width)
            )

        lines[(final_index - 1) % self.menu_height] += (
            (f"%s{final_index}. ".rjust(6) + "Tools%s") % colors.GREY
        )

        print(
            "\n".join(lines),
            end="\n\n"
        )

        while True:
            choice = ui.fetch_input(
                "Select an option", color=colors.GREY
            )

            if module := get_choice(choice, site_list):
                break
            elif choice.lower().replace(" ", "") in [str(final_index), "tools"]:
                self.tools_menu()
            elif EntriesManager.is_clear_command(choice):
                EntriesManager.clear(choice)
            elif SessionsManager.is_clear_command(choice):
                SessionsManager.clear(choice)
            elif LogManager.is_export_command(choice):
                LogManager.export(choice)
            else:
                ui.logger.error("That's not an option")

            sleep(2), ui.recede_cursor(2)

        self.module_menu(module)

    def tools_menu(self):
        ui.clear(limit=self.header_height + 1)
        self.print_header_title("Tools")
        print()

        tool_list = ModuleManager.get_tools()

        lines = [
            "  %s0. Back%s" % colors.GREY
        ]
        for index, tool in enumerate(tool_list):
            lines.append(
                f"%s{index + 1}.%s ".rjust(9) % colors.GREY + tool
            )

        print(
            "\n".join(lines),
            end="\n\n"
        )

        while True:
            choice = ui.fetch_input(
                "Select an option", color=colors.GREY
            )

            if module := get_choice(choice, tool_list):
                break
            elif choice.lower().replace(" ", "") in ["0", "back"]:
                self.main_menu()
            else:
                ui.logger.error("That's not an option")

            sleep(2), ui.recede_cursor(2)

        self.module_menu(module)

    def module_menu(self, module):
        ui.clear(limit=self.header_height + 1)
        self.print_header_title(module)
        print()

        submodules = ModuleManager.get_submodules(module)

        lines = [
            "  %s0. Back%s" % colors.GREY
        ]
        for index, submodule in enumerate(submodules):
            lines.append(
                f"%s{index + 1}.%s ".rjust(9) % colors.GREY + submodule
            )

        print(
            "\n".join(lines),
            end="\n\n"
        )

        while True:
            choice = ui.fetch_input(
                "Select an option", color=colors.GREY
            )

            if submodule := get_choice(choice, submodules):
                status, msg = ModuleManager.is_module_runnable(module, submodule)
                if status:
                    break
                else:
                    ui.logger.error(msg)
            elif choice.lower().replace(" ", "") in ["0", "back"]:
                if module in SITE_LIST:
                    self.main_menu()
                else:
                    self.tools_menu()
            else:
                ui.logger.error("That's not an option")

            sleep(2), ui.recede_cursor(2)

        self.module_init(module, submodule)

    def module_init(self, module, submodule):
        ui.clear(limit=self.header_height + 1)
        self.print_header_title(module)

        ModuleInit(module, submodule)

        Hub().module_menu(module)
