import unittest
from flask import url_for
from app import create_app, db
from app.models import User, Project, Transaction
from decimal import Decimal
from config import Config

class TestDonationFunctionality(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        
        # Create test project
        self.project = Project(
            title='Test Project',
            description='Test Description',
            goal_amount=10.0,
            created_by=1,  # Will be updated after user creation
            status='active'
        )
        
        db.session.add(self.project)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_donate_modal_display(self):
        """Test if donation modal is displayed correctly"""
        with self.client as c:
            # Login as donor
            c.post('/auth/login', data={
                'email': Config.TEST_DONOR_EMAIL,
                'password': Config.TEST_DONOR_PASSWORD
            }, follow_redirects=True)
            
            # Get project page
            response = c.get(f'/project/{self.project.id}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'donate-btn', response.data)
            self.assertIn(b'donate-modal', response.data)

    def test_donation_submission(self):
        """Test if donation submission works correctly"""
        with self.client as c:
            # Login as donor
            c.post('/auth/login', data={
                'email': Config.TEST_DONOR_EMAIL,
                'password': Config.TEST_DONOR_PASSWORD
            }, follow_redirects=True)
            
            # Submit donation
            response = c.post(f'/update-project-funds/{self.project.id}', 
                            json={'amount': 1.0},
                            headers={'X-Requested-With': 'XMLHttpRequest'})
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data['success'])
            
            # Verify database update
            project = Project.query.get(self.project.id)
            self.assertEqual(project.funds_raised, Decimal('1.0'))
            
            # Verify transaction creation
            transaction = Transaction.query.filter_by(project_id=self.project.id).first()
            self.assertIsNotNone(transaction)
            self.assertEqual(transaction.amount, Decimal('1.0'))

    def test_donation_validation(self):
        """Test donation amount validation"""
        with self.client as c:
            # Login as donor
            c.post('/auth/login', data={
                'email': Config.TEST_DONOR_EMAIL,
                'password': Config.TEST_DONOR_PASSWORD
            }, follow_redirects=True)
            
            # Test negative amount
            response = c.post(f'/update-project-funds/{self.project.id}', 
                            json={'amount': -1.0},
                            headers={'X-Requested-With': 'XMLHttpRequest'})
            self.assertEqual(response.status_code, 400)
            
            # Test zero amount
            response = c.post(f'/update-project-funds/{self.project.id}', 
                            json={'amount': 0.0},
                            headers={'X-Requested-With': 'XMLHttpRequest'})
            self.assertEqual(response.status_code, 400)
            
            # Test excessive amount
            response = c.post(f'/update-project-funds/{self.project.id}', 
                            json={'amount': 1000000.0},
                            headers={'X-Requested-With': 'XMLHttpRequest'})
            self.assertEqual(response.status_code, 400)

    def test_creator_cannot_donate(self):
        """Test that project creators cannot donate to their own projects"""
        with self.client as c:
            # Login as creator
            c.post('/auth/login', data={
                'email': Config.TEST_USER_EMAIL,
                'password': Config.TEST_USER_PASSWORD
            }, follow_redirects=True)
            
            # Try to donate to own project
            response = c.post(f'/update-project-funds/{self.project.id}', 
                            json={'amount': 1.0},
                            headers={'X-Requested-With': 'XMLHttpRequest'})
            
            self.assertEqual(response.status_code, 403)

if __name__ == '__main__':
    unittest.main() 