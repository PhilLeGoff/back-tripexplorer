from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import User


class ProfileViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def select(self, request):
        user = request.user
        data = request.data or {}
        profile = data.get('profile')
        country = data.get('country')
        city = data.get('city')
        updated = False
        if profile and profile in ('local', 'tourist', 'pro'):
            user.selected_profile = profile
            updated = True
        if country:
            user.selected_country = country
            updated = True
        if city is not None:
            user.selected_city = city
            updated = True
        if updated:
            user.save()
        return Response({
            'profile': user.selected_profile,
            'country': user.selected_country,
            'city': user.selected_city
        })

    @action(detail=False, methods=['get'])
    def me(self, request):
        user = request.user
        return Response({
            'profile': user.selected_profile,
            'country': user.selected_country,
            'city': user.selected_city
        })
