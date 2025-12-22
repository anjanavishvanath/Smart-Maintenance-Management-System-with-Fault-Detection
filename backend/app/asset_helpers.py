from flask_jwt_extended import get_jwt_identity
from flask import request, jsonify
from db import insert_asset

def add_asset_to_db():
    user_identity = get_jwt_identity()
    user_id = int(user_identity)
    data = request.get_json()
    name = data.get("name", "").strip()
    max_rpm = data.get("max_rpm", 0)
    power = data.get("power", 0)
    organization = data.get("organization", "").strip()
    if not name:
        return jsonify({"msg":"All asset fields are required and must be valid"}), 400
    try:
        insert_asset(name, max_rpm, power, organization, user_id)
        return jsonify({"msg": "Asset added successfully"}), 201
    except Exception as e:
        print(f"Error inserting asset: {e}")
        return jsonify({"msg": "Internal server error during asset insertion"}), 500