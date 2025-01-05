from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data.get('uid')
        self.email = user_data.get('email')
        self.display_name = user_data.get('display_name')
        self.photo_url = user_data.get('photo_url')
        self.last_login = user_data.get('last_login')
        self.wallet_address = user_data.get('wallet_address')
        self.wallet_connected_at = user_data.get('wallet_connected_at')

    def get_id(self):
        return str(self.id)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def has_wallet(self):
        return bool(self.wallet_address) 

class TestResult(db.Model):
    """Model for storing automated test results"""
    __tablename__ = 'test_results'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Float, nullable=False)  # Test duration in seconds
    success = db.Column(db.Boolean, nullable=False)
    total_tests = db.Column(db.Integer, nullable=False)
    failures = db.Column(db.Integer, nullable=False)
    errors = db.Column(db.Integer, nullable=False)
    output = db.Column(db.Text, nullable=True)  # Full test output
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'duration': self.duration,
            'success': self.success,
            'total_tests': self.total_tests,
            'failures': self.failures,
            'errors': self.errors,
            'output': self.output
        } 