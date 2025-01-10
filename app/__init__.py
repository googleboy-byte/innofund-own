from flask import Flask
from flask_login import LoginManager
from flask_moment import Moment
from firebase_admin import credentials, initialize_app, firestore, storage, db as rtdb
import os
from dotenv import load_dotenv
import logging
from .utils.warning_filters import setup_warning_filters

# Set up warning filters at app startup
setup_warning_filters()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
try:
    # Clean up existing apps
    logger.debug("Initializing Firebase apps...")
    try:
        import firebase_admin
        for app in firebase_admin._apps.values():
            firebase_admin.delete_app(app)
        logger.debug("Cleaned up existing Firebase apps")
    except Exception as e:
        logger.debug(f"No existing apps to clean up: {str(e)}")

    # Initialize main Firebase app
    main_cred_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                'firebase', 'innofund-firebase-admin.json')
    logger.debug(f"Main Firebase credentials path: {main_cred_path}")
    
    default_app = initialize_app(credentials.Certificate(main_cred_path), {
        'databaseURL': os.getenv('FIREBASE_DATABASE_URL', 'https://innofund-own-default-rtdb.asia-southeast1.firebasedatabase.app')
    })
    logger.debug("Main Firebase app initialized")

    # Initialize Storage app
    storage_cred_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                   'firebase', 'innofund-storage-firebase-admin.json')
    logger.debug(f"Storage Firebase credentials path: {storage_cred_path}")
    storage_app = initialize_app(credentials.Certificate(storage_cred_path), {
        'storageBucket': os.getenv('STORAGE_BUCKET', 'innofund-own.appspot.com')
    }, name='storage')
    logger.debug("Storage Firebase app initialized")

    # Initialize RTDB app
    rtdb_cred_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                'firebase', 'innofund-rtdb-firebase-admin.json')
    logger.debug(f"RTDB Firebase credentials path: {rtdb_cred_path}")
    rtdb_app = initialize_app(credentials.Certificate(rtdb_cred_path), {
        'databaseURL': os.getenv('RTDB_DATABASE_URL', 'https://innofund-own-rtdb-default-rtdb.asia-southeast1.firebasedatabase.app')
    }, name='rtdb')
    logger.debug("RTDB Firebase app initialized")

except Exception as e:
    logger.error(f"Error initializing Firebase: {str(e)}")
    import traceback
    logger.error(traceback.format_exc())
    raise

load_dotenv()

# Initialize Flask-Login
login_manager = LoginManager()

# Initialize Flask-Moment
moment = Moment()

def create_app():
    try:
        app = Flask(__name__)
        app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
        
        # Initialize extensions
        login_manager.init_app(app)
        moment.init_app(app)
        login_manager.login_view = 'auth.login'
        
        # Register blueprints
        from app import routes
        from app.auth import auth_bp
        from app.blockchain_routes import blockchain_bp
        
        app.register_blueprint(routes.main)
        app.register_blueprint(auth_bp)
        app.register_blueprint(blockchain_bp, url_prefix='/blockchain')
        
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
        from app.models import User
        from firebase_admin import auth
        
        user = auth.get_user(user_id)
        db = firestore.client()
        user_doc = db.collection('users').document(user_id).get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            return User(
                uid=user.uid,
                email=user.email,
                display_name=user_data.get('display_name', user.display_name),
                photo_url=user_data.get('photo_url', user.photo_url)
            )
        return None
        
    except Exception as e:
        logger.error(f"Error loading user: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None