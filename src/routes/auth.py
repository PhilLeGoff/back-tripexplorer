from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError, AuthenticationFailed
import logging
import traceback

try:
    from rest_framework_simplejwt.tokens import RefreshToken
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    RefreshToken = None

from ..controllers.auth_controller import AuthController

logger = logging.getLogger(__name__)


class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'], authentication_classes=[])
    def signup(self, request):
        if not JWT_AVAILABLE:
            return Response({'detail': 'JWT authentication not available. Install djangorestframework-simplejwt.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            logger.debug("Auth signup payload: %s", request.data)
            result = AuthController.signup(request.data)
            status_code = result.pop('status', status.HTTP_201_CREATED)
            return Response(result, status=status_code)
        except ValidationError as ve:
            return Response({'error': getattr(ve, 'detail', str(ve)), 'payload': request.data}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Signup error")
            return Response({'error': str(e), 'details': traceback.format_exc(), 'payload': request.data}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], authentication_classes=[])
    def signin(self, request):
        if not JWT_AVAILABLE:
            return Response({'detail': 'JWT authentication not available. Install djangorestframework-simplejwt.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            logger.debug("Auth signin payload: %s", request.data)
            result = AuthController.signin(request.data)
            status_code = result.pop('status', status.HTTP_200_OK)
            return Response(result, status=status_code)
        except ValidationError as ve:
            return Response({'error': getattr(ve, 'detail', str(ve)), 'payload': request.data}, status=status.HTTP_400_BAD_REQUEST)
        except AuthenticationFailed as af:
            return Response({'error': str(af), 'payload': request.data}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.exception("Signin error")
            return Response({'error': str(e), 'details': traceback.format_exc(), 'payload': request.data}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], authentication_classes=[])
    def refresh(self, request):
        if not JWT_AVAILABLE:
            return Response({'detail': 'JWT authentication not available. Install djangorestframework-simplejwt.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            logger.debug("Auth refresh payload: %s", request.data)
            result = AuthController.refresh(request.data)
            status_code = result.pop('status', status.HTTP_200_OK)
            return Response(result, status=status_code)
        except ValidationError as ve:
            return Response({'error': getattr(ve, 'detail', str(ve)), 'payload': request.data}, status=status.HTTP_400_BAD_REQUEST)
        except AuthenticationFailed as af:
            return Response({'error': str(af), 'payload': request.data}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.exception("Refresh error")
            return Response({'error': str(e), 'details': traceback.format_exc(), 'payload': request.data}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


