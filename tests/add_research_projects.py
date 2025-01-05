import sys
import os
import json
import firebase_admin
from firebase_admin import credentials, db, firestore, storage
from datetime import datetime
import random

# Add the parent directory to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from config import Config

# Get the absolute paths for Firebase credentials
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rtdb_cred_path = os.path.join(base_dir, Config.RTDB_FIREBASE_CREDENTIALS)
auth_cred_path = os.path.join(base_dir, Config.FIREBASE_CREDENTIALS)
storage_cred_path = os.path.join(base_dir, Config.STORAGE_FIREBASE_CREDENTIALS)

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    # Initialize RTDB app
    rtdb_cred = credentials.Certificate(rtdb_cred_path)
    rtdb_app = firebase_admin.initialize_app(rtdb_cred, {
        'databaseURL': Config.RTDB_DATABASE_URL
    }, name='rtdb')
    
    # Initialize Firestore app for auth
    auth_cred = credentials.Certificate(auth_cred_path)
    auth_app = firebase_admin.initialize_app(auth_cred, name='firestore')
    
    # Initialize Storage app with storage credentials
    storage_cred = credentials.Certificate(storage_cred_path)
    storage_app = firebase_admin.initialize_app(storage_cred, {
        'storageBucket': Config.STORAGE_BUCKET
    }, name='storage')

# Get database references
rtdb_ref = db.reference('projects', app=firebase_admin.get_app('rtdb'))
firestore_db = firestore.client(app=firebase_admin.get_app('firestore'))
bucket = storage.bucket(app=firebase_admin.get_app('storage'))

# After initialization, add these debug prints
print("\nVerifying Firebase configurations:")
print(f"Storage bucket name: {bucket.name}")
print(f"Storage app project ID: {firebase_admin.get_app('storage').project_id}")
print("---\n")

def load_paper_metadata():
    """Load the research papers metadata from JSON file."""
    metadata_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'research_papers',
        'papers_metadata.json'
    )
    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def upload_pdf_to_storage(local_pdf_path, creator_id, timestamp):
    """Upload a PDF file to Firebase Storage and return its public URL."""
    print(f"\nAttempting to upload PDF: {local_pdf_path}")
    print(f"Using storage bucket: {bucket.name}")
    print(f"Creator ID for path: {creator_id}")
    print(f"Timestamp for path: {timestamp}")
    
    if not local_pdf_path or not os.path.exists(local_pdf_path):
        print(f"PDF file not found at path: {local_pdf_path}")
        return None
        
    # Create a unique blob path matching the project creation pattern
    blob_path = f'projects/{creator_id}/{timestamp}/proof.pdf'
    print(f"Full storage path: {blob_path}")
    blob = bucket.blob(blob_path)
    
    # Upload the file
    try:
        blob.upload_from_filename(local_pdf_path)
        # Make the file publicly accessible and get the URL
        blob.make_public()
        url = blob.public_url
        print(f"Successfully uploaded PDF. URL: {url}")
        return url
    except Exception as e:
        print(f"Error uploading PDF: {e}")
        return None

def create_project_from_paper(paper_data):
    """Convert a paper's metadata into a project structure."""
    print(f"\nProcessing paper: {paper_data['title']}")
    print(f"Local PDF path in metadata: {paper_data.get('local_pdf')}")
    
    # Calculate a random goal amount between 50 and 200 ETH
    goal_amount = round(random.uniform(50.0, 200.0), 2)
    # Calculate a random amount raised between 0 and goal amount
    funds_raised = round(random.uniform(0, goal_amount), 2)
    
    # Create citations string from authors and source, handling missing fields
    authors = paper_data.get('authors', ['Unknown Author'])
    source = paper_data.get('source', 'Unknown Source')
    topic = paper_data.get('topic', 'Research')
    url = paper_data.get('url', '#')
    
    citations = f'''
    1. {', '.join(authors)} - "{paper_data['title']}" ({source})
    2. Related work in {topic}
    3. Source URL: {url}
    '''
    
    # Upload PDF if available
    pdf_url = None
    if paper_data.get('local_pdf'):
        # Clean up the PDF path - remove any ./research_papers/ prefix
        pdf_filename = os.path.basename(paper_data['local_pdf'].replace('\\', '/'))
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_pdf_path = os.path.join(base_dir, 'research_papers', pdf_filename)
        
        # Remove this PDF upload from here - we'll do it after getting the project ID
        print(f"Full PDF path: {local_pdf_path}")
    
    # Determine if project is active
    is_active = random.random() > 0.2  # 80% chance of being active
    
    # Set theme properties exactly as expected by frontend
    status = 'active' if is_active else 'inactive'
    theme = 'default' if is_active else 'red'
    theme_color = 'default' if is_active else 'red'
    
    return {
        'title': f"Implementation of: {paper_data['title']}",
        'description': f"This project aims to implement and expand upon the research presented in '{paper_data['title']}'. {paper_data.get('abstract', 'No abstract available.')}\n\nWe will focus on practical implementation and real-world applications of this research.",
        'team_members': [],  # Will be populated with actual user IDs
        'citations': citations,
        'goal_amount': goal_amount,
        'funds_raised': funds_raised,
        'status': status,
        'theme': theme,
        'themeColor': theme_color,  # This is needed for proper styling
        'created_at': None,  # Will be set in add_research_projects
        'created_by': None,  # Will be set in add_research_projects
        'creator_name': None,  # Will be set in add_research_projects
        'documents': [],  # Will be populated with PDFs
        'updates': [],  # Empty updates array
        'comments': [],  # Empty comments array
        'backers': [],  # Empty backers array
        'research_paper': {
            'title': paper_data['title'],
            'authors': authors,
            'source': source,
            'topic': topic,
            'url': url,
            'local_pdf': paper_data.get('local_pdf', ''),
            'pdf_url': None  # This will be updated after we upload the PDF
        },
        'tags': [topic, 'Research', 'Implementation'],  # Add some relevant tags
        'views': random.randint(10, 100),  # Random view count
        'last_updated': None,  # Will be set same as created_at
        'completion_status': 0,  # Initial completion status
        'wallet_address': None  # Will be populated from creator's data if available
    }

def get_random_users(count=3):
    """Get random user IDs from Firestore."""
    users = []
    user_docs = firestore_db.collection('users').limit(10).get()
    all_users = [doc.id for doc in user_docs]
    
    if all_users:
        # Select random users, but no more than available
        count = min(count, len(all_users))
        users = random.sample(all_users, count)
    
    return users

def add_research_projects():
    """Add research-based projects to the database."""
    print("Starting to add research-based projects...")
    
    # Clear existing projects
    rtdb_ref.delete()
    print("Cleared existing projects")
    
    # Load paper metadata
    papers_data = load_paper_metadata()
    
    # Convert each paper into a project
    for paper_id, paper_data in papers_data.items():
        project = create_project_from_paper(paper_data)
        
        # Get random team members
        project['team_members'] = get_random_users()
        
        # Get a random creator from the team members
        creator_id = random.choice(project['team_members'])  # This is the Firestore user ID
        creator_doc = firestore_db.collection('users').document(creator_id).get()
        creator_data = creator_doc.to_dict()
        
        # Add creator information
        timestamp = datetime.now().isoformat()
        project['created_by'] = creator_id
        project['creator_name'] = creator_data.get('display_name', 'Unknown User')
        project['created_at'] = timestamp
        project['last_updated'] = timestamp
        project['wallet_address'] = creator_data.get('wallet_address')
        
        # First handle PDF upload using the creator's Firestore ID
        if paper_data.get('local_pdf'):
            pdf_filename = os.path.basename(paper_data['local_pdf'].replace('\\', '/'))
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            local_pdf_path = os.path.join(base_dir, 'research_papers', pdf_filename)
            
            # Create timestamp in the required format
            timestamp = datetime.now().isoformat()
            
            print(f"Full PDF path: {local_pdf_path}")
            # Using creator_id (Firestore ID) for storage path
            pdf_url = upload_pdf_to_storage(local_pdf_path, creator_id, timestamp)
            print(f"Resulting PDF URL: {pdf_url}")
            
            if pdf_url:
                # Get original filename without extension for the document name
                doc_name = os.path.splitext(pdf_filename)[0]
                
                # Add the PDF to the documents array instead of research_paper
                project['documents'].append({
                    'url': pdf_url,
                    'timestamp': timestamp,
                    'name': doc_name,
                    'type': 'pdf'
                })
                # Also keep it in research_paper for reference
                project['research_paper']['pdf_url'] = pdf_url
        
        # Then push the complete project to RTDB
        new_project_ref = rtdb_ref.push(project)
        project_id = new_project_ref.key
        
        # Verify the data after pushing
        stored_project = rtdb_ref.child(project_id).get()
        print("\nVerifying stored project data:")
        print(f"Documents array: {json.dumps(stored_project.get('documents', []), indent=2)}")
        
        # Update creator's projects array in Firestore
        creator_ref = firestore_db.collection('users').document(creator_id)
        creator_ref.update({
            'projects': firestore.ArrayUnion([project_id])
        })
        
        print(f"Added project: {project['title']}")
        print(f"Project ID: {project_id}")
        print(f"Creator: {project['creator_name']} ({creator_id})")
        print("---")

def update_research_projects():
    """Update theme and status of existing research projects."""
    print("Starting to update research projects...")
    
    # Get all existing projects
    all_projects = rtdb_ref.get()
    if not all_projects:
        print("No projects found to update.")
        return
    
    for project_id, project in all_projects.items():
        # Only update if it's a research project (has research_paper field)
        if not project.get('research_paper'):
            continue
            
        # Determine if project should be active
        is_active = random.random() > 0.2  # 80% chance of being active
        
        # Set theme properties
        status = 'active' if is_active else 'inactive'
        theme = 'default' if is_active else 'red'
        theme_color = 'default' if is_active else 'red'
        
        # Update only the necessary fields
        updates = {
            'status': status,
            'theme': theme,
            'themeColor': theme_color,
            'last_updated': datetime.now().isoformat()
        }
        
        # Update the project
        rtdb_ref.child(project_id).update(updates)
        
        print(f"Updated project: {project.get('title')}")
        print(f"New status: {status}")
        print(f"New theme: {theme}")
        print("---")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--create':
        # Create new projects
        add_research_projects()
        print("Research projects created successfully!")
    else:
        # Just update existing projects
        update_research_projects()
        print("Research projects updated successfully!") 