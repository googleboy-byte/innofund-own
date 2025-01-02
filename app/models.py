from flask_login import UserMixin

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