from typing import Dict, Any, Tuple, Optional
from flask import jsonify
from functools import wraps
from flask import request, g
from models import Token

def validate_required_fields(
    data: Dict[str, Any], required_fields: list[str]
) -> Tuple[bool, Optional[str], Optional[int]]:
    if not data or not all(field in data for field in required_fields):
        return (
            False,
            jsonify({"error": f'Missing required fields: {", ".join(required_fields)}'}),
            400,
        )
    return True, None, None


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token_str = auth.split(" ", 1)[1]
        token = Token.query.filter_by(token=token_str).first()
        if not token:
            return jsonify({"error": "Invalid or expired token"}), 401
        g.current_user = token.user
        return f(*args, **kwargs)

    return decorated


def validate_build_artifact(artifact_type: str, artifact_url: str) -> Tuple[bool, Optional[Dict[str, str]]]:
    if artifact_type not in ["differential", "zip"]:
        return False, {"error": 'artifact_type must be "differential" or "zip"'}
    if artifact_type == "differential" and not artifact_url.endswith("live-update-manifest.json"):
        return False, {"error": "artifact_url must be a live-update-manifest.json file"}
    if artifact_type == "zip" and not artifact_url.endswith(".zip"):
        return False, {"error": "artifact_url must be a .zip file"}
    return True, {}