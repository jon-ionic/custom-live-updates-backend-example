from flask import Blueprint, render_template, request, redirect
from models import db, App, Build, Deployment
import uuid

ui = Blueprint("ui", __name__)


@ui.route("/ui/apps", methods=["GET", "POST"])
def ui_apps():
    if request.method == "POST":
        name = request.form.get("name")
        app_id = request.form.get("id")
        if name and app_id:
            if not App.query.get(app_id):
                new_app = App(id=app_id, name=name)
                db.session.add(new_app)
                db.session.commit()
        return redirect("/ui/apps")
    apps = App.query.all()
    return render_template("apps.html", apps=apps)


@ui.route("/ui/apps/<app_id>", methods=["GET", "POST"])
def ui_app(app_id):
    app_obj = App.query.get(app_id)
    if not app_obj:
        return redirect("/ui/apps")
    if request.method == "POST":
        artifact_url = request.form.get("artifact_url")
        artifact_type = request.form.get("artifact_type")
        commit_sha = request.form.get("commit_sha")
        commit_message = request.form.get("commit_message")
        commit_ref = request.form.get("commit_ref")
        if all([artifact_url, artifact_type, commit_sha, commit_message, commit_ref]):
            new_build = Build(
                app_id=app_id,
                artifact_url=artifact_url,
                artifact_type=artifact_type,
                snapshot_id=str(uuid.uuid4()),
                commit_sha=commit_sha,
                commit_message=commit_message,
                commit_ref=commit_ref,
            )
            db.session.add(new_build)
            db.session.commit()
        return redirect(f"/ui/apps/{app_id}/builds")
    builds = Build.query.filter_by(app_id=app_id).order_by(Build.id.desc()).limit(5).all()
    deployments = (
        Deployment.query.filter_by(app_id=app_id)
        .order_by(Deployment.id.desc())
        .join(Build)
        .limit(5)
        .all()
    )
    return render_template("app.html", app=app_obj, builds=builds, deployments=deployments)


@ui.route("/ui/apps/<app_id>/builds", methods=["GET", "POST"])
def ui_builds(app_id):
    app_obj = App.query.get(app_id)
    if not app_obj:
        return redirect("/ui/apps")
    if request.method == "POST":
        artifact_url = request.form.get("artifact_url")
        artifact_type = request.form.get("artifact_type")
        commit_sha = request.form.get("commit_sha")
        commit_message = request.form.get("commit_message")
        commit_ref = request.form.get("commit_ref")
        if all([artifact_url, artifact_type, commit_sha, commit_message, commit_ref]):
            new_build = Build(
                app_id=app_id,
                artifact_url=artifact_url,
                artifact_type=artifact_type,
                snapshot_id=str(uuid.uuid4()),
                commit_sha=commit_sha,
                commit_message=commit_message,
                commit_ref=commit_ref,
            )
            db.session.add(new_build)
            db.session.commit()
        return redirect(f"/ui/apps/{app_id}/builds")
    builds = Build.query.filter_by(app_id=app_id).order_by(Build.id.desc()).all()
    return render_template("builds.html", app=app_obj, builds=builds)


@ui.route("/ui/apps/<app_id>/deployments", methods=["GET", "POST"])
def ui_deployments(app_id):
    app_obj = App.query.get(app_id)
    if not app_obj:
        return redirect("/ui/apps")
    builds = Build.query.filter_by(app_id=app_id).order_by(Build.id.desc()).all()
    if request.method == "POST":
        build_id = request.form.get("build_id")
        channel_name = request.form.get("channel_name")
        if build_id and channel_name:
            new_deployment = Deployment(app_id=app_id, build_id=build_id, channel_name=channel_name)
            db.session.add(new_deployment)
            db.session.commit()
        return redirect(f"/ui/apps/{app_id}/deployments")
    deployments = (
        Deployment.query.filter_by(app_id=app_id).order_by(Deployment.id.desc()).join(Build).all()
    )
    return render_template("deployments.html", app=app_obj, builds=builds, deployments=deployments)
