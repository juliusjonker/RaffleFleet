# -*- coding: utf-8 -*-
from constants import modules
from common import data
from common.utils import current_ts


class ModuleManager:
    @staticmethod
    def get_modules(include_config=False):
        if include_config:
            return {
                site: config for site, config in modules.SITES.items()
                if not config.get("isSecret") or site in data.USER["secretModules"]
            }, {
                tool: config for tool, config in modules.TOOLS.items()
                if not config.get("isSecret") or tool in data.USER["secretModules"]
            }
        else:
            return [
                site for site, config in modules.SITES.items()
                if not config.get("isSecret") or site in data.USER["secretModules"]
            ], [
                tool for tool, config in modules.TOOLS.items()
                if not config.get("isSecret") or tool in data.USER["secretModules"]
            ]

    @staticmethod
    def get_sites():
        return [
            site for site, config in modules.SITES.items()
            if not config.get("isSecret") or site in data.USER["secretModules"]
        ]

    @staticmethod
    def get_tools():
        return [
            tool for tool, config in modules.TOOLS.items()
            if not config.get("isSecret") or tool in data.USER["secretModules"]
        ]

    @staticmethod
    def get_submodules(module):
        return [*modules.MODULES[module]["submodules"]]

    @staticmethod
    def is_module_disabled(module, submodule):
        return (
            module in data.APP["disabledModules"] or
            f"{module}.{submodule}" in data.APP["disabledModules"]
        )

    @staticmethod
    def is_module_runnable(module, submodule):
        if ModuleManager.is_module_disabled(module, submodule):
            return False, "Option is locked"

        required_input = modules.MODULES[module]["submodules"][submodule]["input"]
        module_files = (
            data.SITE_FILES[module] if module in modules.SITE_LIST else
            data.TOOL_FILES[module]
        )

        if "activeRaffle" in required_input or "expiredRaffle" in required_input:
            loaded_raffles = ModuleManager.get_raffles(
                module, "active" if "activeRaffle" in required_input else "expired"
            )

            if not loaded_raffles and "expiredRaffle" in required_input:
                return False, "No raffles loaded"

        if "form" in required_input and not module_files:
            return False, "No form template loaded"

        if "profiles" in required_input and not module_files:
            return False, "No profiles loaded"

        if "tasks" in required_input and not module_files:
            return False, "No tasks loaded"

        if "proxies" in required_input and not data.PROXY_FILES:
            return False, "No proxies loaded"

        return True, None

    @staticmethod
    def get_raffles(site, category):
        raffles = {
            "active": {},
            "expired": {}
        }

        for product_name, raffle in data.RAFFLES.get(site, {}).items():
            if not raffle["expiry"] or raffle["expiry"] > current_ts():
                raffles["active"][product_name] = raffle
            else:
                raffles["expired"][product_name] = raffle

        return dict(sorted(
            raffles[category].items(),
            key=lambda x: x[1]["expiry"] or 0,
            reverse=(category == "expired")
        ))

    @staticmethod
    def get_raffle_entries(site, product_name):
        try:
            return data.USER["analytics"][site][product_name]["entries"]
        except KeyError:
            return 0
