import unittest
from flask import url_for
from app import create_app, db
from app.models import User, Project
from decimal import Decimal
from config import Config

class TestProjectFunctionality(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_project_creation(self):
        """Test project creation functionality"""
        with self.client as c:
            # Login
            c.post('/auth/login', data={
                'email': Config.TEST_USER_EMAIL,
                'password': Config.TEST_USER_PASSWORD
            }, follow_redirects=True)
            
            # Create project
            response = c.post('/create-project', data={
                'title': 'Test Project',
                'description': 'Test Description',
                'goal_amount': '10.0',
                'team_members': '[]'
            }, follow_redirects=True)
            
            self.assertEqual(response.status_code, 200)
            
            # Verify project creation
            project = Project.query.filter_by(title='Test Project').first()
            self.assertIsNotNone(project)
            self.assertEqual(project.description, 'Test Description')
            self.assertEqual(project.goal_amount, Decimal('10.0'))

    def test_project_deactivation(self):
        """Test project deactivation functionality"""
        with self.client as c:
            # Login
            c.post('/auth/login', data={
                'email': Config.TEST_USER_EMAIL,
                'password': Config.TEST_USER_PASSWORD
            }, follow_redirects=True)
            
            # Create a test project
            response = c.post('/create-project', data={
                'title': 'Test Project',
                'description': 'Test Description',
                'goal_amount': '10.0',
                'team_members': '[]'
            }, follow_redirects=True)
            
            project = Project.query.filter_by(title='Test Project').first()
            
            # Deactivate project
            response = c.post(f'/deactivate-project/{project.id}',
                            headers={'X-Requested-With': 'XMLHttpRequest'})
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data['success'])
            
            # Verify project status
            project = Project.query.get(project.id)
            self.assertEqual(project.status, 'inactive')

    def test_project_listing(self):
        """Test project listing functionality"""
        with self.client as c:
            # Login
            c.post('/auth/login', data={
                'email': Config.TEST_USER_EMAIL,
                'password': Config.TEST_USER_PASSWORD
            }, follow_redirects=True)
            
            # Create multiple test projects
            for i in range(3):
                c.post('/create-project', data={
                    'title': f'Test Project {i}',
                    'description': f'Test Description {i}',
                    'goal_amount': '10.0',
                    'team_members': '[]'
                }, follow_redirects=True)
            
            # Test dashboard listing
            response = c.get('/dashboard')
            self.assertEqual(response.status_code, 200)
            for i in range(3):
                self.assertIn(f'Test Project {i}'.encode(), response.data)
            
            # Test API listing
            response = c.get('/api/projects?page=1')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(len(data['projects']), 3)

    def test_project_view(self):
        """Test project view functionality"""
        with self.client as c:
            # Login
            c.post('/auth/login', data={
                'email': Config.TEST_USER_EMAIL,
                'password': Config.TEST_USER_PASSWORD
            }, follow_redirects=True)
            
            # Create a test project
            response = c.post('/create-project', data={
                'title': 'Test Project',
                'description': 'Test Description',
                'goal_amount': '10.0',
                'team_members': '[]'
            }, follow_redirects=True)
            
            project = Project.query.filter_by(title='Test Project').first()
            
            # View project
            response = c.get(f'/project/{project.id}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Test Project', response.data)
            self.assertIn(b'Test Description', response.data)
            self.assertIn(b'10.0 ETH', response.data)

if __name__ == '__main__':
    unittest.main() 