from __future__ import annotations

from typing import Optional, Tuple

import mongoengine as me

from ..models import Attraction


class AttractionRepository:
    @staticmethod
    def base_queryset():
        return Attraction.objects.order_by('-likes', '-rating', '-user_ratings_total')

    @classmethod
    def get_popular_by_country(cls, country: str, limit: int = 20):
        qs = cls.base_queryset().filter(country__icontains=country)
        featured = qs.filter(is_featured=True)
        if featured.count() > 0:
            return featured.limit(limit)
        return qs.limit(limit)

    @classmethod
    def search(
        cls,
        *,
        text: str = '',
        country: Optional[str] = None,
        city: Optional[str] = None,
        category: Optional[str] = None,
        min_rating: Optional[float] = None,
        min_reviews: Optional[int] = None,
        min_photos: Optional[int] = None,
        price_level: Optional[int] = None,
        place_type: Optional[str] = None,
        location: Optional[Tuple[float, float]] = None,
        radius_m: Optional[int] = None,
        limit: int = 50,
    ):
        qs = cls.base_queryset()

        if text:
            q = (
                me.Q(name__icontains=text)
                | me.Q(formatted_address__icontains=text)
                | me.Q(category__icontains=text)
            )
            qs = qs.filter(q)

        if country:
            qs = qs.filter(country__icontains=country)
        if city:
            qs = qs.filter(city__icontains=city)
        if category:
            qs = qs.filter(category__icontains=category)
        if min_rating is not None:
            qs = qs.filter(rating__gte=float(min_rating))
        if min_reviews is not None:
            qs = qs.filter(user_ratings_total__gte=int(min_reviews))
        if min_photos is not None:
            qs = qs.filter(photos_count__gte=int(min_photos))
        if price_level is not None:
            qs = qs.filter(price_level=int(price_level))
        if place_type:
            qs = qs.filter(types__contains=place_type)

        if location and radius_m:
            lat, lng = location
            # MongoEngine expects point as [lng, lat]
            try:
                qs = qs.filter(location__near=[lng, lat], location__max_distance=radius_m)
            except Exception:
                # Fallback to using .near if filter style above not supported
                qs = qs.near('location', [lng, lat], max_distance=radius_m)

        return qs.limit(limit)

    @classmethod
    def get_similar_nearby(cls, attraction: Attraction, limit: int = 10):
        qs = cls.base_queryset().filter(id__ne=attraction.id)
        if attraction.city:
            qs = qs.filter(city__iexact=attraction.city)
        if attraction.category:
            qs = qs.filter(category__icontains=attraction.category)

        # If attraction has a location, use geospatial ordering
        loc = getattr(attraction, 'location', None)
        if loc and isinstance(loc, dict):
            coords = loc.get('coordinates') or []
            if len(coords) >= 2:
                try:
                    qs = qs.near('location', coords, max_distance=5000)
                except Exception:
                    # ignore geo ordering if it fails
                    pass
        return qs.limit(limit)


