from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import db, App, Build, Deployment, User, Token
import uuid
from functools import wraps

ui = Blueprint("ui", __name__)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("ui.login"))
        return f(*args, **kwargs)

    return decorated_function


@ui.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            flash("Username and password required.", "danger")
            return redirect(url_for("ui.register"))
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("ui.register"))
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("ui.login"))
    return render_template("register.html")


@ui.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            flash("Logged in successfully!", "success")
            return redirect(url_for("ui.ui_apps"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@ui.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out.", "info")
    return redirect(url_for("ui.login"))


@ui.route("/tokens", methods=["GET", "POST"])
@login_required
def tokens():
    user = User.query.get(session["user_id"])
    if request.method == "POST":
        new_token = Token(user_id=user.id)
        db.session.add(new_token)
        db.session.commit()
        flash("New token created!", "success")
        return redirect(url_for("ui.tokens"))
    tokens = Token.query.filter_by(user_id=user.id).order_by(Token.created_at.desc()).all()
    return render_template("tokens.html", tokens=tokens)


@ui.route("/ui/apps", methods=["GET", "POST"])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
