# -*- coding: utf-8 -*-
import random
import json
import re
import uuid
import string
from common import http
from common.utils import sleep, current_ts
from tasks.common import webhooks, Logger
from tasks.common.classes import Task, InstagramPost
from tasks.common.errors import HTTPError, JSONError
from .constants import NAME, DOMAIN, APP_ID, USER_AGENT


class EnterRaffle:
    max_retries = 3

    def __init__(self, task: Task):
        self.task = task

        self.logger = Logger(
            NAME, task.id, task.formatted_parent_id
        )

        self.session = http.Session(
            client="ios",
            proxy=task.proxies.get(),
            user_agent=USER_AGENT,
            accept_language="en-GB"
        )

        self.post = InstagramPost(
            url=task.input.raffle["url"],
            actions=[
                "Followed ",
                "Liked the post",
                f"Commented `{task.parent.input}`"
            ]
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

    def execute(self):
        status = "entered" if self.log_in() else "failed"

        if status == "entered":
            webhooks.Entry(
                NAME, self.post, self.task.parent, self.session.proxy
            ).send()

        self.task.manager.increment(
            status,
            task=self.task,
            raffle="Post by " + " & ".join(self.post.authors),
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
        return self.fetch_post()

    def fetch_post(self):
        self.logger.info("Entering raffle...")

        self.delay()

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    self.task.input.raffle["url"],
                    headers={
                        "user-agent": None,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "accept-language": None,
                        "accept-encoding": "gzip, deflate, br"
                    }
                )
            except HTTPError as error:
                self.logger.error(error.msg), self.delay()
                self.switch_proxy()
                continue

            if response.ok:
                try:
                    self.data["targetUserId"] = re.findall('property="instapp:owner_user_id" content="(.*?)"', response.body)[0]
                    self.data["targetPostId"] = re.findall(r'property="al:ios:url" content="instagram://media\?id=(.*?)"', response.body)[0]
                    break
                except IndexError:
                    self.logger.error("Failed to enter raffle"), self.delay()
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

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.get(
                    f"https://{DOMAIN}/api/v1/media/{self.data['targetPostId']}_{self.data['targetUserId']}/info/",
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
                        "x-ig-nav-chain": "ExploreFragment:explore_popular:2:main_search::,SingleSearchTypeaheadTabFragment:search_typeahead:5:button::",
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
                    content = response.json()["items"][0]

                    self.post.authors = ["@" + content["user"]["username"]]
                    self.data["usersToFollow"] = [content["user"]["pk_id"]]
                    for user in content.get("coauthor_producers", []):
                        self.post.authors.append("@" + user["username"])
                        self.data["usersToFollow"].append(user["pk_id"])

                    if content.get("carousel_media"):
                        self.post.image = content["carousel_media"][0]["image_versions2"]["candidates"][0]["url"]
                    else:
                        self.post.image = content["image_versions2"]["candidates"][0]["url"]

                    self.post.actions[0] += (
                        " & ".join(f"`{x}`" for x in self.post.authors)
                    )
                    break
                except (JSONError, KeyError, IndexError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status in [400, 401, 403]:
                try:
                    content = response.json()

                    if content.get("message") == "challenge_required":
                        self.logger.error("Failed to enter raffle: Account clipped")
                        return False
                    elif content.get("require_login") or content.get("message") == "login_required":
                        self.logger.error("Failed to enter raffle: Logged out")
                        return self.log_in(rerun=True)
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to enter raffle"), self.delay()
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

        return self.fulfill_requirements()

    def fulfill_requirements(self):
        for user_id in self.data["usersToFollow"]:
            self.delay()

            error_count = 0
            while error_count < self.max_retries:
                try:
                    response = self.session.post(
                        f"https://{DOMAIN}/api/v1/friendships/create/{user_id}/",
                        body={
                            "signed_body": "SIGNATURE." + json.dumps({
                                "user_id": user_id,
                                "radio_type": "wifi-none",
                                "_uid": self.data["userId"],
                                "device_id": self.data["appleDeviceId"],
                                "_uuid": self.data["deviceId"],
                                "nav_chain": "ExploreFragment:explore_popular:2:main_search::,SingleSearchTypeaheadTabFragment:search_typeahead:5:button::,UserDetailFragment:profile:11:search_result::,ProfileMediaTabFragment:profile:12:button::"
                            })
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
                            "x-ig-nav-chain": "ExploreFragment:explore_popular:2:main_search::,SingleSearchTypeaheadTabFragment:search_typeahead:5:button::,UserDetailFragment:profile:11:search_result::,ProfileMediaTabFragment:profile:12:button::",
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
                        if response.json()["status"] == "ok":
                            break
                        else:
                            raise KeyError
                    except (JSONError, KeyError):
                        self.logger.error("Failed to enter raffle"), self.delay()
                        error_count += 1
                        continue
                elif response.status in [400, 401, 403]:
                    try:
                        content = response.json()

                        if content.get("message") == "challenge_required":
                            self.logger.error("Failed to enter raffle: Account clipped")
                            return False
                        elif content.get("require_login") or content.get("message") == "login_required":
                            self.logger.error("Failed to enter raffle: Logged out")
                            return self.log_in(rerun=True)
                        else:
                            raise KeyError
                    except (JSONError, KeyError):
                        self.logger.error("Failed to enter raffle"), self.delay()
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

        self.delay()

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}/api/v1/media/{self.data['targetPostId']}_{self.data['targetUserId']}/like/",
                    body={
                        "signed_body": "SIGNATURE." + json.dumps({
                            "delivery_class": "organic",
                            "tap_source": "button",
                            "media_id": f"{self.data['targetPostId']}_{self.data['targetUserId']}",
                            "radio_type": "wifi-none",
                            "_uid": self.data["userId"],
                            "_uuid": self.data["deviceId"],
                            "nav_chain": "ExploreFragment:explore_popular:2:main_search::,SingleSearchTypeaheadTabFragment:search_typeahead:5:button::,UserDetailFragment:profile:11:search_result::,ProfileMediaTabFragment:profile:12:button::,ContextualFeedFragment:feed_contextual:13:button::",
                            "is_carousel_bumped_post": "false",
                            "container_module": "feed_contextual_profile",
                            "feed_position": "0"
                        })
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
                        "x-ig-nav-chain": "ExploreFragment:explore_popular:2:main_search::,SingleSearchTypeaheadTabFragment:search_typeahead:5:button::,UserDetailFragment:profile:11:search_result::,ProfileMediaTabFragment:profile:12:button::,ContextualFeedFragment:feed_contextual:13:button::",
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
                    if response.json()["status"] == "ok":
                        break
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status in [400, 401, 403]:
                try:
                    content = response.json()

                    if content.get("message") == "challenge_required":
                        self.logger.error("Failed to enter raffle: Account clipped")
                        return False
                    elif content.get("require_login") or content.get("message") == "login_required":
                        self.logger.error("Failed to enter raffle: Logged out")
                        return self.log_in(rerun=True)
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to enter raffle"), self.delay()
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

        self.delay()

        error_count = 0
        while error_count < self.max_retries:
            try:
                response = self.session.post(
                    f"https://{DOMAIN}/api/v1/media/{self.data['targetPostId']}_{self.data['targetUserId']}/comment/",
                    body={
                        "signed_body": "SIGNATURE." + json.dumps({
                            "delivery_class": "organic",
                            "idempotence_token": str(uuid.uuid4()),
                            "radio_type": "wifi-none",
                            "_uid": self.data["userId"],
                            "_uuid": self.data["deviceId"],
                            "nav_chain": "ExploreFragment:explore_popular:2:main_search::,SingleSearchTypeaheadTabFragment:search_typeahead:5:button::,UserDetailFragment:profile:11:search_result::,ProfileMediaTabFragment:profile:12:button::,ContextualFeedFragment:feed_contextual:13:button::,CommentThreadFragment:comments_v2:15:button::",
                            "comment_text": self.task.parent.input,
                            "is_carousel_bumped_post": "false",
                            "container_module": "comments_v2_feed_contextual_profile",
                            "feed_position": "0"
                        })
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
                        "x-ig-nav-chain": "ExploreFragment:explore_popular:2:main_search::,SingleSearchTypeaheadTabFragment:search_typeahead:5:button::,UserDetailFragment:profile:11:search_result::,ProfileMediaTabFragment:profile:12:button::,ContextualFeedFragment:feed_contextual:13:button::,CommentThreadFragment:comments_v2:15:button::",
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
                    if response.json()["status"] == "ok":
                        break
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to enter raffle"), self.delay()
                    error_count += 1
                    continue
            elif response.status == 400:
                try:
                    content = response.json()

                    if content.get("comments_disabled"):
                        self.logger.error("Failed to enter raffle: Comments disabled")
                        return False
                    elif content.get("message") == "challenge_required":
                        self.logger.error("Failed to enter raffle: Account clipped")
                        return False
                    elif content.get("require_login") or content.get("message") == "login_required":
                        self.logger.error("Failed to enter raffle: Logged out")
                        return self.log_in(rerun=True)
                    else:
                        raise KeyError
                except (JSONError, KeyError):
                    self.logger.error("Failed to enter raffle"), self.delay()
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

        self.logger.success("Successfully entered raffle")
        return True
