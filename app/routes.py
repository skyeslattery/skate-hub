from flask import Blueprint, render_template, url_for, redirect, flash
from flask_login import login_user, login_required, logout_user, current_user
from app import db, bcrypt  
from app.models import User, RegisterForm, LoginForm, ProfileForm, Spot, SpotForm, MediaForm, Post, Comment, Like, CommentForm
import os
from dotenv import load_dotenv
import boto3
from mimetypes import guess_type
import uuid

main = Blueprint('main', __name__)
load_dotenv()

maps_key = os.getenv('MAPS_KEY')

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

@main.route('/dashboard')
@login_required
def dashboard():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    posts.reverse()
    return render_template('dashboard.html', posts=posts)

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

@main.route('/spot_map')
@login_required
def spot_map():
    skate_spots = Spot.query.all()
    skate_spots_dict = [spot.to_dict() for spot in skate_spots]
    return render_template('spot_map.html', skate_spots=skate_spots_dict, maps_key=maps_key)

@main.route('/post_spot', methods=['GET', 'POST'])
@login_required
def post_spot():
    form = SpotForm()

    if form.validate_on_submit():
        new_spot = Spot(
            name=form.spot_name.data,
            description=form.description.data,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
            user_id=current_user.id
        )
        db.session.add(new_spot)
        db.session.commit()
        flash('new spot added!', 'success')
        return redirect(url_for('main.dashboard'))

    # Handling form errors
    if form.errors:
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                flash(f'{fieldName.capitalize()}: {err}', 'danger')

    return render_template('post_spot.html', form=form, maps_key=maps_key)

@main.route('/create_media', methods=['GET', 'POST'])
@login_required
def create_media():
    form = MediaForm()
    form.associated_spot.choices = [('0', 'select a spot')] + [(spot.id, spot.name) for spot in Spot.query.all()]

    if form.validate_on_submit():
        media_file = form.media.data  # Get the FileStorage object
        caption = form.caption.data
        associated_spot_id = form.associated_spot.data

        if media_file:
            try:
                # Handle file upload to S3
                media_url = upload_to_s3(media_file)

                if media_url:
                    # Create a new post in your database
                    new_post = Post(
                        content=media_url,
                        caption=caption,
                        user_id=current_user.id,
                        spot_id=associated_spot_id
                    )
                    db.session.add(new_post)
                    db.session.commit()
                    flash('New media post added!', 'success')
                    return redirect(url_for('main.dashboard'))
                else:
                    flash('Failed to upload media. Please try again.', 'danger')
            except Exception as e:
                flash(f'Error uploading media: {str(e)}', 'danger')

    # Handling form errors
    if form.errors:
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                flash(f'{fieldName.capitalize()}: {err}', 'danger')

    return render_template('create_post.html', form=form)

s3 = boto3.client('s3')

def upload_to_s3(file_obj):
    try:
        file_name = str(uuid.uuid4())
        mime_type, _ = guess_type(file_obj.filename)
        file_extension = mime_type.split('/')[1]

        s3_key = f"{file_name}.{file_extension}"

        s3.upload_fileobj(
            file_obj,
            os.getenv('S3_BUCKET_NAME'),  
            s3_key,
            ExtraArgs={
                'ACL': 'public-read',  
                'ContentType': mime_type  
            }
        )

        file_url = f"https://{os.getenv('S3_BUCKET_NAME')}.s3.amazonaws.com/{s3_key}"

        return file_url

    except Exception as e:
        print(f"Error uploading file to S3: {e}")
        return None


@main.route('/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()

    if like:
        like = db.session.merge(like)
        db.session.delete(like)
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)

    db.session.commit()
    return redirect(url_for('main.dashboard'))

@main.route('/comments/<int:post_id>', methods=['GET', 'POST'])
@login_required
def comments(post_id):
    post = Post.query.get_or_404(post_id)
    form = CommentForm()

    if form.validate_on_submit():
        comment = Comment(text=form.text.data, user_id=current_user.id, post_id=post.id)
        db.session.add(comment)
        db.session.commit()
        flash('comment posted!', 'success')
        return redirect(url_for('main.comments', post_id=post_id))

    comments = Comment.query.filter_by(post_id=post_id).all()
    return render_template('comments.html', post=post, form=form, comments=comments)
