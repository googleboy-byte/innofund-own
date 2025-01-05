import pytest
from app import create_app, db
from app.models import User
from config import Config

@pytest.fixture(scope='session')
def app():
    """Create and configure a new app instance for each test."""
    app = create_app('testing')
    
    # Create a test context
    ctx = app.app_context()
    ctx.push()
    
    # Create test database and tables
    db.create_all()
    
    with app.test_client() as client:
        # Register test creator
        client.post('/auth/register', data={
            'email': Config.TEST_USER_EMAIL,
            'password': Config.TEST_USER_PASSWORD,
            'display_name': 'Test Creator'
        }, follow_redirects=True)
        
        # Connect wallet for creator
        client.post('/connect-wallet', data={
            'wallet_address': Config.TEST_USER_WALLET
        }, follow_redirects=True)
        
        # Register test donor
        client.post('/auth/register', data={
            'email': Config.TEST_DONOR_EMAIL,
            'password': Config.TEST_DONOR_PASSWORD,
            'display_name': 'Test Donor'
        }, follow_redirects=True)
        
        # Connect wallet for donor
        client.post('/connect-wallet', data={
            'wallet_address': Config.TEST_DONOR_WALLET
        }, follow_redirects=True)
    
    yield app
    
    # Cleanup: Delete test users from Firebase
    try:
        with app.test_client() as client:
            # Login as admin
            client.post('/auth/login', data={
                'email': Config.ADMIN_EMAIL,
                'password': Config.ADMIN_PASSWORD
            }, follow_redirects=True)
            
            # Delete test users
            client.post('/admin/delete-user', data={
                'email': Config.TEST_USER_EMAIL
            })
            client.post('/admin/delete-user', data={
                'email': Config.TEST_DONOR_EMAIL
            })
    except Exception as e:
        print(f"Error cleaning up test users: {str(e)}")
    
    db.session.remove()
    db.drop_all()
    ctx.pop()

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test CLI runner for the app."""
    return app.test_cli_runner() 