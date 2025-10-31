from __future__ import annotations

from typing import Dict, Any

from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, ValidationError

try:
    from rest_framework_simplejwt.tokens import RefreshToken
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    RefreshToken = None

from ..serializers import SignUpSerializer, SignInSerializer
from ..models import User


class AuthController:
    @staticmethod
    def ensure_jwt_available():
        if not JWT_AVAILABLE:
            raise ValidationError({'detail': 'JWT not available. Install djangorestframework-simplejwt.'})

    @staticmethod
    def signup(payload: Dict[str, Any]) -> Dict[str, Any]:
        AuthController.ensure_jwt_available()
        serializer = SignUpSerializer(data=payload)
        # Return serializer validation errors as a 400 with details
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        try:
            user = serializer.save()
        except Exception as e:
            # Handle common duplicate key / unique constraint errors gracefully
            msg = str(e).lower()
            if 'duplicate' in msg or 'unique' in msg or 'e11000' in msg:
                raise ValidationError({'email': ['A user with that email already exists.']})
            # Fallback
            raise

        if not user:
            raise ValidationError({'detail': 'Unable to create user'})
        refresh = RefreshToken.for_user(user)
        return {
            'user': SignUpSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'status': status.HTTP_201_CREATED,
        }

    @staticmethod
    def signin(payload: Dict[str, Any]) -> Dict[str, Any]:
        AuthController.ensure_jwt_available()

        # Basic presence validation to return helpful 400s
        email = payload.get('email') or payload.get('username')
        password = payload.get('password')
        if not email or not password:
            raise ValidationError({'detail': 'email and password are required'})

        # Normalize email for lookup
        email_lookup = email.strip().lower()

        # Use a safe lookup that returns None if not found
        try:
            user = User.objects(email__iexact=email_lookup).first()
        except Exception:
            user = None

        if not user:
            # keep error message generic
            raise AuthenticationFailed('Invalid credentials')

        if not user.check_password(password):
            raise AuthenticationFailed('Invalid credentials')

        refresh = RefreshToken.for_user(user)
        return {
            'user': SignUpSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'status': status.HTTP_200_OK,
        }

    @staticmethod
    def refresh(payload: Dict[str, Any]) -> Dict[str, Any]:
        AuthController.ensure_jwt_available()
        token = payload.get('refresh')
        if not token:
            raise ValidationError({'detail': 'refresh token required'})
        try:
            refresh = RefreshToken(token)
            return {'access': str(refresh.access_token), 'status': status.HTTP_200_OK}
        except Exception:
            raise AuthenticationFailed('invalid refresh token')


