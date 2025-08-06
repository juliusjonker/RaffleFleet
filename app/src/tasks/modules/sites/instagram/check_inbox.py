# -*- coding: utf-8 -*-
import random
import json
import uuid
import string
from common import http
from common.utils import sleep, current_ts
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, InstagramMessage
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME, DOMAIN, APP_ID, USER_AGENT


class CheckInbox:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = Logger(
            NAME, task.id, task.formatted_parent_id
        )

        self.session = http.Session(
            client="ios",
            proxy=task.proxies.get(),
            user_agent=USER_AGENT
        )

        self.message = InstagramMessage(
            sender=task.input.instagram["account"]
        )
        self.data = {
            "deviceId": str(uuid.uuid4()),
            "familyDeviceId": str(uuid.uuid4()),
            "appleDeviceId": str(uuid.uuid4()),
            "adId": str(uuid.uuid4()),
            "hmac": "hmac." + "".join(random.choices(string.ascii_letters + string.digits, k=48))
        }

    @staticmethod
    def delay():
        sleep(random.randint(1000, 2000) / 1000)

    def switch_proxy(self):
        self.session.set_proxy(
            self.task.proxies.get()
        )

    def get_new_message(self, messages):
        for thread in messages:
            if (
                thread["users"][0]["username"] == self.message.sender[1:] and
                thread["items"][0]["item_id"] != thread["last_seen_at"].get(self.data["userId"], {}).get("item_id")
            ):
                self.message.text = thread["items"][0]["text"]
                return "new_message"
        else:
            return "empty"

    def execute(self):
        status = self.data["status"] if self.log_in() else "failed"

        if status == "new_message":
            webhooks.NewMessage(
                NAME, self.message, self.task.parent, self.session.proxy
            ).send()

        self.task.manager.increment(
            status,
            task=self.task,
            message=self.message,
            parent=self.task.parent,
            proxy=self.session.proxy
        )

    def log_in(self, rerun=False):
        self.logger.info("Logging in...")

        if not rerun and (content := self.task.manager.sessions.get(self.task.parent)):
            self.data.update(content)
            self.delay()
        else:
            error_count = 0
            while error_count < self.max_retries:
                try:
                    response = self.session.post(
                        f"https://{DOMAIN}/api/v1/accounts/login/",
                        body={
                            "signed_body": "SIGNATURE." + json.dumps({
                                "jazoest": "22564",
                                "country_codes": "[{\"country_code\":\"44\",\"source\":[\"default\",\"sim\"]}]",
                                "phone_id": self.data["familyDeviceId"],
                                "enc_password": f"#PWD_INSTAGRAM:0:{current_ts()}:{self.task.parent.password}",
                                "username": self.task.parent.username,
                                "adid": self.data["adId"],
                                "guid": self.data["deviceId"],
                                "device_id": self.data["appleDeviceId"],
                                "google_tokens": "[]",
                                "login_attempt_count": "0"
                            })
                        },
                        headers={
                            "x-ig-app-locale": "en_GB",
                            "x-ig-device-locale": "en_GB",
                            "x-ig-mapped-locale": "en_GB",
                            "x-ig-bandwidth-speed-kbps": "-1.000",
                            "x-ig-bandwidth-totalbytes-b": "0",
                            "x-ig-bandwidth-totaltime-ms": "0",
                            "x-ig-www-claim": "0",
                            "x-ig-device-id": self.data["deviceId"],
                            "x-ig-family-device-id": self.data["familyDeviceId"],
                            "x-ig-timezone-offset": "0",
                            "x-ig-nav-chain": "AjV:self_profile:2:main_profile::,Jgl:bottom_sheet_profile:3:button::,AZr:settings_category_options:4:button::,BFC:web_view:5:button::,AD1:login_landing:6:button::",
                            "x-fb-connection-type": "WIFI",
                            "x-ig-connection-type": "WIFI",
                            "x-ig-capabilities": "3brTv10=",
                            "x-ig-app-id": APP_ID,
                            "priority": "u=3",
                            "user-agent": None,
                            "accept-language": None,
                            "x-mid": "Y-J-LQABAAEx---8rXEXlgo_etCt",
                            "ig-intended-user-id": "0",
                            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                            "content-length": None,
                            "accept-encoding": "gzip, deflate",
                            "x-fb-http-engine": "Liger",
                            "x-fb-client-ip": "True",
                            "x-fb-server-cluster": "True"
                        }
                    )
                except HTTPError as error:
                    self.logger.error(error.msg), self.delay()
                    self.switch_proxy()
                    continue

                if response.ok:
                    try:
                        content = response.json()

                        if content["status"] == "ok":
                            self.data["userId"] = content["logged_in_user"]["pk_id"]
                            self.data["authHeader"] = response.headers["ig-set-authorization"]
                            break
                        else:
                            raise KeyError
                    except (JSONError, KeyError):
                        self.logger.error("Failed to log in"), self.delay()
                        error_count += 1
                        continue
                elif response.status == 400:
                    try:
                        content = response.json()

                        if content.get("exception_name") == "UserInvalidCredentials":
                            self.logger.error("Failed to log in: Invalid credentials")
                            return False
                        elif content.get("message") == "challenge_required":
                            self.logger.error("Failed to log in: Account clipped")
                            return False
                        else:
                            raise KeyError
                    except (JSONError, KeyError):
                        self.logger.error("Failed to log in"), self.delay()
                        error_count += 1
                        continue
                else:
                    self.logger.error((
                        f"Request failed: {response.status} - {response.reason}",
                        "switching proxy" if response.status in [403, 429] else None
                    )), self.delay()
                    if response.status in [403, 429]:
                        self.switch_proxy()
                    error_count += 1
                    continue
            else:
                return False

            self.task.manager.sessions.save(self.task.parent, {
                "deviceId": self.data["deviceId"],
                "familyDeviceId": self.data["familyDeviceId"],
                "appleDeviceId": self.data["appleDeviceId"],
                "adId": self.data["adId"],
                "hmac": self.data["hmac"],
                "authHeader": self.data["authHeader"],
                "userId": self.data["userId"]
            })

        self.logger.success("Successfully logged in")
        return self.fetch_inbox()

    def fetch_inbox(self):
        self.logger.info("Checking inbox...")

        self.delay()

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/api/v1/direct_v2/inbox/",
                    params={
                        "visual_message_return_type": "unseen",
                        "thread_message_limit": "10",
                        "persistentBadging": "true",
                        "limit": "20",
                        "fetch_reason": "manual_refresh"
                    },
                    headers={
                        "x-ig-app-locale": "en_GB",
                        "x-ig-device-locale": "en_GB",
                        "x-ig-mapped-locale": "en_GB",
                        "x-ig-bandwidth-speed-kbps": "55999.000",
                        "x-ig-bandwidth-totalbytes-b": "25590728",
                        "x-ig-bandwidth-totaltime-ms": "766",
                        "x-ig-concurrent-enabled": "false",
                        "x-ig-app-startup-country": "GB",
                        "x-ig-www-claim": self.data["hmac"],
                        "x-ig-device-id": self.data["deviceId"],
                        "x-ig-family-device-id": self.data["familyDeviceId"],
                        "x-ig-timezone-offset": "0",
                        "x-ig-nav-chain": "MainFeedFragment:feed_timeline:1:cold_start::,GalleryPickerFragment:gallery_picker:30:camera_action_bar_button_main_feed::,PhotoFilterFragment:photo_filter:31:button::,FollowersShareFragment:metadata_followers_share:32:next::,MainFeedFragment:feed_timeline:33:return_from_main_camera_to_feed::,DirectInboxFragment:direct_inbox:34:on_launch_direct_inbox::,DirectInboxFragment:direct_inbox:35:button::",
                        "x-fb-connection-type": "WIFI",
                        "x-ig-connection-type": "WIFI",
                        "x-ig-capabilities": "3brTv10=",
                        "x-ig-app-id": APP_ID,
                        "priority": "u=3",
                        "user-agent": None,
                        "accept-language": None,
                        "authorization": self.data["authHeader"],
                        "x-mid": "Y-J-LQABAAEx---8rXEXlgo_etCt",
                        "ig-u-ds-user-id": self.data["userId"],
                        "ig-intended-user-id": self.data["userId"],
                        "accept-encoding": "gzip, deflate",
                        "x-fb-http-engine": "Liger",
                        "x-fb-client-ip": "True",
                        "x-fb-server-cluster": "True"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["status"] = self.get_new_message(
                        response.json()["inbox"]["threads"]
                    )
                    break
                except (JSONError, KeyError, IndexError):
                    self.logger.error("Failed to check inbox"), self.delay()
                    error_count += 1
                    continue
            elif response.status in [400, 401, 403]:
                try:
                    content = response.json()

                    if content.get("message") == "challenge_required":
                        self.logger.error("Failed to check inbox: Account clipped")
                        return False
                    elif content.get("require_login") or content.get("message") == "login_required":
                        self.logger.error("Failed to check inbox: Logged out")
                        return self.log_in(rerun=True)
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to check inbox"), self.delay()
                    error_count += 1
                    continue
            else:
                self.logger.error((
                    f"Request failed: {response.status} - {response.reason}",
                    "switching proxy" if response.status in [403, 429] else None
                )), self.delay()
                if response.status in [403, 429]:
                    self.switch_proxy()
                error_count += 1
                continue
        else:
            return False

        if self.data["status"] == "new_message":
            self.logger.success("Checked inbox: New message")
            return True
        else:
            return self.fetch_pending_inbox()

    def fetch_pending_inbox(self):
        self.delay()

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/api/v1/direct_v2/pending_inbox_streaming/",
                    params={
                        "visual_message_return_type": "unseen",
                        "thread_batch_size": "5",
                        "thread_limit": "20",
                        "thread_message_limit": "1",
                        "persistentBadging": "true"
                    },
                    headers={
                        "x-ig-app-locale": "en_GB",
                        "x-ig-device-locale": "en_GB",
                        "x-ig-mapped-locale": "en_GB",
                        "x-ig-bandwidth-speed-kbps": "55999.000",
                        "x-ig-bandwidth-totalbytes-b": "25590728",
                        "x-ig-bandwidth-totaltime-ms": "766",
                        "x-ig-concurrent-enabled": "false",
                        "x-ig-app-startup-country": "GB",
                        "x-ig-www-claim": self.data["hmac"],
                        "x-ig-device-id": self.data["deviceId"],
                        "x-ig-family-device-id": self.data["familyDeviceId"],
                        "x-ig-timezone-offset": "0",
                        "x-ig-nav-chain": "MainFeedFragment:feed_timeline:1:cold_start::,GalleryPickerFragment:gallery_picker:30:camera_action_bar_button_main_feed::,PhotoFilterFragment:photo_filter:31:button::,FollowersShareFragment:metadata_followers_share:32:next::,MainFeedFragment:feed_timeline:33:return_from_main_camera_to_feed::,DirectInboxFragment:direct_inbox:34:on_launch_direct_inbox::,DirectInboxFragment:direct_inbox:35:button::",
                        "x-fb-connection-type": "WIFI",
                        "x-ig-connection-type": "WIFI",
                        "x-ig-capabilities": "3brTv10=",
                        "x-ig-app-id": APP_ID,
                        "priority": "u=3",
                        "user-agent": None,
                        "accept-language": None,
                        "authorization": self.data["authHeader"],
                        "x-mid": "Y-J-LQABAAEx---8rXEXlgo_etCt",
                        "ig-u-ds-user-id": self.data["userId"],
                        "ig-intended-user-id": self.data["userId"],
                        "accept-encoding": "gzip, deflate",
                        "x-fb-http-engine": "Liger",
                        "x-fb-client-ip": "True",
                        "x-fb-server-cluster": "True"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["status"] = self.get_new_message(
                        json.loads(response.json()["json_response"])["inbox"]["threads"]
                    )
                    break
                except (JSONError, KeyError, IndexError):
                    self.logger.error("Failed to check inbox"), self.delay()
                    error_count += 1
                    continue
            elif response.status in [400, 401, 403]:
                try:
                    content = response.json()

                    if content.get("message") == "challenge_required":
                        self.logger.error("Failed to check inbox: Account clipped")
                        return False
                    elif content.get("require_login") or content.get("message") == "login_required":
                        self.logger.error("Failed to check inbox: Logged out")
                        return self.log_in(rerun=True)
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to check inbox"), self.delay()
                    error_count += 1
                    continue
            else:
                self.logger.error((
                    f"Request failed: {response.status} - {response.reason}",
                    "switching proxy" if response.status in [403, 429] else None
                )), self.delay()
                if response.status in [403, 429]:
                    self.switch_proxy()
                error_count += 1
                continue
        else:
            return False

        if self.data["status"] == "new_message":
            self.logger.success("Checked inbox: New message")
        else:
            self.logger.info("Checked inbox: Empty")
        return True
