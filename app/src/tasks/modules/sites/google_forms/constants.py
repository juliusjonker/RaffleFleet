# -*- coding: utf-8 -*-
NAME = "Google Forms"

DOMAIN = "docs.google.com"
SHORT_DOMAIN = "forms.gle"

FIELDS = [
    {
        "id": None,
        "type": "email",
        "placeholder": "example@email.com"
    },
    {
        "id": 0,
        "type": "shortAnswer",
        "placeholder": "Text"
    },
    {
        "id": 1,
        "type": "paragraph",
        "placeholder": "Text"
    },
    {
        "id": 2,
        "type": "multipleChoice",
        "placeholder": "Choose 1 option"
    },
    {
        "id": 3,
        "type": "dropdown",
        "placeholder": "Choose 1 option"
    },
    {
        "id": 4,
        "type": "checkbox",
        "placeholder": "Choose 1 or multiple options"
    },
    {
        "id": 8,
        "type": "newPage",
        "placeholder": None
    },
    {
        "id": 9,
        "type": "date",
        "placeholder": {
            "basic": "31/12",
            "withYear": "31/12/2000",
            "withTime": "31/12 12:00",
            "withYearAndTime": "31/12/2000 12:00"
        }
    },
    {
        "id": 10,
        "type": "time",
        "placeholder": {
            "basic": "12:00",
            "withSeconds": "12:00:00"
        }
    },
    {
        "id": 11,
        "type": "image"
    }
]

FIELD_IDS = {
    field["id"]: field["type"]
    for field in FIELDS
}
FIELD_TYPES = {
    field["type"]: field
    for field in FIELDS
}
