from flask import Flask, request, jsonify, redirect
from models import db, App, Build, Deployment
import uuid

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()


def validate_required_fields(data, required_fields):
    if not data or not all(field in data for field in required_fields):
        return (
            False,
            jsonify({"error": f'Missing required fields: {", ".join(required_fields)}'}),
            400,
        )
    return True, None, None


@app.route("/apps/<app_id>", methods=["GET"])
def get_app(app_id):
    app = App.query.get(app_id)
    if not app:
        return jsonify({"error": "App not found"}), 404
    return jsonify({"id": app.id, "name": app.name})


@app.route("/apps", methods=["POST"])
def create_app():
    data = request.get_json()

    validated, response, error_code = validate_required_fields(data, ["name", "id"])
    if not validated:
        return response, error_code

    if App.query.get(data["id"]):
        return jsonify({"error": "App with this ID already exists"}), 409

    try:
        new_app = App(id=data["id"], name=data["name"])
        db.session.add(new_app)
        db.session.commit()

        return jsonify({"id": new_app.id, "name": new_app.name}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/apps/<app_id>/builds", methods=["POST"])
def create_build(app_id):
    data = request.get_json()

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

    if not App.query.get(app_id):
        return jsonify({"error": "App not found"}), 404

    if data["artifact_type"] not in ["differential", "zip"]:
        return jsonify({"error": 'artifact_type must be either "differential" or "zip"'}), 400

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
        return jsonify({"error": str(e)}), 500


@app.route("/apps/<app_id>/deployments", methods=["POST"])
def create_deployment(app_id):
    data = request.get_json()

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
        return jsonify({"error": str(e)}), 500


@app.route("/apps/<app_id>/channels/check-device", methods=["POST"])
def check_device(app_id):
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

    update_available = build.snapshot_id != existing_snapshot_id and build.id != existing_build_id

    return jsonify(
        {
            "data": {
                "available": update_available,
                "compatible": update_available,
                "partial": False,
                "snapshot": build.snapshot_id if update_available else None,
                "url": build.artifact_url if update_available else None,
                "build": build.id if update_available else None,
                "incompatibleUpdateAvailable": False,
            }
        }
    )


@app.route("/apps/<app_id>/shapshots/<snapshot_id>/manifest_v2", methods=["GET"])
def manifest_check(app_id, snapshot_id):
    if not App.query.get(app_id):
        return jsonify({"error": "App not found"}), 404

    build = Build.query.filter_by(snapshot_id=snapshot_id).first()
    if not build:
        return jsonify({"error": "Build not found"}), 404

    return redirect(build.artifact_url)


@app.route("/apps", methods=["GET"])
def get_apps():
    apps = App.query.all()
    return jsonify([{"id": app.id, "name": app.name} for app in apps])


@app.route("/apps/<app_id>/builds", methods=["GET"])
def get_builds(app_id):
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


@app.route("/apps/<app_id>/deployments", methods=["GET"])
def get_deployments(app_id):
    if not App.query.get(app_id):
        return jsonify({"error": "App not found"}), 404

    deployments = Deployment.query.filter_by(app_id=app_id).order_by(Deployment.id.desc()).all()
    return jsonify(
        [
            {
                "id": deployment.id,
                "app_id": deployment.app_id,
                "build_id": deployment.build_id,
                "channel_name": deployment.channel_name,
                "created_at": deployment.created_at.isoformat(),
            }
            for deployment in deployments
        ]
    )


if __name__ == "__main__":
    app.run(debug=True)
