from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app, jsonify
from firebase_admin import auth as firebase_auth, firestore
import requests
from requests_oauthlib import OAuth2Session
import os
from functools import wraps
import json
from datetime import datetime
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from urllib.parse import urlparse

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
    users_ref = db.collection('users').document(user_id)
    user_data['last_login'] = datetime.now()
    users_ref.set(user_data, merge=True)

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
            user = firebase_auth.get_user_by_email(email)
            # In a real app, you'd verify the password here
            login_user(User({
                'uid': user.uid,
                'email': user.email,
                'display_name': user.display_name,
                'photo_url': user.photo_url
            }))
            store_user_data(user.uid, {
                'email': email,
                'login_method': 'email',
                'last_login': datetime.now()
            })
            return redirect(next_page)
        except:
            flash('Invalid credentials')
    
    # Pass next parameter to template
    return render_template('auth/login.html', title='Login', next=next_page)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        try:
            user = firebase_auth.create_user(
                email=email,
                password=password,
                display_name=name
            )
            
            # Create User object and login
            user_obj = User({
                'uid': user.uid,
                'email': email,
                'display_name': name
            })
            login_user(user_obj)
            
            # Store user data
            user_data = {
                'email': email,
                'display_name': name,
                'login_method': 'email',
                'created_at': datetime.now(),
                'last_login': datetime.now()
            }
            store_user_data(user.uid, user_data)
            
            return redirect(url_for('main.dashboard'))
        except:
            flash('Registration failed')
    return render_template('auth/register.html', title='Register')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

# Google OAuth routes
@auth_bp.route('/login/google')
def google_login():
    google = OAuth2Session(
        current_app.config['GOOGLE_CLIENT_ID'],
        scope=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ],
        redirect_uri=url_for('auth.google_callback', _external=True)
    )
    authorization_url, state = google.authorization_url(
        GOOGLE_AUTH_URL,
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    session['oauth_state'] = state
    return redirect(authorization_url)

@auth_bp.route('/login/google/callback')
def google_callback():
    if 'error' in request.args:
        flash('Google login failed: ' + request.args.get('error', 'Unknown error'))
        return redirect(url_for('auth.login'))
        
    try:
        google = OAuth2Session(
            current_app.config['GOOGLE_CLIENT_ID'],
            state=session.get('oauth_state'),
            redirect_uri=url_for('auth.google_callback', _external=True)
        )
        
        token = google.fetch_token(
            GOOGLE_TOKEN_URL,
            client_secret=current_app.config['GOOGLE_CLIENT_SECRET'],
            authorization_response=request.url
        )
        
        resp = google.get(GOOGLE_USERINFO_URL)
        if resp.status_code != 200:
            raise Exception(f"Failed to get user info: {resp.text}")
            
        user_info = resp.json()
        
        try:
            user = firebase_auth.get_user_by_email(user_info['email'])
        except:
            user = firebase_auth.create_user(
                email=user_info['email'],
                display_name=user_info['name'],
                photo_url=user_info.get('picture')
            )
        
        # Replace session with Flask-Login
        user_obj = User({
            'uid': user.uid,
            'email': user_info['email'],
            'display_name': user_info['name'],
            'photo_url': user_info.get('picture')
        })
        login_user(user_obj)
        
        # Store user data
        user_data = {
            'email': user_info['email'],
            'display_name': user_info['name'],
            'photo_url': user_info.get('picture'),
            'login_method': 'google',
            'last_login': datetime.now()
        }
        if not db.collection('users').document(user.uid).get().exists:
            user_data['created_at'] = datetime.now()
        
        store_user_data(user.uid, user_data)
        
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.dashboard')
        return redirect(next_page)
        
    except Exception as e:
        print("Google login error:", str(e))
        flash('Failed to log in with Google')
        return redirect(url_for('auth.login'))

# GitHub OAuth routes
@auth_bp.route('/login/github')
def github_login():
    # Instead of OAuth flow, redirect to the login page with a flag
    return render_template('auth/login.html', title='Login', github_login=True)

@auth_bp.route('/auth/github/callback', methods=['GET', 'POST'])
def github_callback():
    print("Method:", request.method)
    print("Session before:", dict(session))  # Debug print
    
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
            user_data = {
                'email': user_info['email'],
                'display_name': user_info['displayName'],
                'photo_url': user_info['photoURL'],
                'login_method': 'github',
                'last_login': datetime.now()
            }
            if not db.collection('users').document(user.uid).get().exists:
                user_data['created_at'] = datetime.now()
            
            store_user_data(user.uid, user_data)
            
            # Return success without logging in yet
            return jsonify({'success': True})
            
        except Exception as e:
            print("GitHub login error:", str(e))
            return jsonify({'success': False, 'error': str(e)}), 400
    
    # Handle GET request after Firebase Auth
    try:
        print("Query params:", request.args)
        id_token = request.args.get('id_token')
        if not id_token:
            raise ValueError("No ID token provided")
            
        decoded_token = firebase_auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        print(f"Decoded token uid: {uid}")  # Debug print
        
        user = firebase_auth.get_user(uid)
        print(f"Firebase user: {user.__dict__}")  # Debug print
        
        user_doc = db.collection('users').document(uid).get()
        user_data = user_doc.to_dict() if user_doc.exists else {}
        print(f"Firestore data: {user_data}")  # Debug print
        
        user_obj = User({
            'uid': user.uid,
            'email': user.email,
            'display_name': user.display_name,
            'photo_url': user.photo_url,
            **user_data
        })
        
        # Force logout any existing user
        logout_user()
        
        # Login with remember=True and force=True
        login_success = login_user(user_obj, remember=True, force=True)
        print(f"Login success: {login_success}")
        print(f"Current user authenticated: {current_user.is_authenticated}")
        print(f"Current user id: {current_user.get_id()}")
        print("Session after:", dict(session))  # Debug print
        
        if not login_success:
            raise ValueError("Failed to login user")
        
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.dashboard')
        
        return redirect(next_page)
        
    except Exception as e:
        print("GitHub callback error:", str(e))
        import traceback
        traceback.print_exc()
        flash('Failed to complete GitHub login')
        return redirect(url_for('auth.login')) 