# -*- coding: utf-8 -*-
import re
from common.utils import extract_domain
from tasks.common.errors import HTTPError, ChallengeError, JSONError


class Solver:
    max_retries = 3

    def __init__(self, session, response):
        self.session = session

        self.url = response.url
        self.domain = extract_domain(response.url)
        self.body = response.body

    def solve(self):
        try:
            bm_verify = re.findall('"bm-verify": "(.*?)"', self.body)[0]
            proof_of_work = (
                int(re.findall("var i = (.*?);", self.body)[0]) +
                int(eval(re.findall(r"Number\((.*?)\)", self.body)[0]))
            )
        except:
            raise ChallengeError

        for _ in range(self.max_retries):
            try:
                response = self.session.post(
                    f"https://{self.domain}/_sec/verify?provider=interstitial",
                    body={
                        "bm-verify": bm_verify,
                        "pow": proof_of_work
                    },
                    headers={
                        "content-length": None,
                        "sec-ch-ua": None,
                        "sec-ch-ua-platform": None,
                        "sec-ch-ua-mobile": "?0",
                        "user-agent": None,
                        "content-type": "application/json",
                        "accept": "*/*",
                        "origin": f"https://{self.domain}",
                        "sec-fetch-site": "same-origin",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-dest": "empty",
                        "referer": self.url,
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": None
                    }
                )

                if response.json()["reload"]:
                    break
                else:
                    raise KeyError
            except (HTTPError, JSONError, KeyError):
                continue
        else:
            raise ChallengeError
