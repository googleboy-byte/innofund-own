import os
import sys
import firebase_admin
from firebase_admin import credentials, firestore, db as rtdb
from datetime import datetime, timezone
import logging
from dotenv import load_dotenv
import re

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app.utils.web3_utils import create_project_on_chain

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_html_tags(text):
    """Remove HTML tags from text"""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Replace HTML entities
    clean = clean.replace('&#x2212;', '-')
    clean = clean.replace('&#x2013;', '-')
    return clean

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    try:
        # Check if apps are already initialized
        if not firebase_admin._apps:
            # Initialize Firebase Admin with service account
            cred = credentials.Certificate(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                                      'firebase', 'innofund-firebase-admin.json'))
            firebase_admin.initialize_app(cred, {
                'databaseURL': os.getenv('FIREBASE_DATABASE_URL'),
                'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET')
            }, name='default')
            
            # Initialize RTDB app
            rtdb_cred = credentials.Certificate(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                                           'firebase', 'innofund-rtdb-firebase-admin.json'))
            firebase_admin.initialize_app(rtdb_cred, {
                'databaseURL': os.getenv('FIREBASE_DATABASE_URL')
            }, name='rtdb')
            
            logger.info("Firebase initialized successfully")
        else:
            logger.info("Firebase already initialized")
        return True
    except Exception as e:
        logger.error(f"Error initializing Firebase: {str(e)}")
        return False

def migrate_projects_to_blockchain():
    """Migrate existing projects to blockchain"""
    try:
        # Get Firestore and RTDB instances
        db = firestore.client()
        rtdb_ref = rtdb.reference('projects', app=firebase_admin.get_app('rtdb'))
        
        # Get all projects from RTDB
        all_projects = rtdb_ref.get()
        if not all_projects:
            logger.info("No projects found in RTDB")
            return
        
        logger.info(f"Found {len(all_projects)} projects to migrate")
        
        # Process each project
        for project_id, project_data in all_projects.items():
            try:
                # Skip if already has blockchain ID
                if project_data.get('blockchain_project_id') is not None:
                    logger.info(f"Project {project_id} already has blockchain ID: {project_data['blockchain_project_id']}")
                    continue
                
                logger.info(f"\nProcessing project: {project_id}")
                
                # Clean title and description
                title = clean_html_tags(project_data.get('title', ''))
                description = clean_html_tags(project_data.get('description', ''))
                
                logger.info(f"Title: {title}")
                
                # Create project on blockchain with 1 day duration
                blockchain_project_id = create_project_on_chain(
                    name=title,
                    description=description,
                    funding_goal=float(project_data['goal_amount']),
                    deadline_days=1  # Set to 1 day to match contract limit
                )
                
                logger.info(f"Created on blockchain with ID: {blockchain_project_id}")
                
                # Update RTDB
                rtdb_ref.child(project_id).update({
                    'blockchain_project_id': int(blockchain_project_id)
                })
                
                # Update Firestore
                firestore_doc = db.collection('projects').document(project_id)
                firestore_doc.update({
                    'blockchain_project_id': int(blockchain_project_id)
                })
                
                logger.info(f"Updated databases with blockchain ID for project {project_id}")
                
            except Exception as project_error:
                logger.error(f"Error processing project {project_id}: {str(project_error)}")
                continue
        
        logger.info("\nMigration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        logger.info("Starting blockchain migration...")
        
        # Initialize Firebase
        if not initialize_firebase():
            logger.error("Failed to initialize Firebase. Exiting.")
            sys.exit(1)
        
        # Run migration
        migrate_projects_to_blockchain()
        
    except Exception as e:
        logger.error(f"Migration script failed: {str(e)}")
        sys.exit(1)
