from flask import Blueprint, render_template, url_for, redirect, request, flash, current_app
from flask_login import login_user, login_required, logout_user, current_user
from app import db, bcrypt  
from app.models import User, RegisterForm, LoginForm, ProfileForm

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template('home.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('logged in successfully!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('login failed. please check username and password.', 'danger')
    return render_template('login.html', form=form)

@main.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    return render_template('dashboard.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_user = User(username=form.username.data, password=hashed_password, email=form.email.data)
        db.session.add(new_user)
        db.session.commit()
        flash('Your account has been created!', 'success')
        return redirect(url_for('main.login'))
    elif form.errors:
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                flash(f'{fieldName.capitalize()}: {err}', 'danger')
    return render_template('register.html', form=form)

@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('your profile has been updated!', 'success')
        return redirect(url_for('main.profile'))
    elif form.errors:
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                flash(f'{fieldName.capitalize()}: {err}', 'danger')
    return render_template('profile.html', form=form)

@main.route('/delete_profile', methods=['POST'])
@login_required
def delete_profile():
    user = User.query.get(current_user.id)
    if user:
        user = db.session.merge(user)
        logout_user()
        db.session.delete(user)
        db.session.commit()
        flash('your profile has been deleted.', 'success')
    else:
        flash('user not found.', 'danger')
    return redirect(url_for('main.home'))

@main.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('you have been logged out.', 'success')
    return redirect(url_for('main.login'))