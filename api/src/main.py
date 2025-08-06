# -*- coding: utf-8 -*-
from flask import Flask, jsonify
import endpoints


app = Flask(__name__)

app.url_map.strict_slashes = False

app.register_blueprint(endpoints.analytics)
app.register_blueprint(endpoints.auth)
app.register_blueprint(endpoints.logs)


@app.errorhandler(400)
def bad_request(_):
    return jsonify(
        success=False,
        message="Bad request"
    ), 400


@app.errorhandler(404)
def not_found(_):
    return jsonify(
        success=False,
        message="Not found"
    ), 404


@app.errorhandler(405)
def method_not_allowed(_):
    return jsonify(
        success=False,
        message="Method not allowed"
    ), 405


@app.errorhandler(500)
def server_error(_):
    return jsonify(
        success=False,
        message="Internal server error"
    ), 500
