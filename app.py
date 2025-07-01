from flask import Flask
from models import db
from routes.api import api as api_blueprint
from routes.ui import ui as ui_blueprint
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()

app.register_blueprint(api_blueprint)
app.register_blueprint(ui_blueprint)

if __name__ == "__main__":
    app.run(debug=True)
