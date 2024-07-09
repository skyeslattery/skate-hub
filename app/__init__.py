from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
import os

db = SQLAlchemy()
bcrypt = Bcrypt()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev')

    app.config['S3_BUCKET'] = 'skate-hub'
    app.config['S3_KEY'] = 'AKIA4Y37UOSMJTSTND6V'
    app.config['S3_SECRET'] = 'your-secret-key'
    app.config['S3_LOCATION'] = f"http://{app.config['S3_BUCKET']}.s3.amazonaws.com/"
    
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    bcrypt.init_app(app)
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    from app.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    with app.app_context():
        db.create_all()
    
    from app.routes import main
    app.register_blueprint(main)
    
    return app