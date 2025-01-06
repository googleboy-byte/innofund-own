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
    try:
        # Get stats from RTDB
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        all_projects = rtdb_ref.get() or {}
        
        # Calculate stats
        active_projects = sum(1 for p in all_projects.values() if p.get('status') == 'active')
        total_eth = sum(float(p.get('funds_raised', 0)) for p in all_projects.values())
        
        # Get unique researchers (creators + team members)
        researchers = set()
        for project in all_projects.values():
            researchers.add(project.get('created_by'))
            researchers.update(project.get('team_members', []))
        researchers.discard(None)  # Remove None if present
        
        stats = {
            'total_projects': active_projects,
            'total_eth': round(total_eth, 2),
            'total_researchers': len(researchers)
        }
        
        # Get featured projects (top 3 by funding progress)
        featured_projects = []
        for project_id, project in all_projects.items():
            if project.get('status') == 'active':
                project['id'] = project_id
                project['funding_progress'] = (float(project.get('funds_raised', 0)) / float(project.get('goal_amount', 1))) * 100
                featured_projects.append(project)
        
        featured_projects.sort(key=lambda x: x['funding_progress'], reverse=True)
        featured_projects = featured_projects[:3]
        
        return render_template('landing1.html',
                             title='InnoFund - Decentralized Research Funding',
                             stats=stats,
                             featured_projects=featured_projects)
    except Exception as e:
        print(f"Error in index route: {str(e)}")
        return render_template('landing1.html',
                             title='InnoFund - Decentralized Research Funding',
                             stats={'total_projects': 0, 'total_eth': 0, 'total_researchers': 0},
                             featured_projects=[])

@main.route('/feed')
def feed():
    try:
        # Get initial projects from RTDB (just first 4)
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        all_projects = rtdb_ref.get()
        
        # Convert to list and get first 4
        projects_list = []
        if all_projects:
            for project_id, project in all_projects.items():
                project['id'] = project_id
                # Initialize votes if not present
                project['upvotes'] = project.get('upvotes', 0)
                project['downvotes'] = project.get('downvotes', 0)
                projects_list.append(project)
            projects_list = projects_list[:4]  # Only get first 4 projects
        
        return render_template('dashboard.html', 
                             title='Research Projects',
                             projects=projects_list)
    except Exception as e:
        print("Feed error:", str(e))
        import traceback
        traceback.print_exc()
        flash('Error loading projects', 'error')
        return redirect(url_for('main.about'))

@main.route('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('main.feed'))

@main.route('/about')
def about():
    return render_template('about.html', title='About')

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
            # Initialize new user document if it doesn't exist
            user_data = {
                'id': current_user.id,
                'email': current_user.email,
                'display_name': current_user.display_name,
                'photo_url': current_user.photo_url,
                'created_at': datetime.now(),
                'bio': '',
                'social_links': {
                    'linkedin': '',
                    'github': '',
                    'twitter': ''
                },
                'privacy_settings': {
                    'profile_private': False
                }
            }
            db.collection('users').document(current_user.id).set(user_data)
        else:
            user_data = user_doc.to_dict()
            user_data['id'] = current_user.id
            
            # Ensure all required fields exist
            if 'created_at' not in user_data:
                user_data['created_at'] = datetime.now()
            if 'bio' not in user_data:
                user_data['bio'] = ''
            if 'social_links' not in user_data:
                user_data['social_links'] = {'linkedin': '', 'github': '', 'twitter': ''}
            if 'privacy_settings' not in user_data:
                user_data['privacy_settings'] = {'profile_private': False}
        
        # Debug output
        print("\n=== Profile Data ===")
        print(f"User ID: {current_user.id}")
        print(f"Is Authenticated: {current_user.is_authenticated}")
        print(f"User Data: {user_data}")
        
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
        
        # Check privacy settings
        if not is_owner and user_data.get('privacy_settings', {}).get('profile_private', False):
            flash('This profile is private', 'error')
            return redirect(url_for('main.dashboard'))
        
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
            # Validate goal amount
            goal_amount = float(request.form['goal_amount'])
            if goal_amount <= 0:
                flash('Goal amount must be greater than 0', 'error')
                return redirect(url_for('main.create_project'))
            if goal_amount > 200:
                flash('Goal amount cannot exceed 200 ETH', 'error')
                return redirect(url_for('main.create_project'))

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
                'documents': [],
                'upvotes': 0,  # Initialize upvotes
                'downvotes': 0  # Initialize downvotes
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
        print("\n=== Loading My Projects ===")
        print(f"User ID: {current_user.id}")
        
        # Get user's project IDs from Firestore
        user_doc = db.collection('users').document(current_user.id).get()
        if not user_doc.exists:
            print("User document not found in Firestore")
            flash('User profile not found', 'error')
            return redirect(url_for('main.dashboard'))
            
        user_data = user_doc.to_dict()
        stored_project_ids = user_data.get('projects', [])
        print(f"Found {len(stored_project_ids)} stored project IDs")

        # Get all RTDB projects
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        all_projects = rtdb_ref.get() or {}
        valid_projects = {}
        
        # Find valid projects that belong to the user
        for project_id, project_data in all_projects.items():
            if project_data and isinstance(project_data, dict):
                if project_data.get('created_by') == current_user.id:
                    valid_projects[project_id] = project_data
                    
        print(f"Found {len(valid_projects)} valid projects for user")
        
        # Update user's project list if it's different
        valid_project_ids = list(valid_projects.keys())
        if set(valid_project_ids) != set(stored_project_ids):
            print("Updating user's project list in Firestore")
            db.collection('users').document(current_user.id).update({
                'projects': valid_project_ids
            })
            flash('Your project list has been updated.', 'info')
        
        # Get initial projects (first 6)
        projects = []
        for project_id in list(valid_projects.keys())[:6]:
            project_data = valid_projects[project_id]
            project_data['id'] = project_id
            projects.append(project_data)
        
        print(f"Returning {len(projects)} projects")
        return render_template('my_projects.html', 
                             title='My Projects',
                             projects=projects,
                             has_more=len(valid_projects) > 6)
                             
    except Exception as e:
        print("\n!!! My Projects Error !!!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print("Full traceback:")
        print(traceback.format_exc())
        flash('Error loading projects', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/api/my-projects')
@login_required
def get_my_projects():
    try:
        page = int(request.args.get('page', 1))
        per_page = 6
        start_idx = (page - 1) * per_page

        # Get all RTDB projects
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        all_projects = rtdb_ref.get() or {}
        
        # Filter projects that belong to the user
        user_projects = {
            pid: data for pid, data in all_projects.items()
            if data and isinstance(data, dict) and data.get('created_by') == current_user.id
        }
        
        # Sort projects by creation date (newest first)
        sorted_projects = sorted(
            user_projects.items(),
            key=lambda x: x[1].get('created_at', ''),
            reverse=True
        )
        
        # Paginate
        page_projects = sorted_projects[start_idx:start_idx + per_page]
        projects = []
        for project_id, project_data in page_projects:
            project_data['id'] = project_id
            projects.append(project_data)

        return jsonify({
            'projects': projects,
            'has_more': start_idx + per_page < len(sorted_projects)
        })

    except Exception as e:
        print("API my projects error:", str(e))
        return jsonify({'error': str(e)}), 500

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
        print(f"\n=== Starting View Project ===")
        print(f"Project ID: {project_id}")
        
        # Get project data
        project_ref = rtdb.reference('projects', app=get_app('rtdb')).child(project_id)
        print("Got project reference")
        project = project_ref.get()
        print(f"Project data: {project}")
        
        if not project:
            print("Project not found")
            flash('Project not found', 'error')
            return redirect(url_for('main.feed'))
            
        project['id'] = project_id
        
        # Ensure poll data is properly structured
        if 'poll' in project and project['poll']:
            poll = project['poll']
            # Ensure each option has votes and voters
            for option in poll.get('options', []):
                if 'votes' not in option:
                    option['votes'] = 0
                if 'voters' not in option:
                    option['voters'] = []
            # Ensure total_votes exists
            if 'total_votes' not in poll:
                poll['total_votes'] = sum(option.get('votes', 0) for option in poll.get('options', []))
        else:
            project['poll'] = None
        
        # Store browsing history if user is logged in
        if current_user.is_authenticated:
            try:
                print(f"Storing browsing history for user: {current_user.id}")
                user_doc_ref = db.collection('users').document(current_user.id)
                
                # Get current browsing history or initialize empty list
                user_doc = user_doc_ref.get()
                user_data = user_doc.to_dict() if user_doc.exists else {}
                browsing_history = user_data.get('browsing_history', [])
                
                # Create new history entry
                history_entry = {
                    'project_id': project_id,
                    'project_title': project.get('title', 'Unknown Project'),
                    'timestamp': datetime.now().isoformat(),
                    'category': project.get('category', 'Uncategorized')
                }
                
                # Add to beginning of list and keep only last 100 entries
                browsing_history.insert(0, history_entry)
                browsing_history = browsing_history[:100]
                
                # Update user document
                user_doc_ref.set({
                    'browsing_history': browsing_history
                }, merge=True)
                print("Browsing history updated successfully")
                
            except Exception as history_error:
                print(f"Error storing browsing history: {str(history_error)}")
                # Continue execution even if history storage fails
        
        # Get user's vote if logged in
        user_vote = None
        if current_user.is_authenticated:
            print(f"Getting votes for user: {current_user.id}")
            votes_ref = rtdb.reference('project_votes', app=get_app('rtdb')).child(project_id)
            user_votes = votes_ref.get() or {}
            user_vote = user_votes.get(current_user.id)
            print(f"User vote: {user_vote}")
        
        # Get creator info
        creator = None
        if project.get('created_by'):
            print(f"Getting creator info for: {project.get('created_by')}")
            creator_doc = db.collection('users').document(project['created_by']).get()
            if creator_doc.exists:
                creator = creator_doc.to_dict()
                print("Creator found")
            else:
                print("Creator document does not exist")
        
        # Get team member details
        team_members = []
        for member_id in project.get('team_members', []):
            print(f"Getting team member info for: {member_id}")
            member_doc = db.collection('users').document(member_id).get()
            if member_doc.exists:
                member_data = member_doc.to_dict()
                team_members.append({
                    'id': member_id,
                    'name': member_data.get('display_name', 'Unknown User'),
                    'photo_url': member_data.get('photo_url'),
                    'title': member_data.get('title', 'Team Member')
                })
                print(f"Team member found: {member_data.get('display_name')}")
            else:
                print(f"Team member document does not exist for ID: {member_id}")
        
        # Update project with detailed team member data
        project['team_members'] = team_members
        
        print("Rendering template...")
        return render_template('view_project.html',
                             title=project.get('title', 'View Project'),
                             project=project,
                             creator=creator,
                             is_owner=current_user.is_authenticated and current_user.id == project.get('created_by'),
                             user_vote=user_vote)
                             
    except Exception as e:
        print("\n!!! View Project Error !!!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print("Full traceback:")
        print(traceback.format_exc())
        flash('Error loading project', 'error')
        return redirect(url_for('main.feed'))

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
        project_ref = rtdb.reference('projects', app=get_app('rtdb')).child(project_id)
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
        import traceback
        print("Full traceback:")
        print(traceback.format_exc())
        return jsonify({'error': 'Error deactivating project'}), 500

@main.route('/api/projects')
def get_paginated_projects():
    try:
        page = int(request.args.get('page', 1))
        per_page = 4  # Number of projects per page
        
        # Get all projects from RTDB
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        all_projects = rtdb_ref.get()
        
        if not all_projects:
            return jsonify({'projects': [], 'has_more': False})
        
        # Convert to list
        projects_list = []
        for project_id, project in all_projects.items():
            project['id'] = project_id
            projects_list.append(project)
        
        # Calculate pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_projects = projects_list[start_idx:end_idx]
        
        return jsonify({
            'projects': paginated_projects,
            'has_more': end_idx < len(projects_list)
        })
    except Exception as e:
        print("Pagination error:", str(e))
        return jsonify({'error': 'Failed to load projects'}), 500

@main.route('/api/vote/<project_id>', methods=['POST'])
@login_required
def vote_project(project_id):
    try:
        data = request.get_json()
        vote_type = data.get('vote_type')
        
        if vote_type not in ['up', 'down']:
            return jsonify({'success': False, 'error': 'Invalid vote type'}), 400
            
        # Get project reference from RTDB
        project_ref = rtdb.reference(f'projects/{project_id}', app=get_app('rtdb'))
        project = project_ref.get()
        
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
            
        # Get user's current vote
        votes_ref = rtdb.reference(f'project_votes/{project_id}', app=get_app('rtdb'))
        user_votes = votes_ref.get() or {}
        current_vote = user_votes.get(current_user.id)
        
        # Update vote counts
        upvotes = project.get('upvotes', 0)
        downvotes = project.get('downvotes', 0)
        
        # Remove previous vote if exists
        if current_vote == 'up':
            upvotes = max(0, upvotes - 1)
        elif current_vote == 'down':
            downvotes = max(0, downvotes - 1)
        
        # Add new vote if different from current
        new_vote = None
        if vote_type != current_vote:
            if vote_type == 'up':
                upvotes += 1
                new_vote = 'up'
            else:
                downvotes += 1
                new_vote = 'down'
        
        # Update project votes
        project_ref.update({
            'upvotes': upvotes,
            'downvotes': downvotes
        })
        
        # Update user's vote
        if new_vote:
            votes_ref.update({current_user.id: new_vote})
        else:
            votes_ref.child(current_user.id).delete()
        
        return jsonify({
            'success': True,
            'upvotes': upvotes,
            'downvotes': downvotes,
            'user_vote': new_vote
        })
        
    except Exception as e:
        print("Voting error:", str(e))
        return jsonify({'success': False, 'error': str(e)}), 500

@main.route('/report_project', methods=['POST'])
@login_required
def report_project():
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        reason = data.get('reason')
        details = data.get('details')

        if not all([project_id, reason]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Get project title from RTDB
        project_ref = rtdb.reference(f'projects/{project_id}', app=get_app('rtdb'))
        project = project_ref.get()
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        # Create report document
        report = {
            'project_id': project_id,
            'reporter_id': current_user.id,
            'reporter_name': current_user.display_name,  # Use display_name instead of name
            'reason': reason,
            'details': details,
            'status': 'pending',
            'reported_at': datetime.utcnow(),
            'project_title': project.get('title', 'Unknown Project')
        }

        # Add report to Firestore
        db.collection('reported_projects').add(report)

        return jsonify({'message': 'Report submitted successfully'}), 200

    except Exception as e:
        print(f"Error reporting project: {str(e)}")  # Use print instead of app.logger
        return jsonify({'error': 'An error occurred while submitting the report'}), 500

@main.route('/api/donate/<project_id>', methods=['POST'])
@login_required
def donate(project_id):
    try:
        data = request.get_json()
        amount = float(data.get('amount', 0))
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid donation amount'}), 400
            
        # Get project from RTDB
        rtdb_ref = rtdb.reference(f'projects/{project_id}', app=get_app('rtdb'))
        project = rtdb_ref.get()
        
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
            
        if project.get('status') != 'active':
            return jsonify({'success': False, 'error': 'Project is not active'}), 400
            
        # Update project's funds_raised
        current_funds = float(project.get('funds_raised', 0))
        new_funds = current_funds + amount
        
        # Update in RTDB
        rtdb_ref.update({
            'funds_raised': new_funds
        })
        
        return jsonify({
            'success': True,
            'message': 'Donation processed successfully',
            'new_total': new_funds
        })
        
    except Exception as e:
        print("Donation error:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'An error occurred while processing the donation'}), 500

@main.route('/transaction-history')
@login_required
def transaction_history():
    try:
        print("\n=== Loading Transaction History ===")
        print(f"User ID: {current_user.id}")
        
        # Get all projects from RTDB
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        all_projects = rtdb_ref.get() or {}
        
        # Collect all transactions where user is involved
        transactions = []
        for project_id, project_data in all_projects.items():
            if not project_data or not isinstance(project_data, dict):
                continue
                
            # Add transactions where user is the contributor
            project_transactions = project_data.get('transactions', [])
            if isinstance(project_transactions, list):
                for tx in project_transactions:
                    if tx.get('contributor_id') == current_user.id:
                        tx['type'] = 'contribution'
                        tx['project'] = {
                            'id': project_id,
                            'title': project_data.get('title', 'Unknown Project'),
                            'creator_name': project_data.get('creator_name', 'Unknown Creator')
                        }
                        transactions.append(tx)
            
            # Add received contributions where user is the project creator
            if project_data.get('created_by') == current_user.id:
                for tx in project_transactions:
                    tx['type'] = 'received'
                    tx['project'] = {
                        'id': project_id,
                        'title': project_data.get('title', 'Unknown Project')
                    }
                    transactions.append(tx)
        
        # Sort transactions by timestamp (newest first)
        transactions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        print(f"Found {len(transactions)} transactions")
        
        return render_template('transaction_history.html',
                             title='Transaction History',
                             transactions=transactions)
                             
    except Exception as e:
        print("\n!!! Transaction History Error !!!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print("Full traceback:")
        print(traceback.format_exc())
        flash('Error loading transaction history', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    try:
        data = request.get_json()
        
        # Get current user document
        user_doc = db.collection('users').document(current_user.id)
        
        # Prepare update data
        update_data = {
            'bio': data.get('bio', ''),
            'social_links': {
                'linkedin': data.get('social_links', {}).get('linkedin', ''),
                'github': data.get('social_links', {}).get('github', ''),
                'twitter': data.get('social_links', {}).get('twitter', '')
            },
            'privacy_settings': {
                'profile_private': data.get('privacy_settings', {}).get('profile_private', False)
            },
            'updated_at': datetime.now()
        }
        
        # Update the user document
        user_doc.update(update_data)
        
        return jsonify({'success': True}), 200
    except Exception as e:
        print("Profile update error:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to update profile'}), 500

@main.route('/api/create_poll/<project_id>', methods=['POST'])
@login_required
def create_poll(project_id):
    try:
        # Get project from RTDB
        rtdb_ref = rtdb.reference(f'projects/{project_id}', app=get_app('rtdb'))
        project = rtdb_ref.get()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
            
        # Check if user is project owner
        if project.get('created_by') != current_user.id:
            return jsonify({'error': 'Only project owner can create polls'}), 403
            
        # Get poll data from request
        data = request.get_json()
        question = data.get('question')
        options = data.get('options', [])
        
        # Validate poll data
        if not question or not options:
            return jsonify({'error': 'Question and options are required'}), 400
            
        if len(options) < 2 or len(options) > 5:
            return jsonify({'error': 'Poll must have between 2 and 5 options'}), 400
            
        # Create poll object
        poll = {
            'question': question,
            'options': [{'id': str(i), 'text': opt, 'votes': 0, 'voters': []} for i, opt in enumerate(options)],
            'total_votes': 0,
            'created_at': datetime.now().isoformat()
        }
        
        # Update project with new poll
        rtdb_ref.update({
            'poll': poll
        })
        
        return jsonify({'message': 'Poll created successfully'}), 200
        
    except Exception as e:
        print(f"Error creating poll: {str(e)}")
        return jsonify({'error': 'Failed to create poll'}), 500

@main.route('/api/vote_poll/<project_id>/<option_id>', methods=['POST'])
@login_required
def vote_poll(project_id, option_id):
    try:
        # Get project from RTDB
        rtdb_ref = rtdb.reference(f'projects/{project_id}', app=get_app('rtdb'))
        project = rtdb_ref.get()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
            
        poll = project.get('poll')
        if not poll:
            return jsonify({'error': 'No active poll found'}), 404
            
        # Find the option
        option_found = False
        user_previous_vote = None
        target_option = None
        
        # Ensure all options have a voters list
        for option in poll['options']:
            if 'voters' not in option:
                option['voters'] = []
            
            # Check if user already voted for this option
            if current_user.id in option['voters']:
                if option['id'] == option_id:
                    return jsonify({'error': 'Already voted for this option'}), 400
                else:
                    user_previous_vote = option
                    
            if option['id'] == option_id:
                option_found = True
                target_option = option
                
        if not option_found:
            return jsonify({'error': 'Invalid option'}), 400
            
        # Remove previous vote if exists
        if user_previous_vote:
            user_previous_vote['votes'] = max(0, user_previous_vote['votes'] - 1)
            user_previous_vote['voters'].remove(current_user.id)
            poll['total_votes'] = max(0, poll['total_votes'] - 1)
            
        # Add new vote
        if 'votes' not in target_option:
            target_option['votes'] = 0
        target_option['votes'] += 1
        target_option['voters'].append(current_user.id)
        if 'total_votes' not in poll:
            poll['total_votes'] = 0
        poll['total_votes'] += 1
        
        # Update project with updated poll
        rtdb_ref.update({
            'poll': poll
        })
        
        return jsonify({'message': 'Vote recorded successfully'}), 200
        
    except Exception as e:
        print(f"Error voting on poll: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to record vote'}), 500

@main.route('/api/delete_poll/<project_id>', methods=['POST'])
@login_required
def delete_poll(project_id):
    try:
        # Get project from RTDB
        rtdb_ref = rtdb.reference(f'projects/{project_id}', app=get_app('rtdb'))
        project = rtdb_ref.get()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
            
        # Check if user is project owner
        if project.get('created_by') != current_user.id:
            return jsonify({'error': 'Only project owner can delete polls'}), 403
            
        # Delete the poll by setting it to None
        rtdb_ref.update({
            'poll': None
        })
        
        return jsonify({'message': 'Poll deleted successfully'}), 200
        
    except Exception as e:
        print(f"Error deleting poll: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to delete poll'}), 500
