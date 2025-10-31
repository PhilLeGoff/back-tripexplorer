from __future__ import annotations

from typing import Any, Dict

from rest_framework.exceptions import ValidationError, NotFound

from ..models import Attraction, Compilation, CompilationItem
from ..serializers import CompilationSerializer


class CompilationsController:
    @staticmethod
    def add_item(compilation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        attraction_id = payload.get('attraction_id') or payload.get('attraction')
        if not attraction_id:
            raise ValidationError({'error': 'attraction_id required'})

        try:
            compilation = Compilation.objects.get(id=compilation_id)
        except Compilation.DoesNotExist:
            raise NotFound('Compilation not found')

        try:
            attraction = Attraction.objects.get(id=attraction_id)
        except Attraction.DoesNotExist:
            raise NotFound('Attraction not found')

        # Prevent duplicates
        for item in compilation.items:
            if getattr(item.attraction, 'id', None) == getattr(attraction, 'id', None):
                raise ValidationError({'error': 'Attraction already in compilation'})

        new_item = CompilationItem(attraction=attraction, order_index=payload.get('order_index', 0))
        compilation.items.append(new_item)
        compilation.save()

        return CompilationSerializer(compilation).data

    @staticmethod
    def remove_item(compilation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        attraction_id = payload.get('attraction_id') or payload.get('attraction')
        if not attraction_id:
            raise ValidationError({'error': 'attraction_id required'})

        try:
            compilation = Compilation.objects.get(id=compilation_id)
        except Compilation.DoesNotExist:
            raise NotFound('Compilation not found')

        # Remove matching embedded items
        original_len = len(compilation.items)
        compilation.items = [it for it in compilation.items if str(getattr(it.attraction, 'id', None)) != str(attraction_id)]
        if len(compilation.items) != original_len:
            compilation.save()
            # Also delete the attraction document itself when removed
            try:
                att = Attraction.objects.get(id=attraction_id)
                att.delete()
            except Exception:
                pass

        return CompilationSerializer(compilation).data



