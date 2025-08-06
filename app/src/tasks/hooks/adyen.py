# -*- coding: utf-8 -*-
import base64
import os
import json
from datetime import datetime
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESCCM


class Encryptor:
    def __init__(self, version, public_key, string_prefix="adyenjs"):
        self.version = version
        self.public_key = public_key
        self.string_prefix = string_prefix

    @staticmethod
    def decode_public_key(encoded_public_key):
        components = encoded_public_key.split("|")

        return default_backend().load_rsa_public_numbers(
            rsa.RSAPublicNumbers(
                int(components[0], 16), int(components[1], 16)
            )
        )

    @staticmethod
    def encrypt_with_public_key(public_key, string):
        return public_key.encrypt(
            string, padding.PKCS1v15()
        )

    @staticmethod
    def encrypt_with_aes_key(aes_key, nonce, string):
        return AESCCM(aes_key, tag_length=8).encrypt(
            nonce, string, None
        )

    def encrypt(self, data):
        body = json.dumps({
            "generationtime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            **data
        }, sort_keys=True)

        aes_key = AESCCM.generate_key(256)
        nonce = os.urandom(12)

        encrypted_body = self.encrypt_with_aes_key(
            aes_key, nonce, body.encode()
        )
        encrypted_aes_key = self.encrypt_with_public_key(
            self.decode_public_key(self.public_key), aes_key
        )

        return "{}{}${}${}".format(
            self.string_prefix,
            self.version,
            base64.b64encode(encrypted_aes_key).decode(),
            base64.b64encode(nonce + encrypted_body).decode()
        )
