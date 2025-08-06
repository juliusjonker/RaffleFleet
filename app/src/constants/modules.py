# -*- coding: utf-8 -*-
SITE_LIST = [
    "24Segons",
    "4Elementos",
    "Adidas Confirmed",
    "Afew",
    "Baseline",
    "BSTN",
    "Empire Skate",
    "Fenom",
    "Footpatrol",
    "Footshop",
    "Impact Premium",
    "Instagram",
    "JD Sports",
    "Kickz",
    "Kith EU",
    "Naked",
    "Shelflife",
    "Size?",
    "The Hip Store",
    "Tops & Bottoms"
]

TOOL_LIST = [
    "Geocoding",
    "iCloud"
]

SITES = {
    site.NAME: {
        "submodules": site.SUBMODULES if hasattr(site, "SUBMODULES") else {},
        "input": site.INPUT_CONFIG if hasattr(site, "INPUT_CONFIG") else {},
        "isSecret": hasattr(site, "IS_SECRET")
    } for site in [
        __import__(
            "tasks.modules.sites." +
            site.lower().replace(" ", "_").replace("&", "and").strip("0123456789.?"),
            fromlist="object"
        ) for site in SITE_LIST
    ]
}

TOOLS = {
    tool.NAME: {
        "submodules": tool.SUBMODULES if hasattr(tool, "SUBMODULES") else {},
        "input": tool.INPUT_CONFIG if hasattr(tool, "INPUT_CONFIG") else {},
        "isSecret": hasattr(tool, "IS_SECRET")
    } for tool in [
        __import__(
            "tasks.modules.tools." +
            tool.lower().replace(" ", "_").replace("&", "and").strip("0123456789.?"),
            fromlist="object"
        ) for tool in TOOL_LIST
    ]
}

MODULES = SITES | TOOLS
MODULE_LIST = [*MODULES]
