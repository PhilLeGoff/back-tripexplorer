from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings
from rest_framework.exceptions import AuthenticationFailed

from .models import User as MongoUser


class MongoEngineJWTAuthentication(JWTAuthentication):
    """Authentication class that loads users from the MongoEngine User document.

    SimpleJWT's default JWTAuthentication expects Django ORM user lookups. This class
    overrides get_user to query the MongoEngine User collection instead.
    """

    def get_user(self, validated_token):
        # Token claim name that contains user identifier
        user_id_claim = api_settings.USER_ID_CLAIM
        user_id = validated_token.get(user_id_claim)
        if user_id is None:
            raise AuthenticationFailed('Token contained no recognizable user identification', code='no_user_id')

        # Try multiple lookup strategies to be resilient:
        # 1) direct lookup by id (works if token stores the ObjectId hex or ObjectId)
        # 2) with_id (mongoengine helper)
        # 3) fallback to email lookup if token stored email (unlikely but safe)
        try:
            # 1) Try standard query by id
            user = MongoUser.objects(id=user_id).first()
            if user:
                return user
        except Exception:
            user = None

        try:
            # 2) Try with_id helper (accepts ObjectId or its string)
            user = MongoUser.objects.with_id(user_id)
            if user:
                return user
        except Exception:
            user = None

        # 3) If the claim actually contains an email (or we stored email), try email lookup
        try:
            user = MongoUser.objects(email__iexact=str(user_id)).first()
            if user:
                return user
        except Exception:
            pass

        # If no user found, authentication must fail
        raise AuthenticationFailed('User not found', code='user_not_found')
