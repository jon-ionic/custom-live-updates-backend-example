from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    tokens = db.relationship("Token", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Token(db.Model):
    __tablename__ = "tokens"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class App(db.Model):
    __tablename__ = "apps"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    user = db.relationship("User", backref="apps")
    builds = db.relationship("Build", backref="app", lazy=True)
    deployments = db.relationship("Deployment", backref="app", lazy=True)


class Build(db.Model):
    __tablename__ = "builds"

    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.String(36), db.ForeignKey("apps.id"), nullable=False)
    artifact_url = db.Column(db.String(1024), nullable=False)
    artifact_type = db.Column(db.String(20), nullable=False)
    snapshot_id = db.Column(db.String(255), nullable=False)
    commit_sha = db.Column(db.String(40), nullable=False)
    commit_message = db.Column(db.Text, nullable=False)
    commit_ref = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    deployments = db.relationship("Deployment", backref="build", lazy=True)


class Deployment(db.Model):
    __tablename__ = "deployments"

    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.String(36), db.ForeignKey("apps.id"), nullable=False)
    build_id = db.Column(db.Integer, db.ForeignKey("builds.id"), nullable=False)
    channel_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
