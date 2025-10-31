from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..services.attractions_service import AttractionsService


class AttractionsController:
    @staticmethod
    def popular_by_country(country: str, limit: int = 20):
        return AttractionsService.popular_by_country(country, limit)

    @staticmethod
    def search(params: Dict[str, Any]):
        return AttractionsService.search(params)

    @staticmethod
    def get_by_place_id(place_id: str):
        return AttractionsService.get_by_place_id(place_id)

    @staticmethod
    def similar_suggestions(place_id: str, limit: int = 10):
        return AttractionsService.similar_suggestions(place_id, limit)

    @staticmethod
    def sync_from_google(country: str, limit: int = 20):
        return AttractionsService.sync_from_google(country, limit)

    @staticmethod
    def save_place(place_id: str):
        return AttractionsService.save_place(place_id)

    @staticmethod
    def save_place_to_user(user, place_id: str, compilation_id: str = None, compilation_name: str = None):
        return AttractionsService.save_place_to_user_trip(user, place_id, compilation_id=compilation_id, compilation_name=compilation_name)


