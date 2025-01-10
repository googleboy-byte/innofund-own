from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, timezone
from decimal import Decimal
from web3 import Web3
import firebase_admin
from firebase_admin import credentials, firestore, storage
from firebase_admin import db as rtdb
from firebase_admin import get_app
from .utils.web3_utils import (
    contribute_to_project, 
    create_project_on_chain, 
    get_platform_fees,
    get_project_details
)

# Initialize Firestore
db = firestore.client()

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
@login_required
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
                if isinstance(project.get('created_at'), str):
                    try:
                        project['created_at'] = datetime.fromisoformat(project['created_at'])
                    except (ValueError, TypeError):
                        project['created_at'] = None
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
                flash('Goal amount cannot exceed 200 AVAX', 'error')
                return redirect(url_for('main.create_project'))

            print("\n=== Starting Project Creation ===")
            
            # Create project on blockchain first
            try:
                blockchain_project_id = create_project_on_chain(
                    name=request.form['title'],
                    description=request.form['description'],
                    funding_goal=goal_amount,
                    deadline_days=30
                )
                print(f"Created project on blockchain with ID: {blockchain_project_id}")
            except Exception as e:
                print(f"Error creating project on blockchain: {str(e)}")
                flash('Failed to create project on blockchain. Please try again.', 'error')
                return redirect(url_for('main.create_project'))

            # Clean up team member IDs
            team_members = request.form.getlist('team_members[]')
            cleaned_team_members = []
            for member in team_members:
                if isinstance(member, str):
                    member_id = member.split('/')[-1]
                    cleaned_team_members.append(member_id)
            
            # Prepare project data
            project_data = {
                'title': request.form['title'],
                'description': request.form['description'],
                'team_members': cleaned_team_members,
                'citations': request.form['citations'],
                'goal_amount': goal_amount,
                'funds_raised': 0.0,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'created_by': current_user.id,
                'creator_name': current_user.display_name,
                'status': 'active',
                'documents': [],
                'upvotes': 0,
                'downvotes': 0,
                'blockchain_project_id': int(blockchain_project_id)  # Store blockchain ID
            }
            
            print("\nProject Data:", project_data)

            # Handle file uploads
            if 'documents[]' in request.files:
                storage_app = get_app('storage')
                bucket = storage.bucket(app=storage_app)
                
                files = request.files.getlist('documents[]')
                for file in files:
                    if file and file.filename:
                        try:
                            filename = secure_filename(file.filename)
                            file_path = f"projects/{current_user.id}/{project_data['created_at']}/{filename}"
                            
                            blob = bucket.blob(file_path)
                            blob.upload_from_string(
                                file.read(),
                                content_type=file.content_type
                            )
                            blob.make_public()
                            
                            project_data['documents'].append({
                                'name': filename,
                                'url': blob.public_url
                            })
                        except Exception as e:
                            print(f"Error uploading file {filename}:", str(e))
                            continue

            # Save to RTDB
            rtdb_app = get_app('rtdb')
            ref = rtdb.reference('projects', app=rtdb_app)
            new_project_ref = ref.push(project_data)
            
            # Also save to Firestore for better querying
            firestore_project_data = project_data.copy()
            firestore_project_data['rtdb_key'] = new_project_ref.key
            db.collection('projects').document(new_project_ref.key).set(firestore_project_data)

            # Update user's projects list
            user_doc = db.collection('users').document(current_user.id)
            user_doc.update({
                'projects': firestore.ArrayUnion([new_project_ref.key])
            })

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
        
        # Get user's stored project IDs
        user_doc = db.collection('users').document(current_user.id).get()
        if not user_doc.exists:
            return redirect(url_for('main.dashboard'))
            
        user_data = user_doc.to_dict()
        stored_project_ids = user_data.get('projects', [])
        print(f"Found {len(stored_project_ids)} stored project IDs")

        # Get all RTDB projects
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        all_projects = rtdb_ref.get()
        
        if not all_projects:
            return render_template('my_projects.html',
                                 title='My Projects',
                                 projects=[],
                                 has_more=False)
        
        # Filter and process projects
        valid_projects = []
        for project_id, project_data in all_projects.items():
            if not project_data or not isinstance(project_data, dict):
                continue
                
            if project_data.get('created_by') == current_user.id:
                project_data['id'] = project_id
                
                # Convert timestamps
                created_at = project_data.get('created_at')
                if isinstance(created_at, str):
                    project_data['created_at'] = datetime.fromisoformat(created_at)
                deadline = project_data.get('deadline')
                if isinstance(deadline, str):
                    project_data['deadline'] = datetime.fromisoformat(deadline)
                    
                valid_projects.append(project_data)
                
        print(f"Found {len(valid_projects)} valid projects for user")
        
        # Sort projects by creation date (newest first)
        valid_projects.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        
        # Get first 6 projects for initial display
        display_projects = valid_projects[:6]
        print(f"Returning {len(display_projects)} projects")
        
        return render_template('my_projects.html',
                             title='My Projects',
                             projects=display_projects,
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
        all_projects = rtdb_ref.get()
        
        if not all_projects:
            return jsonify({'projects': [], 'has_more': False})
        
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

        # Forward to blockchain route
        response = requests.post(
            url_for('blockchain.contribute', project_id=project_id, _external=True),
            json={'amount': amount}
        )
        
        if not response.ok:
            return jsonify({'error': response.json().get('error', 'Failed to process donation')}), response.status_code
            
        return jsonify(response.json())

    except Exception as e:
        print("\n!!! Donation Error !!!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print("Full traceback:")
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
            
        # Convert to list
        projects_list = []
        for project_id, project in all_projects.items():
            project['id'] = project_id
            projects_list.append(project)
        
        # Filter and search projects
        results = []
        for project in projects_list:
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
        print("\n=== Starting View Project ===")
        print(f"Project ID: {project_id}")
        
        # Get project data from RTDB
        print("Got project reference")
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        project = rtdb_ref.child(project_id).get()
        
        if not project:
            flash('Project not found', 'error')
            return redirect(url_for('main.feed'))
            
        print("Project data:", project)
        
        # Convert string timestamps to datetime objects
        if isinstance(project.get('created_at'), str):
            project['created_at'] = datetime.fromisoformat(project['created_at'])
        if isinstance(project.get('last_updated'), str):
            project['last_updated'] = datetime.fromisoformat(project['last_updated'])
            
        # Convert transaction timestamps
        if 'transactions' in project:
            for tx in project['transactions']:
                if isinstance(tx.get('timestamp'), str):
                    tx['timestamp'] = datetime.fromisoformat(tx['timestamp'])
                    
        # Store in browsing history if user is logged in
        if current_user.is_authenticated:
            print(f"Storing browsing history for user: {current_user.id}")
            try:
                history_ref = db.collection('browsing_history').document(current_user.id)
                history = history_ref.get()
                
                if history.exists:
                    current_history = history.to_dict().get('history', [])
                else:
                    current_history = []
                    
                # Add current project to history
                current_history.append({
                    'project_id': project_id,
                    'timestamp': datetime.now(timezone.utc)
                })
                
                # Keep only last 50 items
                if len(current_history) > 50:
                    current_history = current_history[-50:]
                    
                history_ref.set({'history': current_history}, merge=True)
                print("Browsing history updated successfully")
                
            except Exception as e:
                print(f"Error updating browsing history: {str(e)}")
                
        # Get user's vote if logged in
        user_vote = None
        if current_user.is_authenticated:
            print(f"Getting votes for user: {current_user.id}")
            votes_ref = rtdb.reference(f'project_votes/{project_id}', app=get_app('rtdb'))
            votes = votes_ref.get() or {}
            user_vote = votes.get(current_user.id)
            print(f"User vote: {user_vote}")
            
        # Get creator info
        creator_id = project.get('created_by')
        creator = None
        if creator_id:
            print(f"Getting creator info for: {creator_id}")
            creator_doc = db.collection('users').document(creator_id).get()
            if creator_doc.exists:
                creator = creator_doc.to_dict()
                print("Creator found")
                
        # Get team member info
        team_members = []
        for member_id in project.get('team_members', []):
            print(f"Getting team member info for: {member_id}")
            member_doc = db.collection('users').document(member_id).get()
            if member_doc.exists:
                member_data = member_doc.to_dict()
                team_members.append({
                    'id': member_id,
                    'name': member_data.get('name', 'Unknown'),
                    'email': member_data.get('email'),
                    'role': member_data.get('role', 'Member'),
                    'photo_url': member_data.get('photo_url', None),
                    'title': member_data.get('role', 'Team Member')  # Use role as title if available
                })
                print(f"Team member found: {member_data}")
            else:
                # Add basic info for members not found in database
                team_members.append({
                    'id': member_id,
                    'name': 'Unknown Member',
                    'email': None,
                    'role': 'Member',
                    'photo_url': None,
                    'title': 'Team Member'
                })
                
        print("Rendering template...")
        return render_template('view_project.html',
                             title=project.get('title'),
                             project=project,
                             creator=creator,
                             team_members=team_members,
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
    try:
        print("\n=== Connecting Wallet ===")
        print(f"User ID: {current_user.id}")
        
        # Get user data from Firestore
        user_doc = db.collection('users').document(current_user.id).get()
        if not user_doc.exists:
            print("User document not found")
            return jsonify({'error': 'User not found'}), 404
            
        user_data = user_doc.to_dict()
        wallet_address = user_data.get('wallet_address')
        
        if wallet_address:
            print(f"Wallet already connected: {wallet_address}")
            return render_template('connect_wallet.html', 
                                 wallet_address=wallet_address,
                                 is_connected=True)
        
        print("No wallet connected yet")
        return render_template('connect_wallet.html', 
                             is_connected=False)
                             
    except Exception as e:
        print(f"Error in connect_wallet: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Error connecting wallet', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/api/connect-wallet', methods=['POST'])
@login_required
def api_connect_wallet():
    try:
        print("\n=== Processing Wallet Connection ===")
        print(f"User ID: {current_user.id}")
        
        data = request.get_json()
        if not data or 'wallet_address' not in data:
            return jsonify({'error': 'No wallet address provided'}), 400
            
        wallet_address = data['wallet_address']
        if not Web3.is_address(wallet_address):
            return jsonify({'error': 'Invalid wallet address'}), 400
            
        # Update user's wallet address in Firestore
        db.collection('users').document(current_user.id).update({
            'wallet_address': wallet_address,
            'wallet_connected_at': datetime.now(timezone.utc)
        })
        
        print(f"Wallet connected successfully: {wallet_address}")
        return jsonify({
            'success': True,
            'wallet_address': wallet_address
        })
        
    except Exception as e:
        print(f"Error in api_connect_wallet: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to connect wallet'}), 500

@main.route('/api/disconnect-wallet', methods=['POST'])
@login_required
def api_disconnect_wallet():
    try:
        print("\n=== Processing Wallet Disconnection ===")
        print(f"User ID: {current_user.id}")
        
        # Remove wallet address from user's document
        db.collection('users').document(current_user.id).update({
            'wallet_address': None,
            'wallet_connected_at': None
        })
        
        print("Wallet disconnected successfully")
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error in api_disconnect_wallet: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to disconnect wallet'}), 500

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
        traceback.print_exc()
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
        user_vote = user_votes.get(current_user.id)
        
        # Update vote counts
        upvotes = project.get('upvotes', 0)
        downvotes = project.get('downvotes', 0)
        
        # Remove previous vote if exists
        if user_vote == 'up':
            upvotes = max(0, upvotes - 1)
        elif user_vote == 'down':
            downvotes = max(0, downvotes - 1)
        
        # Add new vote
        if 'votes' not in project:
            project['votes'] = {}
        if vote_type not in project['votes']:
            project['votes'][vote_type] = 0
        project['votes'][vote_type] += 1
        
        # Update project votes
        project_ref.update({
            'votes': project['votes']
        })
        
        # Update user's vote
        if vote_type:
            votes_ref.update({current_user.id: vote_type})
        else:
            votes_ref.child(current_user.id).delete()
        
        return jsonify({
            'success': True,
            'upvotes': upvotes,
            'downvotes': downvotes,
            'user_vote': vote_type
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
        print(f"\n=== Processing Donation for Project {project_id} ===")
        print(f"User ID: {current_user.id}")
        
        # Validate request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        amount = float(data.get('amount', 0))
        if amount <= 0:
            return jsonify({'error': 'Invalid donation amount'}), 400
            
        # Get user's wallet address
        user_doc = db.collection('users').document(current_user.id).get()
        if not user_doc.exists:
            return jsonify({'error': 'User not found'}), 404
            
        user_data = user_doc.to_dict()
        wallet_address = user_data.get('wallet_address')
        if not wallet_address:
            return jsonify({'error': 'Please connect your wallet first'}), 400
            
        # Validate wallet address format
        try:
            wallet_address = Web3.to_checksum_address(wallet_address)
        except ValueError:
            return jsonify({'error': 'Invalid wallet address format'}), 400
            
        # Get project details from Firestore first
        project_doc = db.collection('projects').document(project_id).get()
        blockchain_project_id = None
        
        if project_doc.exists:
            project_firestore_data = project_doc.to_dict()
            blockchain_project_id = project_firestore_data.get('blockchain_project_id')
            print(f"Found blockchain project ID in Firestore: {blockchain_project_id}")
            
        # If not in Firestore, try RTDB
        if blockchain_project_id is None:
            rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
            project_data = rtdb_ref.child(project_id).get()
            
            if not project_data:
                print(f"Project {project_id} not found in RTDB")
                return jsonify({'error': 'Project not found'}), 404
                
            if project_data.get('status') != 'active':
                return jsonify({'error': 'Project is not active'}), 400
                
            blockchain_project_id = project_data.get('blockchain_project_id')
            print(f"Found blockchain project ID in RTDB: {blockchain_project_id}")
            
        if not blockchain_project_id:
            return jsonify({'error': 'Project not properly initialized on blockchain'}), 400
            
        # Calculate platform fees (0.5%)
        platform_fees = float(amount) * 0.005
        total_amount = amount + platform_fees
        
        print(f"Amount: {amount} AVAX")
        print(f"Platform Fees: {platform_fees} AVAX")
        print(f"Total Amount: {total_amount} AVAX")
        print(f"Wallet Address: {wallet_address}")
        print(f"Using Blockchain Project ID: {blockchain_project_id}")
        
        # Prepare blockchain transaction
        try:
            transaction = contribute_to_project(
                project_id=blockchain_project_id,
                amount=total_amount,
                contributor_address=wallet_address
            )
            
            return jsonify({
                'success': True,
                'transaction': transaction,
                'amount': amount,
                'platform_fees': platform_fees,
                'total_amount': total_amount
            })
            
        except Exception as e:
            print(f"Error preparing blockchain transaction: {str(e)}")
            return jsonify({'error': f'Error preparing blockchain transaction: {str(e)}'}), 500
            
    except Exception as e:
        print(f"\nUnexpected error in donation: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print("Full traceback:")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@main.route('/transaction-history')
@login_required
def transaction_history():
    try:
        print("\n=== Loading Transaction History ===")
        print(f"User ID: {current_user.id}")
        
        # Get user's transactions
        contributions = db.collection('contributions').where('contributor_id', '==', current_user.id).stream()
        
        transactions = []
        for doc in contributions:
            tx = doc.to_dict()
            tx['id'] = doc.id
            
            # Convert timestamps
            created_at = tx.get('created_at')
            if isinstance(created_at, str):
                tx['timestamp'] = datetime.fromisoformat(created_at)
            else:
                tx['timestamp'] = created_at or datetime.now(timezone.utc)
                
            # Get project details
            project_doc = db.collection('projects').document(tx['project_id']).get()
            if project_doc.exists:
                project_data = project_doc.to_dict()
                tx['project_title'] = project_data.get('title', 'Unknown Project')
            else:
                tx['project_title'] = 'Unknown Project'
                
            transactions.append(tx)
            
        print(f"Found {len(transactions)} transactions")
        
        # Sort by timestamp
        transactions.sort(key=lambda x: x.get('timestamp', datetime.min), reverse=True)
        
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
            
        # Create proposal on blockchain first
        response = requests.post(
            url_for('blockchain.create_proposal', project_id=project_id, _external=True),
            json={'description': question}
        )
        
        if not response.ok:
            return jsonify({'error': response.json().get('error', 'Failed to create proposal')}), response.status_code
        
        # Continue with poll creation in Firebase
        poll_data = {
            'description': question,
            'options': options,
            'created_by': current_user.id,
            'created_at': datetime.utcnow(),
            'votes': {option: [] for option in options},
            'transaction_data': response.json().get('transaction_data')
        }
        
        db.collection('projects').document(project_id).collection('polls').add(poll_data)

        return jsonify(response.json())

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
        for option in poll.get('options', []):
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

@main.route('/api/donate/<project_id>/confirm', methods=['POST'])
@login_required
def confirm_donation(project_id):
    try:
        print(f"\n=== Confirming Donation for Project {project_id} ===")
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Get user data
        user_doc = db.collection('users').document(current_user.id).get()
        if not user_doc.exists:
            return jsonify({'error': 'User not found'}), 404
            
        user_data = user_doc.to_dict()
        
        # Record donation in Firebase
        donation_data = {
            'project_id': project_id,
            'contributor_id': current_user.id,
            'contributor_name': user_data.get('display_name', 'Anonymous'),
            'amount': data['amount'],
            'platform_fees': data['platform_fees'],
            'total_amount': data['total_amount'],
            'status': 'completed',
            'transaction_hash': data['transaction_hash'],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Add to contributions collection
        db.collection('contributions').add(donation_data)
        
        # Update project's funds in RTDB
        rtdb_ref = rtdb.reference('projects', app=get_app('rtdb'))
        project_data = rtdb_ref.child(project_id).get()
        
        if project_data:
            current_funds = float(project_data.get('funds_raised', 0))
            rtdb_ref.child(project_id).update({
                'funds_raised': current_funds + data['amount']
            })
            
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error confirming donation: {str(e)}")
        return jsonify({'error': str(e)}), 500
