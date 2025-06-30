from flask import Flask
from models import db
from routes.api import api as api_blueprint
from routes.ui import ui as ui_blueprint

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()

app.register_blueprint(api_blueprint)
app.register_blueprint(ui_blueprint)

if __name__ == "__main__":
    app.run(debug=True)
