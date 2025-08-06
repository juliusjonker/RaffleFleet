# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from common import database, http
from common.security import auth_required
from common.errors import HTTPError, LicenseError, WhopError
from common.constants import WHOP_API_KEY


blueprint = Blueprint("auth", __name__, url_prefix="/auth")


def authorize(license_key, device_id):
    user = fetch_license(license_key, device_id)

    app = {
        item["key"]: item["value"]
        for item in database.APP.scan()["Items"]
    }

    secret_modules = [
        module for module, allowed_users in app["secretModules"].items()
        if user["id"] in allowed_users
    ]
    del app["secretModules"]

    return {
        "app": app,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "licenseKey": license_key,
            "secretModules": secret_modules,
            "analytics": fetch_analytics(user["id"])
        },
        "raffles": fetch_raffles()
    }


def fetch_license(license_key, device_id):
    response = http.post(
        f"https://api.whop.com/api/v2/memberships/{license_key}/validate_license",
        body={
            "metadata": {
                "deviceId": device_id
            }
        },
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {WHOP_API_KEY}"
        }
    )

    if response.status == 201:
        try:
            content = response.json()["discord"]

            return {
                "id": int(content["id"]),
                "name": content["username"].split("#")[0]
            }
        except:
            raise WhopError
    elif response.status == 400:
        raise LicenseError("License is activated on another device")
    elif response.status == 404:
        raise LicenseError("License key is invalid")
    else:
        raise WhopError


def fetch_analytics(user_id):
    query = database.ANALYTICS.get_item(
        Key={"userId": user_id}
    )

    if item := query.get("Item"):
        return {
            site: data["raffles"]
            for site, data in item["sites"].items()
        }
    else:
        return {}


def fetch_raffles():
    raffles = {}
    for item in database.RAFFLES.scan()["Items"]:
        site = item["site"]
        if site not in raffles:
            raffles[site] = {}

        raffles[site][item["productName"]] = {
            "input": item["input"],
            "expiry": item.get("expiry")
        }

    return raffles


@blueprint.route("/<license_key>", methods=["POST"])
@auth_required
def auth(license_key):
    body = request.json

    try:
        device_id = body["deviceId"]
    except KeyError:
        return jsonify(
            success=False,
            message="Bad request"
        ), 400

    try:
        return jsonify(
            success=True,
            data=authorize(
                license_key, device_id
            )
        ), 200
    except (LicenseError, HTTPError, WhopError) as error:
        return jsonify(
            success=False,
            message=error.msg
        ), 401 if isinstance(error, LicenseError) else 500
