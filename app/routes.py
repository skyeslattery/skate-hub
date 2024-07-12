from flask import Blueprint, render_template, url_for, redirect, flash, make_response, request, jsonify
from flask_login import login_user, login_required, logout_user, current_user
from app import db, bcrypt  
from app.models import User, RegisterForm, LoginForm, Spot, SpotForm, MediaForm, Post, Comment, Like, CommentForm, EmptyForm
import os
from dotenv import load_dotenv
import boto3
from mimetypes import guess_type
import uuid
import time
from sqlalchemy.exc import OperationalError, PendingRollbackError
import logging
import tensorflow as tf
import numpy as np
import tensorflow_hub as hub
from io import BytesIO
import moviepy.editor as mp
from PIL import Image


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

module_url = "https://tfhub.dev/google/universal-sentence-encoder/4" 
model = hub.load(module_url)

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

            posts = Post.query.order_by(Post.timestamp.desc()).all()
            posts.reverse()
            return redirect(url_for('main.dashboard', posts=posts))
        else:
            flash('login failed. please check username and password.', 'danger')
    return render_template('login.html', form=form)

@main.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_user = User(
            username=form.username.data,
            password=hashed_password,
            email=form.email.data,
            name=form.name.data,
            bio=form.bio.data
        )

        if not form.profile_pic.data:
            new_user.profile_pic = '/static/default_pfp.jpg'
        
        else:
            profile_pic_url = upload_to_s3(form.profile_pic.data)
            if profile_pic_url:
                new_user.profile_pic = profile_pic_url
            else:
                flash('Failed to upload profile picture. Please try again.', 'danger')
                return render_template('register.html', form=form)

        db.session.add(new_user)
        db.session.commit()

        flash('Your account has been created!', 'success')
        login_user(new_user)
        return redirect(url_for('main.dashboard'))

    elif form.errors:
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                flash(f'{fieldName.capitalize()}: {err}', 'danger')

    return render_template('register.html', form=form)

@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = EmptyForm()
    return render_template('profile.html', form=form)


@main.route('/dashboard')
@login_required
def dashboard():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    posts.reverse()
    form = EmptyForm()
    return render_template('dashboard.html', posts=posts, form=form)

@main.route('/delete_profile', methods=['POST'])
@login_required
def delete_profile():
    user = User.query.get(current_user.id)
    if user:
        user = db.session.merge(user)
        logout_user()
        db.session.delete(user)
        commit_session_with_retry(db.session)
        flash('your profile has been deleted.', 'success')
    else:
        flash('user not found.', 'danger')
        return redirect(url_for('main.home'))
    form = EmptyForm()
    return render_template('home.html', form=form)
    

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
        commit_session_with_retry(db.session)
        flash('new spot added!', 'success')
        return redirect(url_for('main.dashboard'))

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
        media_file = form.media.data  # Get the file object
        caption = form.caption.data
        associated_spot_id = form.associated_spot.data

        if media_file:
            try:
                media_url = upload_to_s3(media_file)

                if media_url:
                    new_post = Post(
                        content=media_url,
                        caption=caption,
                        user_id=current_user.id,
                        spot_id=associated_spot_id
                    )
                    db.session.add(new_post)
                    commit_session_with_retry(db.session)
                    flash('posted!', 'success')
                    return redirect(url_for('main.dashboard'))
                else:
                    flash('Failed to upload media. Please try again.', 'danger')
            except Exception as e:
                flash(f'Error uploading media: {str(e)}', 'danger')

    if form.errors:
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                flash(f'{fieldName.capitalize()}: {err}', 'danger')

    return render_template('create_post.html', form=form)

s3 = boto3.client('s3')

STANDARD_IMAGE_SIZE = (800, 800)
STANDARD_VIDEO_SIZE = (1280, 720)

def upload_to_s3(file_obj):
    try:
        # Use file_obj.filename to get the filename
        file_name = str(uuid.uuid4())
        mime_type, _ = guess_type(file_obj.filename)
        if not mime_type:
            raise ValueError("Could not determine the MIME type")

        file_extension = mime_type.split('/')[1]
        s3_key = f"{file_name}.{file_extension}"

        s3 = boto3.client('s3')
        s3.upload_fileobj(
            file_obj,
            os.getenv('S3_BUCKET_NAME'),  # Ensure this is set in your .env file
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

    if post.is_liked_by(current_user):
        like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
        like = db.session.merge(like)
        db.session.delete(like)
        liked = False
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        liked = True

    commit_session_with_retry(db.session)
    return jsonify({'likes': len(post.likes), 'liked': liked})

@main.route('/comments/<int:post_id>', methods=['GET', 'POST'])
@login_required
def comments(post_id):
    post = Post.query.get_or_404(post_id)
    form = CommentForm()

    if form.validate_on_submit():
        comment = Comment(text=form.text.data, user_id=current_user.id, post_id=post.id)
        db.session.add(comment)
        commit_session_with_retry(db.session)
        flash('comment posted!', 'success')
        return redirect(url_for('main.comments', post_id=post_id))

    comments = Comment.query.filter_by(post_id=post_id).all()

    return render_template('comments.html', post=post, form=form, comments=comments)


@main.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        flash('you do not have permission to delete this post.', 'danger')
        return redirect(url_for('main.dashboard'))

    post = db.session.merge(post)
    db.session.delete(post)
    
    try:
        commit_session_with_retry(db.session)
        flash('post deleted.', 'success')
    except OperationalError:
        flash('an error occurred while deleting the post. please try again.', 'danger')
    
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    posts.reverse()
    return redirect(url_for('main.dashboard', posts=posts))

@main.route('/search_posts', methods=['POST', 'GET'])
@login_required
def search_posts():
    if request.method == 'POST':
        query = request.form.get('query')
    else:
        query = request.args.get('query')

    if not query:
        flash("please enter a search term.", "danger")
        return redirect(url_for('main.dashboard'))

    all_posts = Post.query.all()
    descriptions = [post.caption for post in all_posts]

    post_embeddings = model(descriptions)
    query_embedding = model([query])

    cosine_similarities = np.inner(query_embedding, post_embeddings)

    top_indices = np.argsort(cosine_similarities[0])[::-1]

    similarity_threshold = 0.5

    matched_posts = []
    for index in top_indices:
        similarity_score = cosine_similarities[0][index]
        if similarity_score > similarity_threshold:
            post = all_posts[index]
            matched_posts.append(post)

    form=EmptyForm()

    if matched_posts:
        return render_template('dashboard.html', posts=matched_posts, form=form, results_count=len(matched_posts), query=query)
    else:
        flash('no matching posts found.', 'warning')
        return redirect(url_for('main.dashboard'))
    
def commit_session_with_retry(session, retries=5, delay=1):
    for attempt in range(retries):
        try:
            session.commit()
            break
        except OperationalError as e:
            if 'database is locked' in str(e):
                time.sleep(delay)
            else:
                raise
        except PendingRollbackError:
            session.rollback()
            time.sleep(delay)