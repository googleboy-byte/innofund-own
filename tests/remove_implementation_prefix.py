import sys
import os
import firebase_admin
from firebase_admin import credentials, db

# Add the parent directory to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

# Get the absolute paths for Firebase credentials
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rtdb_cred_path = os.path.join(base_dir, Config.RTDB_FIREBASE_CREDENTIALS)

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate(rtdb_cred_path)
    firebase_admin.initialize_app(cred, {
        'databaseURL': Config.RTDB_DATABASE_URL
    })

def remove_implementation_prefix():
    """Remove 'Implementation of: ' prefix from all project titles in the database."""
    print("Starting to remove 'Implementation of: ' prefix from project titles...")
    
    # Get reference to projects in RTDB
    projects_ref = db.reference('projects')
    
    # Get all projects
    projects = projects_ref.get()
    
    if not projects:
        print("No projects found in the database.")
        return
    
    update_count = 0
    prefix = "Implementation of: "
    
    # Iterate through projects and update titles
    for project_id, project_data in projects.items():
        if project_data.get('title', '').startswith(prefix):
            # Remove the prefix from the title
            new_title = project_data['title'][len(prefix):]
            
            # Update the project title
            projects_ref.child(project_id).update({
                'title': new_title
            })
            
            print(f"Updated project title:")
            print(f"  Old: {project_data['title']}")
            print(f"  New: {new_title}")
            print("---")
            update_count += 1
    
    print(f"\nCompleted! Updated {update_count} project titles.")

if __name__ == '__main__':
    remove_implementation_prefix() 