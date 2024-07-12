from flask_login import UserMixin
from flask import flash
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, HiddenField, PasswordField, SubmitField, SelectField, FileField
from wtforms.validators import InputRequired, Length, ValidationError, Email, EqualTo
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv
from PIL import Image
import re
import datetime
import base64
import boto3
from io import BytesIO
from mimetypes import guess_type, guess_extension
import string
import random

db = SQLAlchemy()

load_dotenv()

EXTENSIONS = ["png", "jpg", "jpeg", "mp4"]
BASE_DIR = os.getcwd()
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
S3_BASE_URL = f"https://{S3_BUCKET_NAME}.s3.us-east-1.amazonaws.com"

class Asset(db.Model):
    __tablename__ = "asset"
    id = db.Column(db.Integer, primary_key=True)
    base_url = db.Column(db.String, nullable=False)
    salt = db.Column(db.String, nullable=False)
    extension = db.Column(db.String, nullable=False)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, **kwargs):
        self.create(kwargs.get("media_data"))

    def serialize(self):
        return {
            "url": f"{self.base_url}/{self.salt}.{self.extension}",
            "created_at": str(self.created_at)
        }

    def create(self, media_data):
        try:
            ext = guess_extension(guess_type(media_data)[0])[1:]

            if ext not in EXTENSIONS:
                raise Exception(f"{ext} is not supported")

            salt = "".join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(16))

            media_str = re.sub("^data:image/.+;base64,|^data:video/.+;base64,", "", media_data)
            media_data = base64.b64decode(media_str)

            self.base_url = S3_BASE_URL
            self.salt = salt
            self.extension = ext
            self.created_at = datetime.datetime.now()

            if ext in ["png", "jpg", "jpeg"]:
                img = Image.open(BytesIO(media_data))
                self.width = img.width
                self.height = img.height

            media_filename = f"{self.salt}.{self.extension}"
            self.upload(media_data, media_filename)

        except Exception as e:
            print(f"error when creating media: {e}")

    def upload(self, media_data, media_filename):
        try:
            media_temp_loc = f"{BASE_DIR}/{media_filename}"
            with open(media_temp_loc, 'wb') as f:
                f.write(media_data)

            s3_client = boto3.client("s3")
            s3_client.upload_file(media_temp_loc, S3_BUCKET_NAME, media_filename)

            s3_resource = boto3.resource("s3")
            object_acl = s3_resource.ObjectAcl(S3_BUCKET_NAME, media_filename)
            object_acl.put(ACL="public-read")

            os.remove(media_temp_loc)

        except Exception as e:
            print(f"error when uploading media: {e}")

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(50), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    profile_pic = db.Column(db.String, nullable=True)
    spots = db.relationship('Spot', backref='user', lazy=True)
    posts = db.relationship('Post', backref='user', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)

class RegisterForm(FlaskForm):
    username = StringField('username', validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "username"})
    email = StringField('email', validators=[Email(), InputRequired(), Length(min=4, max=25)], render_kw={"placeholder": "email"})
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "password"})
    confirm_password = PasswordField('confirm password', validators=[InputRequired(), EqualTo('password', message='passwords must match')], render_kw={"placeholder": "confirm password"})
    name = StringField('name', validators=[Length(max=50)], render_kw={"placeholder": "name"})
    bio = TextAreaField('bio', validators=[Length(max=500)], render_kw={"placeholder": "bio"})
    profile_pic = FileField('profile picture', validators=[FileAllowed(['jpg', 'jpeg', 'png'], 'images only')])
    submit = SubmitField('register')

    def validate_username(self, username):
        existing_user_username = User.query.filter_by(username=username.data).first()
        if existing_user_username:
            raise ValidationError('username is already taken.')

    def validate_email(self, email):
        existing_user_email = User.query.filter_by(email=email.data).first()
        if existing_user_email:
            raise ValidationError('email is already in use.')

class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "username"})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "password"})
    submit = SubmitField('login')

class Spot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.String(200))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    posts = db.relationship('Post', backref='spot', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'latitude': self.latitude,
            'longitude': self.longitude
        }

class SpotForm(FlaskForm):
    spot_name = StringField('spot name', validators=[InputRequired(), Length(max=100)])
    description = TextAreaField('description', validators=[InputRequired()])
    latitude = HiddenField('latitude', validators=[InputRequired()])
    longitude = HiddenField('longitude', validators=[InputRequired()])
    submit = SubmitField('post spot')

class MediaForm(FlaskForm):
    media = FileField('media', validators=[
        FileRequired(),
        FileAllowed(['jpg', 'jpeg', 'png', 'mp4'], 'Images and videos only!')
    ])
    caption = StringField('caption', validators=[Length(max=500)])
    associated_spot = SelectField('add spot', coerce=int, choices=[('', 'select spot')])
    submit = SubmitField('post media')

class Post(db.Model):
    __tablename__ = "post"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    caption = db.Column(db.String(500), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey('spot.id'))
    timestamp = db.Column(db.DateTime)
    likes = db.relationship('Like', backref='post', lazy=True)
    comments = db.relationship('Comment', backref='post', lazy=True)
    media_type = db.Column(db.String(10))

    def is_liked_by(self, user):
        return Like.query.filter_by(post_id=self.id, user_id=user.id).count() > 0   

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(300), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    timestamp = db.Column(db.DateTime)

class CommentForm(FlaskForm):
    text = StringField('comment', validators=[InputRequired()])
    submit = SubmitField('post comment')

class EmptyForm(FlaskForm):
    pass