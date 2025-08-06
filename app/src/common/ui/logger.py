# -*- coding: utf-8 -*-
from constants import colors
from constants.env import OS
from common.utils import current_datetime, joins


def success(msg, short=False):
    print(
        (" " if short else "  ") +
        f"%s{'✓' if OS.advanced_chars else '●'}%s " % colors.GREEN + msg
    )


def error(msg, short=False):
    print(
        (" " if short else "  ") +
        f"%s{'✕' if OS.advanced_chars else '●'}%s " % colors.RED + msg
    )


def log(msg, color=colors.WHITE):
    print(joins(
        f" %s{current_datetime()}%s" % colors.DARK_GREY, f"%s{msg}%s" % color,
        sep=" %s|%s " % colors.GREY
    ))
