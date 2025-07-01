from flask import Blueprint, request, jsonify, redirect, g, jsonify
from models import db, App, Build, Deployment, Token, User
import uuid
import os
import logging
from typing import Tuple, Any, Dict, Optional
from functools import wraps
from utils import validate_required_fields, token_required, validate_build_artifact

api = Blueprint("api", __name__)

BASE_URL = os.getenv("LIVE_UPDATES_BASE_URL", "http://localhost:8000")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ------------------------
# App management endpoints
# ------------------------


@api.route("/apps", methods=["GET"])
@token_required
def get_all_apps():
    apps = App.query.all()
    return jsonify([{"id": app.id, "name": app.name} for app in apps])


@api.route("/apps", methods=["POST"])
@token_required
def create_app():
    data = request.get_json()
    logger.info(f"Creating new app with data: {data}")
    validated, response, error_code = validate_required_fields(data, ["name", "id"])
    if not validated:
        return response, error_code
    if App.query.get(data["id"]):
        return jsonify({"error": "App with this ID already exists"}), 409
    try:
        new_app = App(id=data["id"], name=data["name"])
        db.session.add(new_app)
        db.session.commit()
        logger.info(f"Successfully created app: {new_app.id}")
        return jsonify({"id": new_app.id, "name": new_app.name}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating app: {str(e)}")
        return jsonify({"error": str(e)}), 500


# --------------------------
# Build management endpoints
# --------------------------


@api.route("/apps/<app_id>/builds", methods=["GET"])
@token_required
def get_all_builds(app_id: str):
    if not App.query.get(app_id):
        return jsonify({"error": "App not found"}), 404
    builds = Build.query.filter_by(app_id=app_id).order_by(Build.id.desc()).all()
    return jsonify(
        [
            {
                "id": build.id,
                "app_id": build.app_id,
                "artifact_url": build.artifact_url,
                "artifact_type": build.artifact_type,
                "snapshot_id": build.snapshot_id,
                "commit_sha": build.commit_sha,
                "commit_message": build.commit_message,
                "commit_ref": build.commit_ref,
            }
            for build in builds
        ]
    )


@api.route("/apps/<app_id>/builds", methods=["POST"])
@token_required
def create_build(app_id: str):
    data = request.get_json()
    logger.info(f"Creating new build for app {app_id} with data: {data}")
    required_fields = [
        "artifact_url",
        "artifact_type",
        "commit_sha",
        "commit_message",
        "commit_ref",
    ]
    validated, response, error_code = validate_required_fields(data, required_fields)
    if not validated:
        return response, error_code
    artifact_type, artifact_url = data["artifact_type"], data["artifact_url"]

    validated, error = validate_build_artifact(artifact_type, artifact_url)
    if not validated:
        return jsonify(error), 400

    try:
        new_build = Build(
            app_id=app_id,
            artifact_url=data["artifact_url"],
            artifact_type=data["artifact_type"],
            snapshot_id=str(uuid.uuid4()),
            commit_sha=data["commit_sha"],
            commit_message=data["commit_message"],
            commit_ref=data["commit_ref"],
        )
        db.session.add(new_build)
        db.session.commit()
        logger.info(f"Successfully created build: {new_build.id}")
        return (
            jsonify(
                {
                    "id": new_build.id,
                    "app_id": new_build.app_id,
                    "artifact_url": new_build.artifact_url,
                    "artifact_type": new_build.artifact_type,
                    "snapshot_id": new_build.snapshot_id,
                    "commit_sha": new_build.commit_sha,
                    "commit_message": new_build.commit_message,
                    "commit_ref": new_build.commit_ref,
                }
            ),
            201,
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating build: {str(e)}")
        return jsonify({"error": str(e)}), 500


# -------------------------------
# Deployment management endpoints
# -------------------------------


@api.route("/apps/<app_id>/deployments", methods=["GET"])
@token_required
def get_all_deployments(app_id: str):
    if not App.query.get(app_id):
        return jsonify({"error": "App not found"}), 404
    deployments = (
        Deployment.query.filter_by(app_id=app_id).join(Build).order_by(Deployment.id.desc()).all()
    )
    return jsonify(
        [
            {
                "id": deployment.id,
                "app_id": deployment.app_id,
                "build_id": deployment.build_id,
                "channel_name": deployment.channel_name,
                "created_at": deployment.created_at.isoformat(),
                "artifact_type": deployment.build.artifact_type,
                "artifact_url": deployment.build.artifact_url,
                "snapshot_id": deployment.build.snapshot_id,
                "commit_sha": deployment.build.commit_sha,
                "commit_message": deployment.build.commit_message,
                "commit_ref": deployment.build.commit_ref,
            }
            for deployment in deployments
        ]
    )


@api.route("/apps/<app_id>/deployments", methods=["POST"])
@token_required
def create_deployment(app_id: str):
    data = request.get_json()
    logger.info(f"Creating new deployment for app {app_id} with data: {data}")
    required_fields = ["build_id", "channel_name"]
    validated, response, error_code = validate_required_fields(data, required_fields)
    if not validated:
        return response, error_code
    if not App.query.get(app_id):
        return jsonify({"error": "App not found"}), 404
    if not Build.query.get(data["build_id"]):
        return jsonify({"error": "Build not found"}), 404
    try:
        new_deployment = Deployment(
            app_id=app_id, build_id=data["build_id"], channel_name=data["channel_name"]
        )
        db.session.add(new_deployment)
        db.session.commit()
        logger.info(f"Successfully created deployment: {new_deployment.id}")
        return (
            jsonify(
                {
                    "id": new_deployment.id,
                    "app_id": new_deployment.app_id,
                    "build_id": new_deployment.build_id,
                    "channel_name": new_deployment.channel_name,
                    "created_at": new_deployment.created_at.isoformat(),
                }
            ),
            201,
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating deployment: {str(e)}")
        return jsonify({"error": str(e)}), 500


# -------------------------
# Live Update SDK endpoints
# -------------------------


@api.route("/apps/<app_id>/channels/check-device", methods=["POST"])
def check_device(app_id: str):
    data = request.get_json()
    device = data.get("device", {})
    existing_snapshot_id, existing_build_id = device.get("snapshot", None), device.get(
        "build", None
    )
    required_fields = ["channel_name", "app_id", "is_portals", "manifest"]
    validated, response, error_code = validate_required_fields(data, required_fields)
    if not validated:
        return response, error_code
    if not App.query.get(app_id):
        return jsonify({"error": "App not found"}), 404
    artifact_type = "differential" if data["manifest"] is True else "zip"
    deployment = (
        Deployment.query.filter_by(app_id=app_id, channel_name=data["channel_name"])
        .order_by(Deployment.id.desc())
        .first()
    )
    if not deployment:
        return jsonify({"error": "Deployment not found"}), 404
    build = Build.query.filter_by(id=deployment.build_id).first()
    if not build:
        return jsonify({"error": "Build not found"}), 404
    if build.artifact_type != artifact_type:
        return (
            jsonify(
                {
                    "error": f"Build is a {build.artifact_type}, but the SDK is requesting a {artifact_type}"
                }
            ),
            400,
        )
    update_available = build.snapshot_id != existing_snapshot_id and build.id != existing_build_id
    endpoint = "manifest_v2" if build.artifact_type == "differential" else "download"
    return jsonify(
        {
            "data": {
                "available": update_available,
                "compatible": update_available,
                "partial": False,
                "snapshot": build.snapshot_id if update_available else None,
                "url": (
                    f"{BASE_URL}/apps/{app_id}/snapshots/{build.snapshot_id}/{endpoint}"
                    if update_available
                    else None
                ),
                "build": build.id if update_available else None,
                "incompatibleUpdateAvailable": False,
            },
            "meta": {"status": 200, "version": "2.0.0-sdlc-beta.0", "request_id": uuid.uuid4()},
        }
    )


@api.route("/apps/<app_id>/snapshots/<snapshot_id>/manifest_v2", methods=["GET"])
def manifest_check(app_id: str, snapshot_id: str):
    if not App.query.get(app_id):
        return jsonify({"error": "App not found"}), 404
    build = Build.query.filter_by(snapshot_id=snapshot_id).first()
    if not build:
        return jsonify({"error": "Build not found"}), 404
    return redirect(build.artifact_url)


@api.route("/apps/<app_id>/snapshots/<snapshot_id>/download", methods=["GET"])
def download(app_id: str, snapshot_id: str):
    if not App.query.get(app_id):
        return jsonify({"error": "App not found"}), 404
    build = Build.query.filter_by(snapshot_id=snapshot_id).first()
    if not build:
        return jsonify({"error": "Build not found"}), 404
    return redirect(build.artifact_url)
