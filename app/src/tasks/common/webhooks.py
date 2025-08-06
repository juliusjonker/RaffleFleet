# -*- coding: utf-8 -*-
from urllib.parse import quote
from constants import app, colors
from common import data
from tasks.hooks.discord_webhook import Webhook, Embed


class Entry:
    def __init__(self, site, raffle, parent, proxy, location=None, proxy_img=False):
        self.webhook = Webhook(
            url=data.SETTINGS["webhook"],
            username=app.NAME,
            avatar_url=app.SQUARE_LOGO
        )

        self.embed = Embed(
            title="Successful entry!",
            footer_text=app.NAME,
            footer_icon_url=app.ROUND_LOGO,
            color=colors.WEBHOOK
        )

        if hasattr(raffle, "image") and raffle.image:
            self.embed.set_thumbnail(
                "https://imageresize.24i.com/?url=" + quote(raffle.image)
                if proxy_img else raffle.image
            )

        self.embed.add_field(
            "Site", site + (f" - {location}" if location else ""), inline=False
        )

        if hasattr(raffle, "name") and raffle.name:
            self.embed.add_field(
                "Product", raffle.name
            )
        elif hasattr(raffle, "title") and raffle.title:
            self.embed.add_field(
                "Title", raffle.title
            )

        if hasattr(raffle, "size") and raffle.size:
            self.embed.add_field(
                "Size", raffle.size
            )
        if hasattr(raffle, "price") and raffle.price:
            self.embed.add_field(
                "Price", raffle.price
            )

        if hasattr(raffle, "url") and hasattr(raffle, "authors"):
            self.embed.add_field(
                "Raffle", f"[Post by {' & '.join(raffle.authors)}]({raffle.url})"
            )
        if hasattr(raffle, "actions") and raffle.actions:
            self.embed.add_field(
                "Actions", "\n".join(["• " + x for x in raffle.actions]), inline=False
            )

        if hasattr(parent, "email"):
            self.embed.add_field(
                "Email", f"||{parent.email}||", inline=False
            )
        elif hasattr(parent, "data") and parent.data.get("Email"):
            self.embed.add_field(
                "Email", f"||{parent.data['email']}||", inline=False
            )
        elif hasattr(parent, "username"):
            self.embed.add_field(
                "Username", f"||{parent.username}||", inline=False
            )

        self.embed.add_field(
            "Proxy", f"||{proxy.displayable_line}||", inline=False
        )

        self.webhook.add_embed(self.embed)

    def send(self):
        self.webhook.send()


class Win:
    def __init__(self, site, raffle, parent, proxy, order_number=None, location=None, proxy_img=False):
        self.webhook = Webhook(
            url=data.SETTINGS["webhook"],
            username=app.NAME,
            avatar_url=app.SQUARE_LOGO
        )

        self.embed = Embed(
            title="You're a winner!",
            footer_text=app.NAME,
            footer_icon_url=app.ROUND_LOGO,
            color=colors.WEBHOOK
        )

        if hasattr(raffle, "image") and raffle.image:
            self.embed.set_thumbnail(
                "https://imageresize.24i.com/?url=" + quote(raffle.image)
                if proxy_img else raffle.image
            )

        self.embed.add_field(
            "Site", site + (f" - {location}" if location else ""), inline=False
        )

        if hasattr(raffle, "name") and raffle.name:
            self.embed.add_field(
                "Product", raffle.name
            )
        if hasattr(raffle, "size") and raffle.size:
            self.embed.add_field(
                "Size", raffle.size
            )
        if hasattr(raffle, "price") and raffle.price:
            self.embed.add_field(
                "Price", raffle.price
            )

        if hasattr(parent, "email"):
            self.embed.add_field(
                "Email", f"||{parent.email}||", inline=True if order_number else False
            )
        elif hasattr(parent, "data") and parent.data.get("Email"):
            self.embed.add_field(
                "Email", f"||{parent.data['email']}||", inline=True if order_number else False
            )
        elif hasattr(parent, "username"):
            self.embed.add_field(
                "Username", f"||{parent.username}||", inline=True if order_number else False
            )

        if order_number:
            self.embed.add_field(
                "Order Number", f"||{order_number}||"
            )

        self.embed.add_field(
            "Proxy", f"||{proxy.displayable_line}||", inline=False
        )

        self.webhook.add_embed(self.embed)

    def send(self):
        self.webhook.send()


class NewMessage:
    def __init__(self, site, message, parent, proxy, location=None):
        self.webhook = Webhook(
            url=data.SETTINGS["webhook"],
            username=app.NAME,
            avatar_url=app.SQUARE_LOGO
        )

        self.embed = Embed(
            title="New message in inbox!",
            footer_text=app.NAME,
            footer_icon_url=app.ROUND_LOGO,
            color=colors.WEBHOOK
        )

        self.embed.add_field(
            "Site", site + (f" - {location}" if location else ""), inline=False
        )

        self.embed.add_field(
            "Sender", f"`{message.sender}`"
        )

        self.embed.add_field(
            "Message", f"```{message.text}```", inline=False
        )

        if hasattr(parent, "email"):
            self.embed.add_field(
                "Email", f"||{parent.email}||", inline=False
            )
        elif hasattr(parent, "data") and parent.data.get("Email"):
            self.embed.add_field(
                "Email", f"||{parent.data['email']}||", inline=False
            )
        elif hasattr(parent, "username"):
            self.embed.add_field(
                "Username", f"||{parent.username}||", inline=False
            )

        self.embed.add_field(
            "Proxy", f"||{proxy.displayable_line}||", inline=False
        )

        self.webhook.add_embed(self.embed)

    def send(self):
        self.webhook.send()
