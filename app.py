from flask import Flask, request, jsonify, redirect
from models import db, App, Build, Deployment
import os
import uuid
import logging
from typing import Tuple, Any, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BASE_URL = os.getenv("LIVE_UPDATES_BASE_URL", "http://localhost:8000")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()


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


# ------------------------
# App management endpoints
# ------------------------


@app.route("/apps", methods=["GET"])
def get_all_apps():
    """List all registered apps."""
    apps = App.query.all()
    return jsonify([{"id": app.id, "name": app.name} for app in apps])


@app.route("/apps", methods=["POST"])
def create_app():
    """
    Create a new app.
    Apps are uniquely identified by an app ID and an app name.
    """
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


@app.route("/apps/<app_id>/builds", methods=["GET"])
def get_all_builds(app_id: str):
    """List all builds for a specific app."""
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


@app.route("/apps/<app_id>/builds", methods=["POST"])
def create_build(app_id: str):
    """
    Create a new build for an app.

    The Live Updates SDK expects each build to have an "artifact_url" and an "artifact_type".
    This implementation only supports differential live updates, so we are requiring that
    "artifact_type" is "differential" and enforcing that the "artifact_url" is a
    "live-update-manifest.json" file.

    A snapshot ID and a build ID are generated by this endpoint and are used to uniquely
    identify the build.
    """
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

    if artifact_type not in ["differential", "zip"]:
        return jsonify({"error": 'artifact_type must be "differential" or "zip"'}), 400

    if artifact_type == "differential" and not artifact_url.endswith("live-update-manifest.json"):
        return jsonify({"error": "artifact_url must be a live-update-manifest.json file"}), 400

    if artifact_type == "zip" and not artifact_url.endswith(".zip"):
        return jsonify({"error": "artifact_url must be a .zip file"}), 400

    if not App.query.get(app_id):
        return jsonify({"error": "App not found"}), 404

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


@app.route("/apps/<app_id>/deployments", methods=["GET"])
def get_all_deployments(app_id: str):
    """List all deployments for a specific app."""
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


@app.route("/apps/<app_id>/deployments", methods=["POST"])
def create_deployment(app_id: str):
    """
    Create a new deployment for an app.

    A deployment is uniquely identified by a deployment ID.
    It must be associated with an app ID, build ID, and channel name. The deployment will be
    referenced by the plugin, and the SDK will download the corresponding build artifact.
    """
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


@app.route("/apps/<app_id>/channels/check-device", methods=["POST"])
def check_device(app_id: str):
    """
    This is the first endpoint that the SDK will call.

    The SDK will automatically provide data when "sync" is called:
    {
        "device": {
            "binary_version": "1.0",           // Native version number of your app
            "device_id": "c70cb362-38f3-4e74-9792-139efe84b017",  // UUID uniquely identifying the device
            "platform": "android" | "ios",     // Native platform of the device
            "platform_version": "35",          // Android API level or iOS major version
            "snapshot": "e80c799e-b785-4fa2-b799-25bd3682b102",   // Currently active snapshot ID; null if none
            "build": "9492176"                 // Currently active build ID; null if none
        },
        "app_id": "abcd1234",                  // App ID corresponding to the app
        "channel_name": "Production",          // Channel name (production, development, etc.)
        "is_portals": true | false,            // False if using @capacitor/live-updates, true if using Portals
        "plugin_version": "6",                 // Always "6"
        "manifest": true | false               // True if differential updates, false if zip updates
    }

    The check-device endpoint must return something like:
    {
        "data": {
            "available": true,                 // False if device.build matches update's build ID or no update
            "compatible": true,                // False if device.build matches update's build ID or no update
            "partial": false,                  // Not relevant to differential live updates; keep false
            "snapshot": "e5583cc3-038e-44ca-a3ae-dfe0620b3610",  // Snapshot ID for new update; null if none
            "url": "{BASE_URL}/apps/abcd1234/snapshots/{SNAPSHOT_ID}/manifest_v2",  // manifest_v2 or download endpoint
            "build": 10131410,                 // New bundle's build ID; null if none
            "incompatibleUpdateAvailable": false  // Not relevant in current implementation; keep false
        },
        "meta": {
            "status": 200,                     // HTTP status code
            "version": "2.0.0-sdlc-beta.0",    // Required for response parsing
            "request_id": "0ea4c1fb-a8c6-4a38-a206-4abc7f0d3a02"  // Required for response parsing
        }
    }
    """
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


@app.route("/apps/<app_id>/snapshots/<snapshot_id>/manifest_v2", methods=["GET"])
def manifest_check(app_id: str, snapshot_id: str):
    """
    This is the second endpoint that the SDK will call, if differential updates are used.

    The manifest_v2 endpoint will be the URL provided by the check-device endpoint
    in the data.url field, if an update is available.

    The plugin will send a GET request to this endpoint to download the manifest_v2
    file. The endpoint must redirect to the artifact_url of the build, which should be a
    live-update-manifest.json file.

    The plugin will walk through the files in the live-update-manifest.json and
    download the necessary items.
    """
    if not App.query.get(app_id):
        return jsonify({"error": "App not found"}), 404

    build = Build.query.filter_by(snapshot_id=snapshot_id).first()
    if not build:
        return jsonify({"error": "Build not found"}), 404

    return redirect(build.artifact_url)


@app.route("/apps/<app_id>/snapshots/<snapshot_id>/download", methods=["GET"])
def download(app_id: str, snapshot_id: str):
    """
    This is the second endpoint that the SDK will call, if zip updates are used.

    The download endpoint will be the URL provided by the check-device endpoint
    in the data.url field, if an update is available.

    The plugin will send a GET request to this endpoint to download the zip.
    The endpoint must redirect to the artifact_url of the build, which should be a
    .zip file.
    """
    if not App.query.get(app_id):
        return jsonify({"error": "App not found"}), 404

    build = Build.query.filter_by(snapshot_id=snapshot_id).first()
    if not build:
        return jsonify({"error": "Build not found"}), 404

    return redirect(build.artifact_url)


if __name__ == "__main__":
    app.run(debug=True)
