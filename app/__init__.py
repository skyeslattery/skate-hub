import logging
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
import os
from logging.handlers import RotatingFileHandler
from flask_migrate import Migrate
from datetime import datetime

db = SQLAlchemy()
bcrypt = Bcrypt()
csrf = CSRFProtect()

def create_app():
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    logger.info('creating flask app instance')
    
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db?timeout=20'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    migrate = Migrate(app, db)
    
    db.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    
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
    
    @app.after_request
    def add_header(response):
        if request.endpoint in ['main.profile', 'main.dashboard']:
            response.cache_control.no_store = True
        return response
    
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('App startup')
    
    def timeago(dt, default="just now"):
        """
        Returns string representing "time since" e.g.
        3 days ago, 5 hours ago.
        """
        if dt is None:
            return default
        now = datetime.utcnow()
        diff = now - dt

        periods = (
            (diff.days // 365, "year", "years"),
            (diff.days // 30, "month", "months"),
            (diff.days // 7, "week", "weeks"),
            (diff.days, "day", "days"),
            (diff.seconds // 3600, "hour", "hours"),
            (diff.seconds // 60, "minute", "minutes"),
            (diff.seconds, "second", "seconds"),
        )

        for period, singular, plural in periods:
            if period:
                return "{} {} ago".format(period, singular if period == 1 else plural)

        return default

    def timeago_filter(dt):
        return timeago(dt)

    app.jinja_env.filters['timeago'] = timeago_filter
    
    return app
