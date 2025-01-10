from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime
from firebase_admin import firestore
from web3 import Web3
from .utils.web3_utils import (
    create_project_on_chain,
    contribute_to_project,
    create_project_proposal,
    get_project_details,
    get_platform_fees
)
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Initialize Firestore
db = firestore.client()
blockchain_bp = Blueprint('blockchain', __name__)

@blockchain_bp.route('/create-project-chain', methods=['POST'])
@login_required
def create_project_chain():
    """Create a project on the blockchain"""
    try:
        data = request.get_json()
        
        # Create project on blockchain and get ID
        project_id = create_project_on_chain(
            name=data['title'],
            description=data['description'],
            funding_goal=float(data['goal_amount']),
            deadline_days=30
        )
        
        # Convert project ID to integer
        project_id = int(project_id)
        print(f"Created blockchain project with ID: {project_id}")
        
        return jsonify({
            'success': True, 
            'project_id': project_id
        })
    except Exception as e:
        logger.error(f"Error creating project on chain: {str(e)}")
        return jsonify({'error': str(e)}), 500

@blockchain_bp.route('/contribute/<project_id>', methods=['POST'])
@login_required
def contribute(project_id):
    """Contribute to a project"""
    try:
        # Validate request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        amount = float(data.get('amount', 0))
        if amount <= 0:
            return jsonify({'error': 'Invalid contribution amount'}), 400
        
        # Get user's wallet address
        user_doc = db.collection('users').document(current_user.id).get()
        if not user_doc.exists:
            return jsonify({'error': 'User not found'}), 404
        
        user_data = user_doc.to_dict()
        wallet_address = user_data.get('wallet_address')
        if not wallet_address:
            return jsonify({'error': 'Please connect your wallet first'}), 400

        # Prepare transaction data
        try:
            transaction_data = contribute_to_project(project_id, amount, wallet_address)
            platform_fees = get_platform_fees(amount)
            transaction_data['platform_fees'] = platform_fees
        except Exception as e:
            logger.error(f"Error preparing transaction: {str(e)}")
            return jsonify({'error': 'Failed to prepare transaction'}), 500

        # Record contribution intent in Firebase
        try:
            contribution_data = {
                'project_id': project_id,
                'contributor_id': current_user.id,
                'amount': amount,
                'platform_fees': Web3.from_wei(platform_fees, 'ether'),
                'status': 'pending',
                'created_at': datetime.utcnow(),
                'transaction_data': transaction_data
            }
            
            contribution_ref = db.collection('contributions').add(contribution_data)
            logger.info(f"Contribution recorded with ID: {contribution_ref[1].id}")
        except Exception as e:
            logger.error(f"Error recording contribution: {str(e)}")
            return jsonify({'error': 'Failed to record contribution'}), 500

        return jsonify({
            'success': True,
            'transaction_data': transaction_data,
            'contribution_id': contribution_ref[1].id
        })

    except ValueError as e:
        logger.error(f"Value error in contribution: {str(e)}")
        return jsonify({'error': 'Invalid input data'}), 400
    except Exception as e:
        logger.error(f"Unexpected error in contribution: {str(e)}")
        return jsonify({'error': str(e)}), 500

@blockchain_bp.route('/create-proposal/<project_id>', methods=['POST'])
@login_required
def create_proposal(project_id):
    """Create a proposal for a project"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        description = data.get('description')
        if not description:
            return jsonify({'error': 'Description is required'}), 400
            
        # Get user's wallet address
        user_doc = db.collection('users').document(current_user.id).get()
        if not user_doc.exists:
            return jsonify({'error': 'User not found'}), 404
            
        user_data = user_doc.to_dict()
        creator_address = user_data.get('wallet_address')
        if not creator_address:
            return jsonify({'error': 'Please connect your wallet first'}), 400
            
        # Create proposal
        try:
            transaction_data = create_project_proposal(project_id, description, creator_address)
        except Exception as e:
            logger.error(f"Error creating proposal: {str(e)}")
            return jsonify({'error': 'Failed to create proposal'}), 500
            
        # Record proposal in Firebase
        try:
            proposal_data = {
                'project_id': project_id,
                'creator_id': current_user.id,
                'description': description,
                'status': 'pending',
                'created_at': datetime.utcnow(),
                'transaction_data': transaction_data
            }
            
            proposal_ref = db.collection('proposals').add(proposal_data)
            logger.info(f"Proposal recorded with ID: {proposal_ref[1].id}")
        except Exception as e:
            logger.error(f"Error recording proposal: {str(e)}")
            return jsonify({'error': 'Failed to record proposal'}), 500
            
        return jsonify({
            'success': True,
            'transaction_data': transaction_data,
            'proposal_id': proposal_ref[1].id
        })
        
    except ValueError as e:
        logger.error(f"Value error in proposal creation: {str(e)}")
        return jsonify({'error': 'Invalid input data'}), 400
    except Exception as e:
        logger.error(f"Unexpected error in proposal creation: {str(e)}")
        return jsonify({'error': str(e)}), 500
