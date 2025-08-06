# -*- coding: utf-8 -*-
import json
from datetime import datetime
from flask import Blueprint, request, jsonify
from common import http
from common.errors import HTTPError, WebhookError
from common.security import auth_required


blueprint = Blueprint("logs", __name__, url_prefix="/logs")


def upload_logs(user_id, category, file_name, content):
    response = http.post(
        "https://discord.com/api/webhooks/",
        body={
            "payload_json": json.dumps({
                "embeds": [{
                    "title": "User Logs",
                    "description": f"<@{user_id}> has exported his {category} logs, see the attached file.",
                    "timestamp": str(datetime.utcnow())
                }]
            }),
            "file[0]": (
                file_name, content, "text/plain"
            )
        },
        headers={
            "Content-Type": "multipart/form-data"
        }
    )

    if response.status != 200:
        raise WebhookError


@blueprint.route("/<user_id>", methods=["POST"])
@auth_required
def logs(user_id):
    body, files = request.form, request.files

    try:
        user_id = int(user_id)
        category = body["category"]
        logfile = files["logfile"]
    except (ValueError, KeyError):
        return jsonify(
            success=False,
            message="Bad request"
        ), 400

    try:
        upload_logs(
            user_id, category, logfile.filename, logfile.read()
        )

        return jsonify(
            success=True
        ), 200
    except (HTTPError, WebhookError) as error:
        return jsonify(
            success=False,
            message=error.msg
        ), 500
