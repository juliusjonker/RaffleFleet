# -*- coding: utf-8 -*-
from tasks.common.classes import GeoSeed
from .constants import NAME
from .generate_addresses import GenerateAddresses


SUBMODULES = {
    "Generate addresses": {
        "module": GenerateAddresses,
        "parent": GeoSeed,
        "subject": "addresses",
        "input": ["geoSeed", "addressAmount"],
        "output": ["street", "house_number", "line_2", "city", "postcode", "province", "country"],
        "statuses": ["pending", "generated"],
        "isMultiThreaded": False
    }
}
