from flask import Flask
from config import Config

from routes import main_bp
from model import init_db
import os

def create_app():

    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # inicializa banco
    init_db(app)


    # registra blueprint
    app.register_blueprint(main_bp)


    return app



app = create_app()


if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )