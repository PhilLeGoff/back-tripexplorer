import mongoengine as me
from datetime import datetime


class User(me.Document):
    """Simple User document to replace Django auth user.
    Passwords are stored using PBKDF2-SHA256 with a salt.
    """
    email = me.EmailField(required=True, unique=True)
    first_name = me.StringField(default='')
    last_name = me.StringField(default='')
    password = me.StringField(required=True)  # stored as: pbkdf2_sha256$iterations$salt$hash
    is_active = me.BooleanField(default=True)
    created_at = me.DateTimeField(default=datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.utcnow)

    # Preferences persisted per user
    selected_profile = me.StringField(choices=('local', 'tourist', 'pro'), default='tourist')
    selected_country = me.StringField(default='France')

    meta = {
        'indexes': [
            'email'
        ]
    }

    def set_password(self, raw_password: str) -> None:
        import os
        import hashlib
        import binascii

        iterations = 100_000
        salt = binascii.hexlify(os.urandom(16)).decode()
        dk = hashlib.pbkdf2_hmac('sha256', raw_password.encode('utf-8'), salt.encode('utf-8'), iterations)
        hash_hex = binascii.hexlify(dk).decode()
        self.password = f"pbkdf2_sha256${iterations}${salt}${hash_hex}"

    def check_password(self, raw_password: str) -> bool:
        import hashlib
        import binascii

        try:
            algorithm, iterations, salt, hash_hex = self.password.split('$')
            iterations = int(iterations)
        except Exception:
            return False
        dk = hashlib.pbkdf2_hmac('sha256', raw_password.encode('utf-8'), salt.encode('utf-8'), iterations)
        return binascii.hexlify(dk).decode() == hash_hex

    @property
    def pk(self):
        # Provide compatibility with libraries expecting a .pk attribute
        return getattr(self, 'id', None)

    @property
    def is_authenticated(self):
        # For DRF/permission compatibility
        return True

    def __str__(self) -> str:
        return self.email


