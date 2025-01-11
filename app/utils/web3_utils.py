from web3 import Web3
from eth_account import Account
import json
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging
from .warning_filters import ignore_web3_warnings, setup_warning_filters

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up warning filters
setup_warning_filters()

load_dotenv()

# Web3 setup with Avalanche C-Chain
AVALANCHE_TESTNET_URL = os.getenv('AVALANCHE_TESTNET_URL')
if not AVALANCHE_TESTNET_URL:
    raise ValueError("AVALANCHE_TESTNET_URL not found in environment variables")

w3 = Web3(Web3.HTTPProvider(AVALANCHE_TESTNET_URL))
# Add POA middleware for Avalanche
from web3.middleware import geth_poa_middleware
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

CHAIN_ID = int(os.getenv('CHAIN_ID', '43113'))  # Default to Avalanche Testnet

# Contract addresses (using existing values from .env)
FUNDING_CONTRACT_ADDRESS = os.getenv('FUNDING_CONTRACT_ADDRESS')
PROJECT_DAO_ADDRESS = os.getenv('PROJECT_DAO_ADDRESS')
REWARD_TOKEN_ADDRESS = os.getenv('REWARD_TOKEN_ADDRESS')

if not all([FUNDING_CONTRACT_ADDRESS, PROJECT_DAO_ADDRESS, REWARD_TOKEN_ADDRESS]):
    raise ValueError("One or more contract addresses not found in environment variables")

# Platform wallet (using existing private key)
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
if not PRIVATE_KEY:
    raise ValueError("PRIVATE_KEY not found in environment variables")

PLATFORM_WALLET = Account.from_key(PRIVATE_KEY)

@ignore_web3_warnings
def load_contract_abi(contract_name):
    """Load contract ABI from artifacts"""
    try:
        abi_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                            'web3', 'artifacts', 'contracts', f'{contract_name}.sol', 
                            f'{contract_name}.json')
        with open(abi_path) as f:
            contract_json = json.load(f)
            return contract_json['abi']
    except FileNotFoundError:
        logger.error(f"Contract ABI not found for {contract_name}")
        raise
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in contract ABI file for {contract_name}")
        raise

# Load contract ABIs
try:
    funding_contract = w3.eth.contract(
        address=Web3.to_checksum_address(FUNDING_CONTRACT_ADDRESS),
        abi=load_contract_abi('FundingContract')
    )
    logger.info("Funding contract loaded successfully")

    project_dao = w3.eth.contract(
        address=Web3.to_checksum_address(PROJECT_DAO_ADDRESS),
        abi=load_contract_abi('ProjectDAO')
    )
    logger.info("Project DAO contract loaded successfully")

    reward_token = w3.eth.contract(
        address=Web3.to_checksum_address(REWARD_TOKEN_ADDRESS),
        abi=load_contract_abi('RewardToken')
    )
    logger.info("Reward token contract loaded successfully")

except Exception as e:
    logger.error(f"Error loading contracts: {str(e)}")
    raise

@ignore_web3_warnings
def create_project_on_chain(name, description, funding_goal, deadline_days):
    """Create a project on the blockchain"""
    try:
        logger.info(f"Creating project: {name} with goal: {funding_goal} AVAX")
        
        # Convert funding goal to Wei
        funding_goal_wei = Web3.to_wei(funding_goal, 'ether')
        
        # Convert days to seconds for duration (using 12 hours instead of days)
        duration_seconds = int(deadline_days * 12 * 60 * 60)  # 12 hours worth of seconds
        
        # Get the function from contract
        function = funding_contract.functions.createProject(
            name,
            description,
            funding_goal_wei,
            duration_seconds
        )
        
        # Estimate gas
        gas_estimate = function.estimate_gas({'from': PLATFORM_WALLET.address})
        logger.info(f"Estimated gas: {gas_estimate}")
        
        # Build transaction
        transaction = function.build_transaction({
            'from': PLATFORM_WALLET.address,
            'gas': gas_estimate,
            'nonce': w3.eth.get_transaction_count(PLATFORM_WALLET.address),
            'chainId': CHAIN_ID
        })
        
        # Sign and send transaction
        signed_txn = w3.eth.account.sign_transaction(transaction, PLATFORM_WALLET.key)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        logger.info(f"Transaction sent: {tx_hash.hex()}")
        
        # Wait for receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        logger.info(f"Transaction mined in block: {receipt['blockNumber']}")
        
        # Get project ID from event
        project_created_event = funding_contract.events.ProjectCreated().process_receipt(receipt)
        project_id = project_created_event[0]['args']['projectId']
        
        logger.info(f"Project created with ID: {project_id}")
        return project_id

    except Exception as e:
        logger.error(f"Error creating project on chain: {str(e)}")
        raise

@ignore_web3_warnings
def contribute_to_project(project_id, amount, contributor_address):
    """Contribute to a project"""
    try:
        # Convert to checksum address
        contributor_address = Web3.to_checksum_address(contributor_address)
        
        logger.info(f"Preparing contribution: Project ID: {project_id}, Amount: {amount} AVAX, From: {contributor_address}")
        
        # Ensure project_id is an integer
        project_id = int(project_id)
        
        # Verify project exists and is active
        project = funding_contract.functions.projects(project_id).call()
        if not project[7]:  # exists flag
            raise ValueError(f"Project {project_id} does not exist")
        if project[6]:  # funded flag
            raise ValueError(f"Project {project_id} is already fully funded")
            
        # Convert amount to Wei
        amount_wei = Web3.to_wei(amount, 'ether')
        
        # Get the contribute function
        function = funding_contract.functions.contribute(project_id)
        
        # Convert contract address to checksum
        funding_contract_address = Web3.to_checksum_address(FUNDING_CONTRACT_ADDRESS)
        
        # Estimate gas with the actual value being sent
        try:
            gas_estimate = function.estimate_gas({
                'from': contributor_address,
                'value': amount_wei
            })
            # Add 20% buffer to gas estimate for safety
            gas_estimate = int(gas_estimate * 1.2)
        except Exception as e:
            logger.error(f"Error estimating gas: {str(e)}")
            # Use a safe default if estimation fails
            gas_estimate = 300000
        
        # Build transaction
        transaction = {
            'to': funding_contract_address,
            'from': contributor_address,
            'value': amount_wei,
            'gas': gas_estimate,
            'nonce': w3.eth.get_transaction_count(contributor_address),
            'chainId': CHAIN_ID,
            'data': function._encode_transaction_data()
        }
        
        logger.info(f"Contribution transaction prepared for project {project_id}")
        logger.info(f"Transaction details: Gas: {gas_estimate}, Value: {amount_wei} wei")
        logger.info(f"Project creator address: {project[2]}")  # Log creator address
        logger.info(f"Platform fee address: {PLATFORM_WALLET.address}")  # Log platform fee address
        return transaction

    except ValueError as e:
        logger.error(f"Value error in contribution: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error preparing contribution transaction: {str(e)}")
        raise

@ignore_web3_warnings
def create_project_proposal(project_id, description, creator_address):
    """Create a proposal for a project"""
    try:
        # Convert project_id to integer
        project_id = int(project_id)
        
        # Create the proposal call data for the funding contract
        proposal_data = funding_contract.encodeABI(
            fn_name='createProjectProposal',
            args=[project_id, description]
        )
        
        # Get the propose function from DAO contract
        function = project_dao.functions.propose(
            [FUNDING_CONTRACT_ADDRESS],  # targets
            [0],  # values
            [proposal_data],  # calldatas
            description  # description
        )
        
        # Estimate gas
        gas_estimate = function.estimate_gas({'from': creator_address})
        logger.info(f"Estimated gas for proposal: {gas_estimate}")
        
        # Build transaction
        transaction = function.build_transaction({
            'from': creator_address,
            'gas': gas_estimate,
            'nonce': w3.eth.get_transaction_count(creator_address),
            'chainId': CHAIN_ID
        })
        
        return transaction

    except ValueError as e:
        logger.error(f"Error creating proposal: Invalid project ID or description - {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error creating proposal: {str(e)}")
        raise

@ignore_web3_warnings
def get_project_details(project_id):
    """Get project details from the blockchain"""
    try:
        project_id = int(project_id)
        project = funding_contract.functions.projects(project_id).call()
        
        return {
            'name': project[0],
            'description': project[1],
            'creator': project[2],
            'funding_goal': Web3.from_wei(project[3], 'ether'),
            'current_funding': Web3.from_wei(project[4], 'ether'),
            'deadline': datetime.fromtimestamp(project[5]),
            'funded': project[6],
            'exists': project[7]
        }
    except Exception as e:
        logger.error(f"Error getting project details: {str(e)}")
        raise

@ignore_web3_warnings
def get_platform_fees(amount):
    """Calculate platform fees for a given donation amount"""
    try:
        # Convert amount to Wei for precise calculation
        amount_wei = Web3.to_wei(amount, 'ether')
        
        # Calculate fees (0.5% of amount)
        fee_percentage = 0.005
        fees_wei = int(amount_wei * fee_percentage)
        
        return fees_wei
        
    except Exception as e:
        logger.error(f"Error calculating platform fees: {str(e)}")
        raise
