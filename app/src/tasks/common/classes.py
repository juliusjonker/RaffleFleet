# -*- coding: utf-8 -*-
from __future__ import annotations
import random
import string
import managers
from dataclasses import dataclass, asdict
from datetime import datetime
from common import http
from common.utils import xxx_jig
from common.data import COUNTRY_IDS, COUNTRY_DATA, PHONE_DATA, FIRST_NAMES, LAST_NAMES
from . import logger


@dataclass(slots=True)
class Task:
    id: str
    manager: managers.TaskManager
    parent: Profile | FormProfile | Email | Instagram | GeoSeed = None
    proxies: managers.ProxyManager = None
    inheritance: Inheritance = None
    input: Input = None

    @property
    def formatted_parent_id(self):
        return self.manager.format_parent_id(self.parent.id)


@dataclass(slots=True)
class Profile:
    email: str
    password: str
    first_name: str
    last_name: str
    gender: str
    date_of_birth: str
    phone_prefix: str
    phone_number: str
    street: str
    house_number: str
    line_2: str
    city: str
    postcode: str
    province: str
    country: str
    card_number: str
    card_month: str
    card_year: str
    card_cvc: str
    instagram: str
    paypal_email: str
    signature_image: str = None
    ctx: dict = None

    def __post_init__(self):
        self.gender = self.gender.lower().replace(" ", "")
        if self.gender in ["random", "ran", "any", "jig"]:
            self.gender = random.choice(["male", "female"])
        elif self.gender in ["men", "boy"]:
            self.gender = "male"
        elif self.gender in ["woman", "girl"]:
            self.gender = "female"

        if self.first_name.lower().replace(" ", "") in ["random", "ran", "any", "jig"]:
            self.first_name, self.gender = random.choice(FIRST_NAMES)
        elif "XXX" in self.first_name or "xxx" in self.first_name:
            self.first_name = xxx_jig(self.first_name)

        if self.last_name.lower().replace(" ", "") in ["random", "ran", "any", "jig"]:
            self.last_name = random.choice(LAST_NAMES)
        elif "XXX" in self.last_name or "xxx" in self.last_name:
            self.last_name = xxx_jig(self.last_name)

        if self.email.split("@")[0].lower().replace(" ", "") in ["random", "ran", "any", "jig"]:
            address = (
                self.first_name + self.last_name + str(random.randint(1, 99999))
            ).lower().replace(" ", "")
            domain = self.email.split("@")[1] if "@" in self.email else "gmail.com"

            self.email = f"{address}@{domain}"

        if self.password.lower().replace(" ", "") in ["random", "ran", "any", "jig"]:
            self.password = (
                "".join(random.sample(string.ascii_lowercase, 10)) +
                str(random.randint(10, 99)) + (
                    random.choice(".!?") if self.ctx["module"] not in
                    ["Footpatrol", "Kith EU", "Size?", "The Hip Store"] else ""
                )
            ).capitalize()

        if self.date_of_birth.lower().replace(" ", "") in ["random", "ran", "any", "jig"]:
            self.date_of_birth = "/".join((
                str(random.randint(10, 28)),
                f"0{random.randint(1, 9)}",
                str(random.randint(1995, 2003))
            ))
        else:
            self.date_of_birth = self.date_of_birth.replace("-", "/")

        if self.phone_prefix and not self.phone_prefix.startswith("+"):
            self.phone_prefix = "+" + self.phone_prefix

        if self.phone_number.lower().replace(" ", "") in ["random", "ran", "any", "jig"]:
            try:
                length = PHONE_DATA[self.phone_prefix[1:]]["length"]
            except KeyError:
                length = 10

            self.phone_number = "".join((
                str(random.randint(2, 8)),
                str(random.randint(0, 8)),
                random.choice(string.digits),
                str(random.randint(2, 8)),
                *random.choices(string.digits, k=length - 4)
            ))
        elif self.phone_number.startswith("0"):
            self.phone_number = self.phone_number[1:]

        if "XXX" in self.street or "xxx" in self.street:
            self.street = xxx_jig(self.street)

        if "XXX" in self.house_number or "xxx" in self.house_number:
            self.house_number = xxx_jig(self.house_number)
        
        if "XXX" in self.line_2 or "xxx" in self.line_2:
            self.line_2 = xxx_jig(self.line_2)

        self.province = self.province.upper().replace(".", "")

        self.country = self.country.upper().replace(".", "")
        if not len(self.country) == 2:
            try:
                self.country = COUNTRY_IDS[
                    self.country.lower().replace(" ", "").replace("-", "").replace("'", "")
                ]
            except KeyError:
                pass
        elif self.country == "UK":
            self.country = "GB"

        if " " in self.card_number:
            self.card_number = self.card_number.replace(" ", "")

        if len(self.card_month) == 1:
            self.card_month = "0" + self.card_month

        if len(self.card_year) == 2:
            self.card_year = "20" + self.card_year

        if self.instagram.lower().replace(" ", "") in ["random", "ran", "any", "jig"]:
            self.instagram = (
                self.first_name + random.choice(["", ".", "_"]) + self.last_name +
                random.choice(["", self.last_name[-1:]]) +
                random.choice(["", "_"]) +
                random.choice(["", str(random.randint(1, 10))])
            ).lower().replace(" ", "")
        elif self.instagram.startswith("@"):
            self.instagram = self.instagram[1:]

        if self.paypal_email.split("@")[0].lower().replace(" ", "") in ["random", "ran", "any", "jig"]:
            address = (
                self.first_name + self.last_name + str(random.randint(1, 99999))
            ).lower().replace(" ", "")
            domain = self.paypal_email.split("@")[1] if "@" in self.paypal_email else "gmail.com"

            self.paypal_email = f"{address}@{domain}"

    @staticmethod
    def fields(include_optional=False):
        if include_optional:
            return [
                key for key in Profile.__dataclass_fields__  # NOQA
                if key != "ctx"
            ]
        else:
            return [
                key for key, value in Profile.__dataclass_fields__.items()  # NOQA
                if key != "ctx" and value.default is not None
            ]

    @property
    def id(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_phone(self):
        if self.phone_number:
            return self.phone_prefix + self.phone_number
        else:
            return ""

    @property
    def address(self):
        if self.country in ["FR", "GB", "IE", "ZA"]:
            return f"{self.house_number} {self.street}"
        else:
            return f"{self.street} {self.house_number}"

    @property
    def country_name(self):
        try:
            return COUNTRY_DATA[self.country]["name"]
        except KeyError:
            return self.country

    @property
    def card_type(self):
        return (
            "amex" if self.card_number.startswith("3") else
            "visa" if self.card_number.startswith("4") else
            "mastercard"
        )

    @property
    def is_address_loaded(self):
        return all((
            self.street,
            self.house_number,
            self.city,
            self.postcode,
            self.country
        ))

    @property
    def is_creditcard_loaded(self):
        return all((
            self.card_number,
            self.card_month,
            self.card_year,
            self.card_cvc
        ))

    def format_date_of_birth(self, pattern):
        try:
            return datetime.strptime(
                self.date_of_birth, "%d/%m/%Y"
            ).strftime(pattern)
        except ValueError:
            return ""

    def json(self):
        return {
            key: value for key, value in asdict(self).items()
            if key != "ctx" and value is not None
        }


@dataclass(slots=True)
class FormProfile:
    data: dict
    ctx: dict = None

    @staticmethod
    def fields(include_optional=False):
        if include_optional:
            return [
                key for key in FormProfile.__dataclass_fields__  # NOQA
                if key != "ctx"
            ]
        else:
            return [
                key for key, value in FormProfile.__dataclass_fields__.items()  # NOQA
                if key != "ctx" and value.default is not None
            ]

    @property
    def id(self):
        return self.data.get("Email", "")

    def json(self):
        return {
            key: value for key, value in asdict(self).items()
            if key != "ctx" and value is not None
        }


@dataclass(slots=True)
class Email:
    email: str
    ctx: dict = None

    @staticmethod
    def fields(include_optional=False):
        if include_optional:
            return [
                key for key in Email.__dataclass_fields__  # NOQA
                if key != "ctx"
            ]
        else:
            return [
                key for key, value in Email.__dataclass_fields__.items()  # NOQA
                if key != "ctx" and value.default is not None
            ]

    @property
    def id(self):
        return self.email

    def json(self):
        return {
            key: value for key, value in asdict(self).items()
            if key != "ctx" and value is not None
        }


@dataclass(slots=True)
class Instagram:
    username: str
    password: str
    input: str
    ctx: dict = None

    def __post_init__(self):
        if self.username.startswith("@"):
            self.username = self.username[1:]

    @staticmethod
    def fields(include_optional=False):
        if include_optional:
            return [
                key for key in Instagram.__dataclass_fields__  # NOQA
                if key != "ctx"
            ]
        else:
            return [
                key for key, value in Instagram.__dataclass_fields__.items()  # NOQA
                if key != "ctx" and value.default is not None
            ]

    @property
    def id(self):
        return self.username

    def json(self):
        return {
            key: value for key, value in asdict(self).items()
            if key != "ctx" and value is not None
        }


@dataclass(slots=True)
class GeoSeed:
    country: str
    coordinate: tuple[float, float]
    radius: float
    ctx: dict = None

    @staticmethod
    def fields(include_optional=False):
        if include_optional:
            return [
                key for key in GeoSeed.__dataclass_fields__  # NOQA
                if key != "ctx"
            ]
        else:
            return [
                key for key, value in GeoSeed.__dataclass_fields__.items()  # NOQA
                if key != "ctx" and value.default is not None
            ]

    @property
    def id(self):
        return self.country

    def json(self):
        return {
            key: value for key, value in asdict(self).items()
            if key != "ctx" and value is not None
        }


@dataclass(slots=True)
class Proxy:
    line: str

    @property
    def type(self):
        if self.line == "localhost":
            return "localhost"
        elif self.line.count(":") == 1:
            return "unauthorized"
        else:
            return "authorized"

    @property
    def host(self):
        return self.line.split(":")[0]

    @property
    def port(self):
        return self.line.split(":")[1]

    @property
    def username(self):
        return self.line.split(":")[2]

    @property
    def password(self):
        return self.line.split(":")[3]

    @property
    def url(self):
        if self.type == "localhost":
            return ""
        elif self.type == "unauthorized":
            return f"http://{self.line}"
        else:
            components = self.line.split(":")
            return f"http://{components[2]}:{components[3]}@{components[0]}:{components[1]}"

    @property
    def displayable_line(self):
        return ":".join(self.line.split(":")[:2])


@dataclass(slots=True)
class Inheritance:
    session: http.Session = None
    logger: logger.Logger = None


@dataclass(slots=True)
class Input:
    amount: int = None
    raffle: dict = None
    form: dict = None
    size_range: SizeRange = None
    emails: dict = None
    instagram: dict = None
    location: dict = None
    verification: dict = None
    cookies: dict = None


@dataclass(slots=True)
class SizeRange:
    range: tuple[float, float]

    def fits(self, size):
        return self.range[0] <= size <= self.range[1]


@dataclass(slots=True)
class Product:
    name: str = ""
    price: str = ""
    image: str = ""
    size: str = ""

    def match(self, product_name):
        return (
            self.name.lower().strip().replace(" ", "").replace("'", "").replace('"', "") ==
            product_name.lower().strip().replace(" ", "").replace("'", "").replace('"', "")
        )


@dataclass(slots=True)
class Form:
    title: str = ""


@dataclass(slots=True)
class InstagramPost:
    url: str = ""
    image: str = ""
    authors: list[str] = ""
    actions: list[str] = ""


@dataclass(slots=True)
class InstagramMessage:
    sender: str = ""
    text: str = ""


class CaseInsensitiveDict(dict):
    def __init__(self, *args):
        super().__init__(*args)
        for key in dict(self):
            self[key.lower()] = self.pop(key)

    def __getitem__(self, key):
        return super().__getitem__(key.lower())

    def __setitem__(self, key, value):
        return super().__setitem__(key.lower(), value)

    def __delitem__(self, key):
        return super().__delitem__(key.lower())

    def __contains__(self, key):
        return super().__contains__(key.lower())

    def get(self, key, *args):
        return super().get(key.lower(), *args)

    def update(self, dictionary, *args):
        return super().update({
            key.lower(): value
            for key, value in dictionary.items()
        })
