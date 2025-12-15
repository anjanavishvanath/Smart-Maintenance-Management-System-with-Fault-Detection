from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from provision_logic import generate_slpt

def provision_device():
    user_identity = get_jwt_identity()
    print(user_identity)
    user_id = user_identity.get('user_id')
    data = request.get_json() # parse request body
    enrollment_id = data.get('enrollment_id') # didn't apply regex cz, it was done in frontend
    if not enrollment_id:
        return jsonify({"msg":"Enrollment ID (MAC Address) is required"}), 400
    try:
        token_data = generate_slpt(user_id, enrollment_id)
        return jsonify ({
            "msg": "Token successfully generated",
            "slpt": token_data['slpt'],
            "expires_in_seconds": token_data['expires_at']
        }) 
    except Exception as e:
        print(f"Error generating SLPT: {e}")
        return jsonify({"msg": "Internal server error during token generation"}), 500