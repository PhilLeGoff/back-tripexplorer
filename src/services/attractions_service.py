from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

from ..external_services import google_places_service
from ..models import Attraction


class AttractionsService:
    @staticmethod
    def _map_place_to_attraction(place: Dict[str, Any], country_hint: Optional[str] = None) -> Dict[str, Any]:
        """Map a Google Places result (or details result) to our API attraction shape without saving."""
        geometry = place.get('geometry', {}) or {}
        loc = geometry.get('location') or {}
        lat = loc.get('lat')
        lng = loc.get('lng')

        # Try to extract country and city from address components when present
        country = country_hint
        city = None
        for comp in place.get('address_components', []) or []:
            types = comp.get('types', [])
            if 'country' in types and not country:
                country = comp.get('long_name')
            if ('locality' in types or 'postal_town' in types) and not city:
                city = comp.get('long_name')

        # Fallbacks
        formatted_address = place.get('formatted_address') or place.get('vicinity') or ''
        name = place.get('name', '')

        mapped = {
            'place_id': place.get('place_id'),
            'name': name,
            'formatted_address': formatted_address,
            'country': country or '',
            'city': city or '',
            'category': (place.get('types') or [None])[0] or '',
            'types': place.get('types', []) or [],
            'rating': place.get('rating', 0),
            'user_ratings_total': place.get('user_ratings_total', 0),
            'price_level': place.get('price_level'),
            'location': {'lat': lat, 'lng': lng} if lat is not None and lng is not None else None,
            'description': '',
            'website': place.get('website', ''),
            'phone_number': place.get('formatted_phone_number', ''),
            'photo_reference': None,
            'photos_count': len(place.get('photos', []) or []),
            'opening_hours': place.get('opening_hours', {}),
            'reviews': place.get('reviews', []) or [],
            'likes': 0,
            'is_featured': False,
            'raw_data': place,
        }
        # If photos exist, set reference to first photo's photo_reference when available
        photos = place.get('photos') or []
        if photos:
            mapped['photo_reference'] = photos[0].get('photo_reference')

        return mapped

    @staticmethod
    def popular_by_country(country: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Return popular attractions for a country by querying Google Places (not MongoDB)."""
        # Use Google Places text search for tourist attractions in the country
        places = google_places_service.search_attractions_by_country(country, limit=limit)
        mapped = [AttractionsService._map_place_to_attraction(p, country_hint=country) for p in places]
        return mapped

    @staticmethod
    def search(params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search attractions via Google Places based on query params. Does not persist results."""
        # Build query and location
        query = (params.get('q') or '').strip()
        place_type = params.get('type')
        country = params.get('country')
        city = params.get('city')

        location = None
        radius = None
        try:
            lat = float(params.get('lat')) if params.get('lat') is not None else None
            lng = float(params.get('lng')) if params.get('lng') is not None else None
            if lat is not None and lng is not None:
                location = (lat, lng)
        except (TypeError, ValueError):
            location = None

        try:
            radius = int(params.get('radius_m')) if params.get('radius_m') is not None else None
        except (TypeError, ValueError):
            radius = None

        # If no query and no location, avoid calling text search with empty query which triggers INVALID_REQUEST
        if not query and not location:
            if country:
                # Fall back to country-wide attractions search
                places = google_places_service.search_attractions_by_country(country, limit=int(params.get('limit', 50)))
                mapped = [AttractionsService._map_place_to_attraction(p, country_hint=country) for p in places]
                return mapped
            else:
                # Nothing to search for
                import logging
                logging.getLogger(__name__).warning("Search called with empty query and no location/country; returning empty list")
                return []

        # If we have a lat/lng, use nearby search; otherwise, use places text search
        if location:
            lat, lng = location
            # googlemaps client expects (lat, lng) or string "lat,lng"
            loc_param = (lat, lng)
            results = google_places_service.search_places(query=query, location=loc_param, radius=radius, place_type=place_type)
        else:
            # Heuristic: if user typed a single token and no explicit city/country provided, treat the query as a country name.
            if query and not city and not country and (" " not in query.strip()):
                places = google_places_service.search_attractions_by_country(query.strip(), limit=int(params.get('limit', 50)))
                mapped = [AttractionsService._map_place_to_attraction(p, country_hint=query.strip()) for p in places]
                return mapped
            # If no coordinates, broaden text search, include city/country if provided
            text_query = query
            if city:
                text_query = f"{text_query} in {city}" if text_query else f"{city}"
            if country:
                text_query = f"{text_query} in {country}" if text_query else f"{country}"
            results = google_places_service.search_places(query=text_query, location=None, radius=None, place_type=place_type)

        mapped = [AttractionsService._map_place_to_attraction(p, country_hint=country) for p in results]
        return mapped

    @staticmethod
    def get_by_place_id(place_id: str):
        """Fetch place details from Google and map to API shape (no DB persistence)."""
        if not place_id:
            return None
        details = google_places_service.get_place_details(place_id)
        if not details:
            return None
        # Derive country for mapping when possible
        country = None
        for comp in details.get('address_components', []) or []:
            if 'country' in (comp.get('types') or []):
                country = comp.get('long_name')
                break
        return AttractionsService._map_place_to_attraction(details, country_hint=country)

    @staticmethod
    def similar_suggestions(place_id: str, limit: int = 10):
        """Compute similar suggestions using Google only (no DB).

        Strategy: fetch details to get geometry and types, then run a nearby/text search
        with the top type/category and return mapped results.
        """
        base = AttractionsService.get_by_place_id(place_id)
        if not base:
            return []
        # Prefer nearby search by coordinates when available
        mapped: list = []
        geometry = base.get('location')
        primary_type = (base.get('types') or [None])[0]
        if geometry and 'lat' in geometry and 'lng' in geometry:
            # Use keyword = name's first word or category to bias results
            keyword = base.get('name', '').split(' ')[0] if base.get('name') else None
            # google_places_service.search_places accepts location tuple and radius
            results = google_places_service.search_places(
                query=keyword or primary_type or 'tourist attraction',
                location=(geometry['lat'], geometry['lng']),
                radius=5000,
                place_type=primary_type or 'tourist_attraction',
            )
            mapped = [AttractionsService._map_place_to_attraction(r, country_hint=base.get('country')) for r in results[:limit]]
        else:
            results = google_places_service.search_places(
                query=f"{primary_type or base.get('name') or 'tourist attraction'} in {base.get('country','')}",
                location=None,
                radius=None,
                place_type=primary_type or 'tourist_attraction',
            )
            mapped = [AttractionsService._map_place_to_attraction(r, country_hint=base.get('country')) for r in results[:limit]]
        # Filter out the base place if present
        return [m for m in mapped if m.get('place_id') != place_id][:limit]

    @staticmethod
    def sync_from_google(country: str, limit: int = 20):
        # Keep existing sync behavior (admin/manual) — this persists to MongoDB
        places = google_places_service.search_attractions_by_country(country, limit)
        synced = 0
        for place in places:
            place_id = place.get('place_id')
            if not place_id:
                continue
            details = google_places_service.get_place_details(place_id)
            if not details:
                continue

            try:
                attraction = Attraction.objects.get(place_id=place_id)
                created = False
            except Exception:
                attraction = Attraction(place_id=place_id)
                created = True

            attraction.name = details.get('name', '')
            attraction.formatted_address = details.get('formatted_address', '')
            attraction.country = country
            attraction.rating = details.get('rating', 0)
            attraction.user_ratings_total = details.get('user_ratings_total', 0)
            attraction.price_level = details.get('price_level')
            geometry = details.get('geometry', {}) or {}
            loc = geometry.get('location') or {}
            lat = loc.get('lat')
            lng = loc.get('lng')
            if lat is not None and lng is not None:
                attraction.location = {'type': 'Point', 'coordinates': [lng, lat]}
            attraction.photos_count = len(details.get('photos', []) or [])
            attraction.opening_hours = details.get('opening_hours', {})
            attraction.website = details.get('website', '')
            attraction.phone_number = details.get('formatted_phone_number', '')
            attraction.types = details.get('types', []) or []
            attraction.raw_data = details
            attraction.save()

            if created:
                synced += 1
        return synced, len(places or [])

    @staticmethod
    def save_place(place_id: str):
        """Fetch place details from Google and persist as Attraction if not already present."""
        if not place_id:
            raise ValueError('place_id required')
        details = google_places_service.get_place_details(place_id)
        # If Google details are unavailable (e.g., missing API key), fall back to minimal upsert
        if not details:
            try:
                attraction = Attraction.objects.get(place_id=place_id)
                return attraction
            except Exception:
                # Create minimal record so it can be added to compilations
                try:
                    attraction = Attraction(place_id=place_id, name="", formatted_address="", country="", rating=0, user_ratings_total=0)
                    attraction.save()
                    return attraction
                except Exception as e:
                    raise ValueError('Unable to fetch or create place') from e

        try:
            attraction = Attraction.objects.get(place_id=place_id)
            created = False
        except Exception:
            attraction = Attraction(place_id=place_id)
            created = True

        # Map details into attraction
        attraction.name = details.get('name', '')
        attraction.formatted_address = details.get('formatted_address', '')
        # Try to derive country
        country = None
        for comp in details.get('address_components', []) or []:
            if 'country' in (comp.get('types') or []):
                country = comp.get('long_name')
                break
        attraction.country = country or attraction.country or ''
        geometry = details.get('geometry', {}) or {}
        loc = geometry.get('location') or {}
        lat = loc.get('lat')
        lng = loc.get('lng')
        if lat is not None and lng is not None:
            attraction.location = {'type': 'Point', 'coordinates': [lng, lat]}
        attraction.rating = details.get('rating', 0)
        attraction.user_ratings_total = details.get('user_ratings_total', 0)
        attraction.price_level = details.get('price_level')
        photos = details.get('photos', []) or []
        attraction.photos_count = len(photos)
        try:
            # Persist first photo reference for frontend image rendering
            if photos and isinstance(photos, list):
                first = photos[0] or {}
                ref = first.get('photo_reference') or ''
                if ref:
                    attraction.photo_reference = ref
        except Exception:
            pass
        attraction.opening_hours = details.get('opening_hours', {})
        attraction.website = details.get('website', '')
        attraction.phone_number = details.get('formatted_phone_number', '')
        attraction.types = details.get('types', []) or []
        attraction.raw_data = details
        attraction.save()

        return attraction

    @staticmethod
    def save_place_to_user_trip(user, place_id: str, compilation_id: str = None, compilation_name: str = None):
        """Persist a place and add it to a user's compilation (creates compilation if needed).

        Args:
            user: MongoEngine User document (request.user)
            place_id: Google Place ID
            compilation_id: optional existing Compilation id to add to
            compilation_name: optional name for creating a new compilation
        Returns:
            Compilation document after adding the item
        """
        from ..models import Compilation, CompilationItem

        if not user:
            raise ValueError('Authenticated user required')

        # Ensure attraction persisted
        attraction = AttractionsService.save_place(place_id)
        # Attach owner to attraction for auditing/ownership
        try:
            if getattr(attraction, 'owner', None) is None or str(getattr(attraction.owner, 'id', '')) != str(getattr(user, 'id', '')):
                attraction.owner = user
                attraction.save()
        except Exception:
            pass

        # Resolve or create compilation
        compilation = None
        if compilation_id:
            try:
                compilation = Compilation.objects.get(id=compilation_id)
            except Exception:
                compilation = None
            if compilation and compilation.owner and str(compilation.owner.id) != str(user.id):
                raise PermissionError('Not allowed to modify this compilation')

        if not compilation:
            # Try to find a default compilation for user
            default_name = compilation_name or f"My Trip ({user.selected_country or 'Any'})"
            compilation = Compilation.objects(owner=user, name=default_name).first()
            if not compilation:
                compilation = Compilation(name=default_name, owner=user, profile=(user.selected_profile or 'tourist'), country=(user.selected_country or ''))
                compilation.save()

        # Prevent duplicates
        for item in compilation.items:
            if getattr(item.attraction, 'id', None) and str(getattr(item.attraction, 'id')) == str(attraction.id):
                # Already present — return compilation as-is
                return compilation

        new_item = CompilationItem(attraction=attraction, order_index=len(compilation.items))
        compilation.items.append(new_item)
        compilation.save()

        return compilation


