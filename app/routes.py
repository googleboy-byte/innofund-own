from flask import Blueprint, render_template, redirect, url_for, jsonify, session, abort, request, flash
import firebase_admin
from firebase_admin import credentials, firestore, storage
from firebase_admin import db as rtdb  # Rename to avoid confusion
from firebase_admin import get_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
from app import db  # This is the Firestore client

main = Blueprint('main', __name__)

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main.route('/dashboard')
@login_required
def dashboard():
    try:
        # Get all projects from RTDB
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        all_projects = rtdb_ref.get()
        
        # Convert to list and shuffle for random feed
        projects_list = []
        if all_projects:
            for project_id, project in all_projects.items():
                project['id'] = project_id
                projects_list.append(project)
            
            # Shuffle the list for random feed
            from random import shuffle
            shuffle(projects_list)
        
        return render_template('dashboard.html', 
                             title='Dashboard',
                             projects=projects_list)
    except Exception as e:
        print("Dashboard error:", str(e))
        import traceback
        traceback.print_exc()
        return redirect(url_for('auth.logout'))

@main.route('/debug')
def debug():
    output = {
        'is_authenticated': current_user.is_authenticated,
        'user_id': current_user.get_id() if hasattr(current_user, 'get_id') else None,
        'session': dict(session)
    }
    return jsonify(output)

@main.route('/my-profile')
@login_required
def profile():
    try:
        # Get the current user's ID
        user_doc = db.collection('users').document(current_user.id).get()
        if not user_doc.exists:
            flash('Profile not found', 'error')
            return redirect(url_for('main.dashboard'))
            
        user_data = user_doc.to_dict()
        user_data['id'] = current_user.id
        # Pass the public profile URL instead of using the current route
        profile_url = url_for('main.public_profile', user_id=current_user.id, _external=True)
        return render_template('profile.html', 
                             title='My Profile', 
                             user=user_data, 
                             is_owner=True,
                             profile_url=profile_url)
    except Exception as e:
        print("Profile error:", str(e))
        import traceback
        traceback.print_exc()
        flash('Error loading profile', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/profile/<user_id>')
def public_profile(user_id):
    try:
        # Get user data from Firestore
        user_doc = db.collection('users').document(user_id).get()
        
        if not user_doc.exists:
            abort(404)  # User not found
            
        user_data = user_doc.to_dict()
        user_data['uid'] = user_id  # Add UID to the data
        
        # Check if the profile belongs to the current user
        is_owner = current_user.is_authenticated and current_user.id == user_id
        
        # Generate the shareable URL
        profile_url = url_for('main.public_profile', user_id=user_id, _external=True)
        
        return render_template('profile.html', 
                             title=f"{user_data.get('display_name', 'User')} - Profile",
                             user=user_data,
                             is_owner=is_owner,
                             profile_url=profile_url)
    except Exception as e:
        print(f"Public profile error for {user_id}:", str(e))
        import traceback
        traceback.print_exc()
        abort(404)

@main.route('/create-project', methods=['GET', 'POST'])
@login_required
def create_project():
    try:
        if request.method == 'POST':
            print("\n=== Starting Project Creation ===")
            
            # Debug Firebase apps
            print("\nChecking Firebase Apps:")
            print("Available Firebase apps:", list(firebase_admin._apps.keys()))
            
            # Debug form data
            print("\nForm Data:")
            print("Title:", request.form.get('title'))
            print("Description:", request.form.get('description'))
            print("Team Members:", request.form.getlist('team_members[]'))
            print("Citations:", request.form.get('citations'))
            print("Goal Amount:", request.form.get('goal_amount'))
            
            # Debug files
            print("\nFile Upload Data:")
            if 'documents[]' in request.files:
                files = request.files.getlist('documents[]')
                print(f"Number of files: {len(files)}")
                for file in files:
                    print(f"File: {file.filename}, Content Type: {file.content_type}")
            else:
                print("No files uploaded")

            # Clean up team member IDs
            team_members = request.form.getlist('team_members[]')
            cleaned_team_members = []
            for member in team_members:
                # Extract just the ID if it's a URL
                if isinstance(member, str):
                    member_id = member.split('/')[-1]
                    cleaned_team_members.append(member_id)
            
            project_data = {
                'title': request.form['title'],
                'description': request.form['description'],
                'team_members': cleaned_team_members,  # Use cleaned IDs
                'citations': request.form['citations'],
                'goal_amount': float(request.form['goal_amount']),
                'funds_raised': 0.0,  # Initialize funds raised
                'created_at': datetime.now().isoformat(),
                'created_by': current_user.id,
                'creator_name': current_user.display_name,
                'status': 'active',
                'documents': []
            }
            print("\nProject Data:", project_data)

            try:
                print("\n=== Storage Operations ===")
                storage_app = get_app('storage')
                print("Storage app retrieved:", storage_app.name)
                bucket = storage.bucket(app=storage_app)
                print("Storage bucket retrieved:", bucket.name)
                
                if 'documents[]' in request.files:
                    files = request.files.getlist('documents[]')
                    for file in files:
                        if file and file.filename:
                            try:
                                filename = secure_filename(file.filename)
                                file_path = f"projects/{current_user.id}/{project_data['created_at']}/{filename}"
                                print(f"\nUploading file: {file_path}")
                                
                                file_content = file.read()
                                print(f"File size: {len(file_content)} bytes")
                                
                                blob = bucket.blob(file_path)
                                blob.upload_from_string(
                                    file_content,
                                    content_type=file.content_type
                                )
                                blob.make_public()
                                print(f"File uploaded successfully. Public URL: {blob.public_url}")
                                
                                project_data['documents'].append({
                                    'name': filename,
                                    'url': blob.public_url
                                })
                            except Exception as file_error:
                                print(f"Error uploading file {filename}:", str(file_error))
                                raise
            except Exception as storage_error:
                print("\nStorage error:", str(storage_error))
                print("Storage error type:", type(storage_error).__name__)
                import traceback
                print(traceback.format_exc())
                raise

            try:
                print("\n=== RTDB Operations ===")
                rtdb_app = get_app('rtdb')
                print("RTDB app retrieved:", rtdb_app.name)
                ref = rtdb.reference('projects', app=rtdb_app)
                new_project_ref = ref.push(project_data)
                print("Project saved to RTDB. Key:", new_project_ref.key)
            except Exception as rtdb_error:
                print("\nRTDB error:", str(rtdb_error))
                print("RTDB error type:", type(rtdb_error).__name__)
                import traceback
                print(traceback.format_exc())
                raise

            try:
                print("\n=== Firestore Operations ===")
                print("Updating user document for ID:", current_user.id)
                user_doc = db.collection('users').document(current_user.id)
                user_doc.update({
                    'projects': firestore.ArrayUnion([new_project_ref.key])
                })
                print("User document updated successfully")
            except Exception as firestore_error:
                print("\nFirestore error:", str(firestore_error))
                print("Firestore error type:", type(firestore_error).__name__)
                import traceback
                print(traceback.format_exc())
                raise

            print("\n=== Project Creation Completed Successfully ===")
            flash('Project created successfully!', 'success')
            return redirect(url_for('main.dashboard'))

        return render_template('create_project.html', title='Create Project')
    
    except Exception as e:
        print("\n!!! Project Creation Failed !!!")
        print("Error:", str(e))
        print("Error type:", type(e).__name__)
        import traceback
        print(traceback.format_exc())
        flash('An error occurred while creating the project.', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/my-projects')
@login_required
def my_projects():
    try:
        # Get user's project IDs from Firestore
        user_doc = db.collection('users').document(current_user.id).get()
        user_data = user_doc.to_dict()
        project_ids = user_data.get('projects', [])

        # Get project details from RTDB
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        projects = []
        
        for project_id in project_ids:
            project_data = rtdb_ref.child(project_id).get()
            if project_data:
                project_data['id'] = project_id
                projects.append(project_data)
        
        return render_template('my_projects.html', 
                             title='My Projects',
                             projects=projects)
                             
    except Exception as e:
        print("My projects error:", str(e))
        import traceback
        traceback.print_exc()
        flash('Error loading projects', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/edit-project/<project_id>', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    try:
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        project_ref = rtdb_ref.child(project_id)
        
        if request.method == 'POST':
            # Get current project data to preserve funds_raised
            current_project = project_ref.get()
            
            # Update project data
            project_data = {
                'title': request.form['title'],
                'description': request.form['description'],
                'team_members': request.form.getlist('team_members[]'),
                'citations': request.form['citations'],
                'goal_amount': float(request.form['goal_amount']),
                'funds_raised': current_project.get('funds_raised', 0.0),  # Preserve existing funds
                'last_updated': datetime.utcnow().isoformat()
            }
            
            # Handle new file uploads
            if 'documents[]' in request.files:
                files = request.files.getlist('documents[]')
                bucket = storage.bucket(app=get_app('storage'))
                
                for file in files:
                    if file and file.filename:
                        filename = secure_filename(file.filename)
                        file_path = f"projects/{current_user.id}/{datetime.utcnow().isoformat()}/{filename}"
                        blob = bucket.blob(file_path)
                        blob.upload_from_string(
                            file.read(),
                            content_type=file.content_type
                        )
                        blob.make_public()
                        
                        # Append to existing documents
                        if 'documents' not in project_data:
                            project_data['documents'] = []
                        project_data['documents'].append({
                            'name': filename,
                            'url': blob.public_url
                        })
            
            # Update the project
            project_ref.update(project_data)
            flash('Project updated successfully!', 'success')
            return redirect(url_for('main.my_projects'))
            
        # GET request - show edit form
        project_data = project_ref.get()
        if not project_data:
            flash('Project not found', 'error')
            return redirect(url_for('main.my_projects'))
            
        if project_data['created_by'] != current_user.id:
            flash('Unauthorized access', 'error')
            return redirect(url_for('main.my_projects'))
            
        return render_template('edit_project.html',
                             title='Edit Project',
                             project=project_data)
                             
    except Exception as e:
        print("Edit project error:", str(e))
        import traceback
        traceback.print_exc()
        flash('Error updating project', 'error')
        return redirect(url_for('main.my_projects'))

@main.route('/update-project-funds/<project_id>', methods=['POST'])
@login_required
def update_project_funds(project_id):
    try:
        print(f"\n=== Starting Donation Process ===")
        print(f"Project ID: {project_id}")
        print(f"User ID: {current_user.id}")
        print(f"Request Content-Type: {request.content_type}")
        print(f"Request Headers: {dict(request.headers)}")
        
        if request.content_type != 'application/json':
            print(f"Invalid content type: {request.content_type}")
            return jsonify({'error': 'Content-Type must be application/json'}), 415
            
        print(f"Request data: {request.get_data()}")
        data = request.get_json()
        print(f"Received data: {data}")
        amount = float(data.get('amount', 0))
        print(f"Amount: {amount}")
        
        if amount <= 0:
            return jsonify({'error': 'Invalid amount'}), 400

        # Get project reference
        print("\nGetting project reference...")
        project_ref = rtdb.reference(f'projects/{project_id}', app=get_app('rtdb'))
        project = project_ref.get()
        print(f"Project data: {project}")
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
            
        # Check if project is active
        if project.get('status') != 'active':
            return jsonify({'error': 'This project is no longer accepting donations'}), 400
            
        # Check if user is project creator
        if project['created_by'] == current_user.id:
            return jsonify({'error': 'You cannot donate to your own project'}), 400
            
        # Update funds
        current_funds = float(project.get('funds_raised', 0))
        new_funds = current_funds + amount
        goal_amount = float(project.get('goal_amount', 0))
        print(f"\nCurrent funds: {current_funds}")
        print(f"New funds: {new_funds}")
        print(f"Goal amount: {goal_amount}")

        # Check if new funds would exceed goal
        if new_funds > goal_amount:
            return jsonify({'error': 'Donation amount would exceed project goal'}), 400
            
        # Get existing transactions or initialize empty list
        transactions = project.get('transactions', [])
        print(f"\nExisting transactions: {transactions}")
        if not isinstance(transactions, list):
            transactions = []
            
        # Add new transaction
        new_transaction = {
            'amount': amount,
            'contributor_id': current_user.id,
            'contributor_name': current_user.display_name,
            'timestamp': datetime.now().isoformat()
        }
        print(f"\nNew transaction: {new_transaction}")
        transactions.append(new_transaction)
        
        # Update project
        try:
            print("\nUpdating project in RTDB...")
            project_ref.update({
                'funds_raised': new_funds,
                'transactions': transactions
            })
            print("Update successful!")
            return jsonify({'success': True})
        except Exception as update_error:
            print(f"\nError during RTDB update: {str(update_error)}")
            import traceback
            print(traceback.format_exc())
            raise
            
    except Exception as e:
        print("\n!!! Donation Error !!!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': 'Error processing donation'}), 500

@main.route('/search-projects')
def search_projects():
    try:
        query = request.args.get('q', '').lower()
        filters = {
            'status': request.args.get('status'),
            'min_goal': request.args.get('min_goal', type=float),
            'max_goal': request.args.get('max_goal', type=float),
            'sort_by': request.args.get('sort_by', 'recent')  # recent, goal, progress
        }
        
        # Get all projects
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        all_projects = rtdb_ref.get()
        
        if not all_projects:
            return jsonify([])
            
        # Filter and search projects
        results = []
        for project_id, project in all_projects.items():
            project['id'] = project_id
            
            # Search in title and description
            if query and query not in project['title'].lower() and query not in project['description'].lower():
                continue
                
            # Apply filters
            if filters['status'] and project['status'] != filters['status']:
                continue
                
            if filters['min_goal'] and project['goal_amount'] < filters['min_goal']:
                continue
                
            if filters['max_goal'] and project['goal_amount'] > filters['max_goal']:
                continue
                
            results.append(project)
        
        # Sort results
        if filters['sort_by'] == 'recent':
            results.sort(key=lambda x: x['created_at'], reverse=True)
        elif filters['sort_by'] == 'goal':
            results.sort(key=lambda x: x['goal_amount'], reverse=True)
        elif filters['sort_by'] == 'progress':
            results.sort(key=lambda x: (x.get('funds_raised', 0) / x['goal_amount']), reverse=True)
            
        return jsonify(results)
        
    except Exception as e:
        print("Search error:", str(e))
        return jsonify({'error': str(e)}), 500

@main.route('/view-project/<project_id>')
def view_project(project_id):
    try:
        # Get project details from RTDB
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        project = rtdb_ref.child(project_id).get()
        
        if not project:
            flash('Project not found', 'error')
            return redirect(url_for('main.dashboard'))
            
        # Add project ID to the data
        project['id'] = project_id
        
        # Get creator details from Firestore
        creator = db.collection('users').document(project['created_by']).get()
        creator_data = creator.to_dict() if creator.exists else None
        
        # Ensure wallet_address is included in creator_data
        if creator_data and 'wallet_address' not in creator_data:
            creator_data['wallet_address'] = None
        
        # Get team member details from Firestore
        team_members_data = []
        for member_id in project.get('team_members', []):
            # Clean up the member_id if it's a full URL
            if isinstance(member_id, str):
                # Extract just the ID from the URL if present
                member_id = member_id.split('/')[-1]
            
            try:
                member_doc = db.collection('users').document(member_id).get()
                if member_doc.exists:
                    member_data = member_doc.to_dict()
                    team_members_data.append({
                        'name': member_data.get('display_name', 'Unknown'),
                        'photo_url': member_data.get('photo_url'),
                        'title': member_data.get('title', 'Team Member'),
                        'id': member_id
                    })
            except Exception as member_error:
                print(f"Error fetching member {member_id}:", str(member_error))
                continue
        
        # Update project with detailed team member data
        project['team_members'] = team_members_data
        
        return render_template('view_project.html',
                             title=project['title'],
                             project=project,
                             creator=creator_data,
                             is_owner=current_user.is_authenticated and current_user.id == project['created_by'])
                             
    except Exception as e:
        print("View project error:", str(e))
        import traceback
        traceback.print_exc()
        flash('Error loading project', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/connect-wallet')
@login_required
def connect_wallet():
    if current_user.wallet_address:
        return redirect(url_for('main.dashboard'))
    return render_template('connect_wallet.html', title='Connect Wallet')

@main.route('/save-wallet', methods=['POST'])
@login_required
def save_wallet():
    try:
        data = request.get_json()
        wallet_address = data.get('wallet_address')
        
        if not wallet_address:
            return jsonify({'error': 'No wallet address provided'}), 400
            
        # Update user document in Firestore
        user_ref = db.collection('users').document(current_user.id)
        user_ref.update({
            'wallet_address': wallet_address,
            'wallet_connected_at': datetime.now()
        })
        
        # Update current_user
        current_user.wallet_address = wallet_address
        current_user.wallet_connected_at = datetime.now()
        
        return jsonify({'success': True})
    except Exception as e:
        print("Save wallet error:", str(e))
        return jsonify({'error': str(e)}), 500

@main.route('/api/user/<user_id>')
def get_user_data(user_id):
    try:
        # Get user data from Firestore
        user_doc = db.collection('users').document(user_id).get()
        
        if not user_doc.exists:
            return jsonify({'success': False, 'error': 'User not found'})
            
        user_data = user_doc.to_dict()
        return jsonify({
            'success': True,
            'display_name': user_data.get('display_name'),
            'photo_url': user_data.get('photo_url')
        })
    except Exception as e:
        print("Error fetching user data:", str(e))
        return jsonify({'success': False, 'error': 'Failed to fetch user data'})

@main.route('/deactivate-project/<project_id>', methods=['POST'])
@login_required
def deactivate_project(project_id):
    try:
        # Get project reference
        project_ref = rtdb.reference(f'projects/{project_id}', app=get_app('rtdb'))
        project = project_ref.get()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
            
        # Check if user is the project owner
        if project['created_by'] != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
            
        # Update project status
        project_ref.update({
            'status': 'inactive',
            'deactivated_at': datetime.now().isoformat()
        })
        
        return jsonify({'success': True})
        
    except Exception as e:
        print("Deactivate project error:", str(e))
        return jsonify({'error': 'Error deactivating project'}), 500
