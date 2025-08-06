# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from common import database
from common.security import auth_required


blueprint = Blueprint("analytics", __name__, url_prefix="/analytics")


def upload_analytics(user_id, site, product_name, entries, wins):
    query = database.ANALYTICS.get_item(
        Key={"userId": user_id}
    )

    if item := query.get("Item"):
        sites = item["sites"]

        if site in sites:
            site_data = sites[site]

            site_data["entries"] += entries
            site_data["wins"] += wins

            if product_name in site_data["raffles"]:
                site_data["raffles"][product_name]["entries"] += entries
                site_data["raffles"][product_name]["wins"] += wins
            else:
                site_data["raffles"][product_name] = {
                    "entries": entries,
                    "wins": wins
                }
        else:
            site_data = {
                "entries": entries,
                "wins": wins,
                "raffles": {
                    product_name: {
                        "entries": entries,
                        "wins": wins
                    }
                }
            }

        database.ANALYTICS.update_item(
            Key={"userId": user_id},
            UpdateExpression="ADD totalEntries :entries, totalWins :wins  SET sites.#site = :data",
            ExpressionAttributeNames={
                "#site": site
            },
            ExpressionAttributeValues={
                ":entries": entries,
                ":wins": wins,
                ":data": site_data
            }
        )
    else:
        database.ANALYTICS.put_item(Item={
            "userId": user_id,
            "totalEntries": entries,
            "totalWins": wins,
            "sites": {
                site: {
                    "entries": entries,
                    "wins": wins,
                    "raffles": {
                        product_name: {
                            "entries": entries,
                            "wins": wins
                        }
                    }
                }
            }
        })


@blueprint.route("/<user_id>", methods=["POST"])
@auth_required
def analytics(user_id):
    body = request.json

    try:
        user_id = int(user_id)
        site = body["site"]
        product_name = body["productName"]

        entries = body.get("entries", 0)
        wins = body.get("wins", 0)
        if not (entries or wins):
            raise ValueError
    except (ValueError, KeyError):
        return jsonify(
            success=False,
            message="Bad request"
        ), 400

    upload_analytics(
        user_id, site, product_name, entries, wins
    )

    return jsonify(
        success=True
    ), 200
