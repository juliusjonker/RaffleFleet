# -*- coding: utf-8 -*-
import boto3
from boto3.dynamodb.types import TypeDeserializer


TypeDeserializer._deserialize_n = lambda _, value: float(value) if "." in value else int(value)

CLIENT = boto3.resource("dynamodb")

APP = CLIENT.Table("app")
RAFFLES = CLIENT.Table("raffles")
ANALYTICS = CLIENT.Table("analytics")
