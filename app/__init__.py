from flask import Flask, request, render_template, session
from config import Config
import firebase_admin
from firebase_admin import credentials, firestore, storage, db
from firebase_admin import auth as firebase_auth
import os
from flask_login import LoginManager, current_user
from flask_moment import Moment
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'

# Initialize Firebase apps at module level
default_app = None
storage_app = None
rtdb_app = None
db = None
moment = Moment()

def init_firebase(app):
    """Initialize Firebase apps and return the Firestore client"""
    global default_app, storage_app, rtdb_app
    
    logger.debug("Initializing Firebase apps...")
    
    try:
        # First, delete any existing apps
        for app_name in firebase_admin._apps:
            firebase_admin.delete_app(firebase_admin.get_app(app_name))
        logger.debug("Cleaned up existing Firebase apps")
    except:
        pass

    # Initialize main Firebase app (for auth)
    cred_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                            app.config['FIREBASE_CREDENTIALS'])
    logger.debug(f"Main Firebase credentials path: {cred_path}")
    default_app = firebase_admin.initialize_app(credentials.Certificate(cred_path), {
        'databaseURL': app.config['FIREBASE_DATABASE_URL']
    })
    logger.debug("Main Firebase app initialized")
    
    # Initialize Firestore client first
    firestore_client = firestore.client()
    logger.debug("Firestore client initialized")
    
    # Then initialize other apps
    storage_cred_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                    app.config['STORAGE_FIREBASE_CREDENTIALS'])
    logger.debug(f"Storage Firebase credentials path: {storage_cred_path}")
    storage_app = firebase_admin.initialize_app(credentials.Certificate(storage_cred_path), {
        'storageBucket': app.config['STORAGE_BUCKET']
    }, name='storage')
    logger.debug("Storage Firebase app initialized")
    
    rtdb_cred_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                 app.config['RTDB_FIREBASE_CREDENTIALS'])
    logger.debug(f"RTDB Firebase credentials path: {rtdb_cred_path}")
    rtdb_app = firebase_admin.initialize_app(credentials.Certificate(rtdb_cred_path), {
        'databaseURL': app.config['RTDB_DATABASE_URL']
    }, name='rtdb')
    logger.debug("RTDB Firebase app initialized")
    
    return firestore_client

def create_app():
    try:
        app = Flask(__name__)
        app.config.from_object(Config)
        
        # Initialize Firebase and get Firestore client
        global db
        db = init_firebase(app)
        
        @app.errorhandler(404)
        def not_found_error(error):
            print(f"404 Error: {request.url}")
            return render_template('404.html'), 404
        
        # Initialize Flask-Login
        login_manager.init_app(app)
        login_manager.session_protection = 'strong'
        login_manager.refresh_view = 'auth.login'
        login_manager.needs_refresh_message = 'Please login again to confirm your identity.'
        
        @app.before_request
        def before_request():
            if current_user.is_authenticated:
                session.permanent = True
        
        # Initialize Flask-Moment
        moment.init_app(app)
        
        # Register blueprints
        from app import routes
        from app.auth import auth_bp
        
        app.register_blueprint(routes.main)
        app.register_blueprint(auth_bp)
        
        return app
        
    except Exception as e:
        logger.error(f"Error initializing app: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise

@login_manager.user_loader
def load_user(user_id):
    try:
        logger.debug(f"Loading user: {user_id}")
        user = firebase_auth.get_user(user_id)
        if not db:
            logger.warning("Warning: Firestore client not initialized")
            return None
            
        user_doc = db.collection('users').document(user_id).get()
        user_data = user_doc.to_dict() if user_doc.exists else {}
        
        user_obj = User({
            'uid': user.uid,
            'email': user.email,
            'display_name': user.display_name,
            'photo_url': user.photo_url,
            **user_data
        })
        logger.debug(f"Loaded user object: {user_obj.__dict__}")
        return user_obj
    except Exception as e:
        logger.error(f"Error loading user: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

from app.models import User 