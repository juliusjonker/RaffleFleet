# -*- coding: utf-8 -*-
import re


URL = re.compile(r"^https://{}/\S+$")
PROXY = re.compile(r"^[a-zA-Z0-9-.]+:[0-9]+(:\S+:\S+)?$")
COORDINATE = re.compile(r"^(-?\d+(\.\d+)?),\s*(-?\d+(\.\d+)?)$")

EU_SIZE = re.compile(r"^(EU)?\s?[1-5][0-9](\.5|,5|\s1/2|\s[1-2]/3)?\s?(EU)?$", re.IGNORECASE)
UK_SIZE = re.compile(r"^(UK)?\s?([1-9]|1[0-9])(\.5|,5|\s1/2)?\s?(UK)?$", re.IGNORECASE)
US_SIZE = re.compile(r"^(US)?\s?([1-9]|1[0-9])(\.5|,5|\s1/2)?\s?(US)?$", re.IGNORECASE)
ANY_SIZE = re.compile(f"({EU_SIZE.pattern}|{UK_SIZE.pattern}|{US_SIZE.pattern})", re.IGNORECASE)
