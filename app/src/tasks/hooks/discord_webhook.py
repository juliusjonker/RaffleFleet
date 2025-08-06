# -*- coding: utf-8 -*-
from datetime import datetime
from common import http
from common.utils import current_ts, threaded
from tasks.common.errors import HTTPError


class Webhook:
    session = http.Session()

    def __init__(self, url, **kwargs):
        self.url = url

        self.username = kwargs.get("username")
        self.avatar_url = kwargs.get("avatar_url")
        self.content = kwargs.get("content")

        self.embeds = []

    def add_embed(self, embed):
        self.embeds.append(embed.json())

    def json(self):
        body = {}

        if self.username:
            body["username"] = self.username

        if self.avatar_url:
            body["avatar_url"] = self.avatar_url

        if self.content:
            body["content"] = self.content

        if self.embeds:
            body["embeds"] = self.embeds

        return body

    @threaded
    def send(self):
        try:
            self.session.post(
                self.url,
                body=self.json(),
                headers={
                    "content-type": "application/json"
                }
            )
        except HTTPError:
            pass


class Embed:
    def __init__(self, **kwargs):
        self.title = kwargs.get("title")
        self.url = kwargs.get("url")
        self.description = kwargs.get("description")

        self.thumbnail_url = kwargs.get("thumbnail_url")

        self.footer_text = kwargs.get("footer_text")
        self.footer_icon_url = kwargs.get("footer_icon_url")

        if kwargs.get("color"):
            self.color = int(kwargs["color"], 16)
        else:
            self.color = None

        self.timestamp = str(datetime.utcfromtimestamp(
            kwargs.get("timestamp") or current_ts(exact=True)
        ))

        self.fields = []

    def set_thumbnail(self, url):
        self.thumbnail_url = url

    def add_field(self, name, value, inline=True):
        self.fields.append({
            "name": name,
            "value": value,
            "inline": inline
        })

    def json(self):
        body = {
            "footer": {},
            "image": {},
            "thumbnail": {},
            "fields": []
        }

        if self.title:
            body["title"] = self.title

        if self.url:
            body["url"] = self.url

        if self.description:
            body["description"] = self.description

        if self.thumbnail_url:
            body["thumbnail"]["url"] = self.thumbnail_url

        if self.fields:
            body["fields"] = self.fields

        if self.footer_icon_url:
            body["footer"]["icon_url"] = self.footer_icon_url

        if self.footer_text:
            body["footer"]["text"] = self.footer_text

        if self.color:
            body["color"] = self.color

        if self.timestamp:
            body["timestamp"] = self.timestamp

        return body
