from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .routes.attractions import AttractionViewSet, CompilationViewSet
from .routes.auth import AuthViewSet

router = DefaultRouter()
router.register(r'attractions', AttractionViewSet, basename='attraction')
router.register(r'compilations', CompilationViewSet, basename='compilation')
router.register(r'auth', AuthViewSet, basename='auth')

urlpatterns = [
    path('', include(router.urls)),
]



