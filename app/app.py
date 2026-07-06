from flask import Flask
from config import Config
from routes import main_bp
from api import api_bp
from model import init_db
import os
import json
from bson.objectid import ObjectId
from datetime import datetime
from flask.json.provider import DefaultJSONProvider

class MongoJSONProvider(DefaultJSONProvider):
    """Provider personalizado para serializar objetos MongoDB/Bson no Flask 2.x."""
    
    @staticmethod
    def default(obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Configura o provider JSON personalizado para Flask 2.x
    app.json_provider_class = MongoJSONProvider
    app.json = MongoJSONProvider(app)

    # Inicializa banco
    init_db(app)

    # Registra blueprint
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )