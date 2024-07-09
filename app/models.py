from flask_login import UserMixin
from flask import flash
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, HiddenField, PasswordField, SubmitField, SelectField
from wtforms.validators import InputRequired, Length, ValidationError, Email
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)
    spots = db.relationship('Spot', backref='user', lazy=True)
    posts = db.relationship('Post', backref='user', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)

class RegisterForm(FlaskForm):
    email = StringField(validators=[InputRequired(), Email(), Length(min=4, max=25)], render_kw={"placeholder": "email"})
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "username"})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "password"})
    submit = SubmitField('register')

    def validate_username(self, username):
        existing_user_username = User.query.filter_by(username=username.data).first()
        if existing_user_username:
            flash('username taken. try another one!', 'danger')
            raise ValidationError('username taken.')
        
    def validate_email(self, email):
        existing_user_email = User.query.filter_by(email=email.data).first()
        if existing_user_email:
            flash('email already in use.', 'danger')
            raise ValidationError('email already in use.')

class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "username"})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "password"})
    submit = SubmitField('login')

class ProfileForm(FlaskForm):
    username = StringField('username', validators=[Length(min=4, max=20)])
    email = StringField('email', validators=[InputRequired(), Email()])
    submit = SubmitField('update profile')

class Spot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.String(200))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    posts = db.relationship('Post', backref='Spot', lazy=True)

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
    media = StringField('media', validators=[Length(max=500)])
    caption = StringField('caption', validators=[Length(max=500)])
    associated_spot = SelectField('add spot', coerce=int, choices=[('', 'select spot')])
    submit = SubmitField('post media')

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    caption = db.Column(db.String(500), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=True)
    timestamp = db.Column(db.DateTime)
    likes = db.relationship('Like', backref='Post', lazy=True)
    comments = db.relationship('Comment', backref='Post', lazy=True)

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
