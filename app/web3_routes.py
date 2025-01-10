from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from .models import db, Project, Proposal, Vote
from datetime import datetime
from web3 import Web3

# Initialize Web3 instance
w3 = Web3(Web3.HTTPProvider('https://api.avax-test.network/ext/bc/C/rpc'))
web3_bp = Blueprint('web3', __name__)

@web3_bp.route('/update_wallet', methods=['POST'])
@login_required
def update_wallet():
    data = request.get_json()
    wallet_address = data.get('wallet_address')
    
    if not wallet_address:
        return jsonify({'error': 'No wallet address provided'}), 400
        
    current_user.wallet_address = wallet_address
    db.session.commit()
    
    return jsonify({'success': True})

@web3_bp.route('/fund_project/<int:project_id>', methods=['POST'])
@login_required
def fund_project(project_id):
    if not current_user.wallet_address:
        return jsonify({'error': 'Please connect your wallet first'}), 400
        
    data = request.get_json()
    amount = data.get('amount')
    
    if not amount:
        return jsonify({'error': 'No amount provided'}), 400

    # Convert AVAX to Wei
    amount_wei = w3.to_wei(amount, 'ether')
        
    project = Project.query.get_or_404(project_id)
    
    # Update project funding in database
    project.current_funding += float(amount)
    if project.current_funding >= project.funding_goal:
        project.funded = True
    
    db.session.commit()
    
    return jsonify({'success': True})

@web3_bp.route('/vote/<int:proposal_id>', methods=['POST'])
@login_required
def vote_proposal(proposal_id):
    if not current_user.wallet_address:
        return jsonify({'error': 'Please connect your wallet first'}), 400
        
    data = request.get_json()
    support = data.get('support')
    
    if support is None:
        return jsonify({'error': 'No vote support provided'}), 400
        
    proposal = Proposal.query.get_or_404(proposal_id)
    
    # Check if user has already voted
    existing_vote = Vote.query.filter_by(
        proposal_id=proposal_id,
        voter_address=current_user.wallet_address
    ).first()
    
    if existing_vote:
        return jsonify({'error': 'You have already voted on this proposal'}), 400
    
    # Create new vote
    vote = Vote(
        proposal_id=proposal_id,
        voter_address=current_user.wallet_address,
        support=support,
        timestamp=datetime.utcnow()
    )
    
    db.session.add(vote)
    db.session.commit()
    
    return jsonify({'success': True})
