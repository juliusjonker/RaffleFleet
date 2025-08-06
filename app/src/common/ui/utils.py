# -*- coding: utf-8 -*-
import os
import sys
import ctypes
from constants import colors
from constants.env import OS


def clear(limit=None):
    if limit:
        width, height = os.get_terminal_size()

        print(
            f"\033[{limit};0H" +
            (" " * width + "\n") * (height - limit) +
            f"\033[{limit};0H", end="\r"
        )
    else:
        os.system(
            "cls" if OS.Windows else "clear"
        )


def recede_cursor(lines):
    width = os.get_terminal_size().columns

    for _ in range(lines):
        print(f"\033[F{' ' * width}", end="\r")


def enter():
    print("\n\033[F", end="\r")


def set_console_title(title):
    if OS.Windows:
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    else:
        sys.stdout.write(f"\x1b]2;{title}\x07")


def fetch_input(prompt, loading_bar=False, color=colors.WHITE):
    prompt += ": "
    if loading_bar:
        prompt = f"  %s●●●%s " % colors.MAIN + f"%s{prompt}%s" % color
    else:
        prompt = f" %s{prompt}%s" % color

    enter()
    return input(prompt).strip()
