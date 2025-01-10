from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(UserMixin):
    def __init__(self, uid, email, display_name=None, photo_url=None):
        self.id = uid  # Required by Flask-Login
        self.uid = uid
        self.email = email
        self.display_name = display_name or email.split('@')[0]
        self.photo_url = photo_url
        self._is_authenticated = True
        self._is_active = True
        self._is_anonymous = False

    @property
    def is_authenticated(self):
        return self._is_authenticated
    
    @property
    def is_active(self):
        return self._is_active
    
    @property
    def is_anonymous(self):
        return self._is_anonymous

    def get_id(self):
        return str(self.id)

    def to_dict(self):
        return {
            'uid': self.uid,
            'email': self.email,
            'display_name': self.display_name,
            'photo_url': self.photo_url
        }

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