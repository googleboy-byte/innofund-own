from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app, jsonify
from firebase_admin import auth as firebase_auth, firestore
import requests
from requests_oauthlib import OAuth2Session
import os
from functools import wraps
import json
from datetime import datetime
from flask_login import login_user, logout_user, login_required, current_user, LoginManager
from app.models import User
from urllib.parse import urlparse
import logging

# Set up logging
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# Initialize Firestore
db = firestore.client()

# OAuth 2.0 endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Only for development!

def store_user_data(user_id, user_data):
    """Store user data in Firestore"""
    try:
        users_ref = db.collection('users').document(user_id)
        user_data['last_login'] = datetime.now()
        users_ref.set(user_data, merge=True)
        logger.info(f"Stored user data for {user_id}")
    except Exception as e:
        logger.error(f"Error storing user data: {str(e)}")
        raise

# Regular email/password routes
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    # Get next parameter
    next_page = request.args.get('next')
    if not next_page or urlparse(next_page).netloc != '':
        next_page = url_for('main.dashboard')
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Get user from Firebase
            user = firebase_auth.get_user_by_email(email)
            
            # Create User object with the new model structure
            user_obj = User(
                uid=user.uid,
                email=user.email,
                display_name=user.display_name or email.split('@')[0],
                photo_url=user.photo_url
            )
            
            # Login user
            login_user(user_obj)
            
            # Store user data
            store_user_data(user.uid, {
                'email': email,
                'display_name': user_obj.display_name,
                'photo_url': user_obj.photo_url,
                'login_method': 'email'
            })
            
            logger.info(f"User {email} logged in successfully")
            return redirect(next_page)
            
        except Exception as e:
            logger.error(f"Login error for {email}: {str(e)}")
            flash('Invalid credentials')
    
    return render_template('auth/login.html', title='Login', next=next_page)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        display_name = request.form.get('display_name', email.split('@')[0])
        
        try:
            # Create user in Firebase
            user = firebase_auth.create_user(
                email=email,
                password=password,
                display_name=display_name
            )
            
            # Create User object
            user_obj = User(
                uid=user.uid,
                email=user.email,
                display_name=display_name
            )
            
            # Login user
            login_user(user_obj)
            
            # Store user data
            store_user_data(user.uid, {
                'email': email,
                'display_name': display_name,
                'login_method': 'email'
            })
            
            logger.info(f"User {email} registered successfully")
            return redirect(url_for('main.dashboard'))
            
        except Exception as e:
            logger.error(f"Registration error for {email}: {str(e)}")
            flash('Registration failed. Please try again.')
    
    return render_template('auth/register.html', title='Register')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

# Google OAuth routes
@auth_bp.route('/login/google')
def google_login():
    google_client_id = current_app.config.get('GOOGLE_CLIENT_ID')
    google_client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
    
    if not all([google_client_id, google_client_secret]):
        flash('Google OAuth is not configured')
        return redirect(url_for('auth.login'))
    
    google = OAuth2Session(
        google_client_id,
        scope=['openid', 'email', 'profile'],
        redirect_uri=url_for('auth.google_callback', _external=True)
    )
    
    authorization_url, state = google.authorization_url(GOOGLE_AUTH_URL)
    session['oauth_state'] = state
    
    return redirect(authorization_url)

@auth_bp.route('/login/google/callback')
def google_callback():
    if 'error' in request.args:
        flash('Google login failed')
        return redirect(url_for('auth.login'))
    
    google_client_id = current_app.config.get('GOOGLE_CLIENT_ID')
    google_client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
    
    try:
        google = OAuth2Session(
            google_client_id,
            state=session.get('oauth_state'),
            redirect_uri=url_for('auth.google_callback', _external=True)
        )
        
        # Get token
        token = google.fetch_token(
            GOOGLE_TOKEN_URL,
            client_secret=google_client_secret,
            authorization_response=request.url
        )
        
        # Get user info
        resp = google.get(GOOGLE_USERINFO_URL)
        user_info = resp.json()
        
        # Get or create Firebase user
        try:
            user = firebase_auth.get_user_by_email(user_info['email'])
        except:
            user = firebase_auth.create_user(
                email=user_info['email'],
                display_name=user_info.get('name'),
                photo_url=user_info.get('picture')
            )
        
        # Create User object
        user_obj = User(
            uid=user.uid,
            email=user_info['email'],
            display_name=user_info.get('name'),
            photo_url=user_info.get('picture')
        )
        
        # Login user
        login_user(user_obj)
        
        # Store user data
        store_user_data(user.uid, {
            'email': user_info['email'],
            'display_name': user_info.get('name'),
            'photo_url': user_info.get('picture'),
            'login_method': 'google'
        })
        
        logger.info(f"User {user_info['email']} logged in via Google")
        return redirect(url_for('main.dashboard'))
        
    except Exception as e:
        logger.error(f"Google OAuth error: {str(e)}")
        flash('Google login failed')
        return redirect(url_for('auth.login'))

# GitHub OAuth routes
@auth_bp.route('/login/github')
def github_login():
    # Instead of OAuth flow, redirect to the login page with a flag
    return render_template('auth/login.html', title='Login', github_login=True)

@auth_bp.route('/auth/github/callback', methods=['GET', 'POST'])
def github_callback():
    logger.info("GitHub callback received")
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            user_info = data['user']
            
            try:
                user = firebase_auth.get_user_by_email(user_info['email'])
            except:
                user = firebase_auth.create_user(
                    email=user_info['email'],
                    display_name=user_info['displayName'],
                    photo_url=user_info['photoURL'],
                    uid=user_info['uid']
                )
            
            # Store user data
            store_user_data(user.uid, {
                'email': user_info['email'],
                'display_name': user_info['displayName'],
                'photo_url': user_info['photoURL'],
                'login_method': 'github'
            })
            
            logger.info(f"GitHub user data stored for {user_info['email']}")
            return jsonify({'success': True})
            
        except Exception as e:
            logger.error(f"GitHub login error (POST): {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 400
    
    # Handle GET request after Firebase Auth
    try:
        id_token = request.args.get('id_token')
        if not id_token:
            raise ValueError("No ID token provided")
        
        decoded_token = firebase_auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        logger.info(f"Verified GitHub token for UID: {uid}")
        
        user = firebase_auth.get_user(uid)
        user_doc = db.collection('users').document(uid).get()
        user_data = user_doc.to_dict() if user_doc.exists else {}
        
        # Create User object with new model structure
        user_obj = User(
            uid=user.uid,
            email=user.email,
            display_name=user.display_name,
            photo_url=user.photo_url
        )
        
        # Force logout any existing user
        logout_user()
        
        # Login with remember=True
        login_success = login_user(user_obj, remember=True)
        
        if not login_success:
            raise ValueError("Failed to login user")
        
        logger.info(f"GitHub user {user.email} logged in successfully")
        
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.dashboard')
        
        return redirect(next_page)
        
    except Exception as e:
        logger.error(f"GitHub callback error (GET): {str(e)}")
        flash('GitHub login failed')
        return redirect(url_for('auth.login'))

login_manager = LoginManager()
@login_manager.user_loader
def load_user(user_id):
    try:
        # Get user from Firebase
        user = firebase_auth.get_user(user_id)
        
        # Get additional data from Firestore
        user_doc = db.collection('users').document(user_id).get()
        user_data = user_doc.to_dict() if user_doc.exists else {}
        
        # Create User object
        return User(
            uid=user.uid,
            email=user.email,
            display_name=user.display_name or user_data.get('display_name'),
            photo_url=user.photo_url or user_data.get('photo_url')
        )
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None