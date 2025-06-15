from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import uuid

db = SQLAlchemy()


class App(db.Model):
    __tablename__ = "apps"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)

    builds = db.relationship("Build", backref="app", lazy=True)
    deployments = db.relationship("Deployment", backref="app", lazy=True)


class Build(db.Model):
    __tablename__ = "builds"

    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.String(36), db.ForeignKey("apps.id"), nullable=False)
    artifact_url = db.Column(db.String(1024), nullable=False)
    artifact_type = db.Column(db.String(20), nullable=False)  # 'differential' or 'zip'
    snapshot_id = db.Column(db.String(255), nullable=False)
    commit_sha = db.Column(db.String(40), nullable=False)
    commit_message = db.Column(db.Text, nullable=False)
    commit_ref = db.Column(db.String(255), nullable=False)

    deployments = db.relationship("Deployment", backref="build", lazy=True)


class Deployment(db.Model):
    __tablename__ = "deployments"

    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.String(36), db.ForeignKey("apps.id"), nullable=False)
    build_id = db.Column(db.Integer, db.ForeignKey("builds.id"), nullable=False)
    channel_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
