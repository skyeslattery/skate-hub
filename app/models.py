from flask_login import UserMixin
from flask import flash, get_flashed_messages
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError, Email
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)

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
