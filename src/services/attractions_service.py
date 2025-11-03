from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List
import hashlib
import json

from ..external_services import google_places_service
from ..models import Attraction
from ..repositories.attraction_repository import AttractionRepository


# Simple in-memory cache for search results (valid for 5 minutes)
_search_cache: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}
_CACHE_TTL = 5 * 60  # 5 minutes

class AttractionsService:
    @staticmethod
    def _filter_opening_hours(opening_hours: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Filter opening hours to only include open_now and weekday_text."""
        if not opening_hours or not isinstance(opening_hours, dict):
            return {}
        
        filtered = {}
        
        if 'open_now' in opening_hours:
            filtered['open_now'] = opening_hours['open_now']
        
        if 'weekday_text' in opening_hours:
            filtered['weekday_text'] = opening_hours['weekday_text']
        
        return filtered
    
    @staticmethod
    def _map_place_to_attraction(place: Dict[str, Any], country_hint: Optional[str] = None) -> Dict[str, Any]:
        """Map a Google Places result (or details result) to our API attraction shape without saving."""
        geometry = place.get('geometry', {}) or {}
        loc = geometry.get('location') or {}
        lat = loc.get('lat')
        lng = loc.get('lng')

        country = country_hint
        city = None
        for comp in place.get('address_components', []) or []:
            types = comp.get('types', [])
            if 'country' in types and not country:
                country = comp.get('long_name')
            if ('locality' in types or 'postal_town' in types) and not city:
                city = comp.get('long_name')

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
            'opening_hours': AttractionsService._filter_opening_hours(place.get('opening_hours')),
            'reviews': place.get('reviews', []) or [],
            'likes': 0,
            'is_featured': False,
            'raw_data': place,
        }
        photos = place.get('photos') or []
        if photos:
            mapped['photo_reference'] = photos[0].get('photo_reference')

        return mapped

    @staticmethod
    def popular_by_country(country: str, limit: int = 20, profile: str = 'tourist', city: str = None) -> List[Dict[str, Any]]:
        """Return popular attractions for a country (and optionally city) by querying Google Places (not MongoDB).
        
        Profile-specific adaptations:
        - tourist: prioritize tourist_attraction types, landmarks, museums
        - local: prioritize restaurants, cafes, parks, local favorites
        - pro: prioritize business centers, conference venues, corporate amenities
        """
        # Use Google Places text search for attractions in the country/city (profile-aware)
        places = google_places_service.search_attractions_by_country(country, limit=limit * 2, profile=profile, city=city)
        mapped = [AttractionsService._map_place_to_attraction(p, country_hint=country) for p in places]
        
        if profile == 'tourist':
            tourist_types = ['tourist_attraction', 'point_of_interest', 'museum', 'art_gallery', 'church', 'park', 'zoo', 'amusement_park']
            mapped.sort(key=lambda x: (
                -sum(1 for t in (x.get('types') or []) if any(tt in t.lower() for tt in tourist_types)),
                -(x.get('rating', 0)),
                -(x.get('user_ratings_total', 0))
            ))
        elif profile == 'local':
            local_types = ['restaurant', 'cafe', 'bar', 'park', 'gym', 'store', 'shopping_mall', 'supermarket', 'library', 'movie_theater']
            mapped.sort(key=lambda x: (
                -sum(1 for t in (x.get('types') or []) if any(lt in t.lower() for lt in local_types)),
                -(x.get('rating', 0)),
                -(x.get('user_ratings_total', 0))
            ))
        elif profile == 'pro':
            pro_types = ['lodging', 'establishment', 'point_of_interest', 'train_station', 'airport', 'gas_station', 'bank', 'atm']
            mapped.sort(key=lambda x: (
                -sum(1 for t in (x.get('types') or []) if any(pt in t.lower() for pt in pro_types)),
                -(x.get('rating', 0)),
                -(x.get('user_ratings_total', 0))
            ))
        
        return mapped[:limit]

    @staticmethod
    def _generate_cache_key(params: Dict[str, Any]) -> str:
        """Generate a cache key from search parameters."""
        sorted_params = json.dumps(params, sort_keys=True)
        return hashlib.md5(sorted_params.encode()).hexdigest()
    
    @staticmethod
    def search(params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search attractions via Google Places based on query params. Does not persist results.
        
        Profile-based adaptations:
        - tourist: prioritize tourist attractions, landmarks, high ratings
        - local: prioritize local spots, restaurants, cafes, parks
        - pro: prioritize business amenities, hotels, transportation hubs
        """
        import time
        
        # Check cache first
        cache_key = AttractionsService._generate_cache_key(params)
        current_time = time.time()
        
        if cache_key in _search_cache:
            cached_results, cache_time = _search_cache[cache_key]
            if current_time - cache_time < _CACHE_TTL:
                logger = __import__('logging').getLogger(__name__)
                logger.info(f"[Search] Using cached results for key={cache_key[:8]}...")
                return cached_results
        
        profile = params.get('profile', 'tourist')
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

        category = params.get('category')
        min_rating = params.get('min_rating') or params.get('minRating')
        price_level = params.get('price_level') or params.get('maxPrice')
        
        import logging
        logger = logging.getLogger(__name__)
        has_category = bool(category and category.strip())
        has_min_rating = False
        if min_rating:
            try:
                if isinstance(min_rating, (int, float)):
                    has_min_rating = min_rating > 0
                elif isinstance(min_rating, str) and min_rating.strip():
                    has_min_rating = float(min_rating.strip()) > 0
            except (ValueError, TypeError):
                pass
        
        has_price_level = False
        if price_level:
            try:
                if isinstance(price_level, int):
                    has_price_level = price_level < 200
                elif isinstance(price_level, str) and price_level.strip():
                    has_price_level = int(price_level.strip()) < 200
            except (ValueError, TypeError):
                pass
        
        has_filters = has_category or has_min_rating or has_price_level

        requested_types = []
        place_type = None
        if category and category.strip():
            requested_types = [c.strip() for c in category.split(',') if c.strip()]
            if requested_types:
                place_type = requested_types[0]
        if not place_type and not has_filters:
            if profile == 'tourist':
                place_type = 'tourist_attraction'
            elif profile == 'local':
                place_type = None
            elif profile == 'pro':
                place_type = None

        if not query and not location:
            if country:
                if has_filters:
                    if requested_types and place_type:
                        type_name = requested_types[0].replace('_', ' ')
                        if city:
                            text_query = f"{type_name} in {city}, {country}" if country else f"{type_name} in {city}"
                        elif country:
                            text_query = f"{type_name} in {country}"
                        else:
                            text_query = type_name
                        logger.info(f"[Search] Filters applied with no query - using query='{text_query}' and place_type='{place_type}'")
                        results = google_places_service.search_places(query=text_query, location=None, radius=None, place_type=place_type)
                        mapped = [AttractionsService._map_place_to_attraction(p, country_hint=country) for p in results]
                        logger.info(f"[Search] Got {len(mapped)} results after filter search with place_type={place_type}")
                        # Continue to apply filters and ranking below
                    else:
                        # No category filter, but other filters present - fall back to profile-based search
                        mapped = AttractionsService.popular_by_country(country, limit=int(params.get('limit', 50)), profile=profile, city=city)
                        # Cache results before returning
                        _search_cache[cache_key] = (mapped, current_time)
                        return mapped
                else:
                    # Fall back to country-wide or city-wide attractions search (profile-aware)
                    mapped = AttractionsService.popular_by_country(country, limit=int(params.get('limit', 50)), profile=profile, city=city)
                    # Cache results before returning
                    _search_cache[cache_key] = (mapped, current_time)
                    return mapped
            else:
                # Nothing to search for
                import logging
                logging.getLogger(__name__).warning("Search called with empty query and no location/country; returning empty list")
                empty_result: List[Dict[str, Any]] = []
                _search_cache[cache_key] = (empty_result, current_time)
                return empty_result
        
        if 'mapped' not in locals():
            if location:
                lat, lng = location
                loc_param = (lat, lng)
                search_query = query if query else None
                if not has_filters and query:
                    if profile == 'local':
                        search_query = f"{query} local favorites"
                    elif profile == 'pro':
                        search_query = f"{query} business"
                    else:
                        search_query = query
                db_results = []
                try:
                    repo_results = AttractionRepository.search(
                        text=search_query or '',
                        location=location,
                        radius_m=radius or 5000,
                        place_type=place_type,
                        limit=50
                    )
                    db_results = list(repo_results)
                    logger.info(f"[Search] Found {len(db_results)} results in MongoDB")
                except Exception as e:
                    logger.debug(f"[Search] MongoDB search error: {e}")
                
                google_results = google_places_service.search_places(query=search_query, location=loc_param, radius=radius, place_type=place_type)
                
                google_place_ids = {r.get('place_id') for r in google_results if r.get('place_id')}
                results = google_results
                
                for db_attraction in db_results[:10]:
                    if db_attraction.place_id not in google_place_ids:
                        try:
                            db_dict = {
                                'place_id': db_attraction.place_id,
                                'name': db_attraction.name,
                                'formatted_address': db_attraction.formatted_address,
                                'rating': db_attraction.rating,
                                'user_ratings_total': db_attraction.user_ratings_total,
                                'price_level': db_attraction.price_level,
                                'types': db_attraction.types or [],
                                'photos': [],
                                'reviews': db_attraction.reviews or [],
                                'website': db_attraction.website or '',
                                'formatted_phone_number': db_attraction.phone_number or '',
                                'opening_hours': db_attraction.opening_hours or {},
                                'geometry': {}
                            }
                            if db_attraction.location and hasattr(db_attraction.location, 'coordinates'):
                                coords = db_attraction.location.coordinates
                                if len(coords) >= 2:
                                    db_dict['geometry'] = {'location': {'lat': coords[1], 'lng': coords[0]}}
                            results.append(db_dict)
                        except Exception as e:
                            logger.debug(f"[Search] Error converting MongoDB result: {e}")
            else:
                if query and not city and not country and (" " not in query.strip()) and not has_filters:
                    mapped = AttractionsService.popular_by_country(query.strip(), limit=int(params.get('limit', 50)), profile=profile)
                    _search_cache[cache_key] = (mapped, current_time)
                    return mapped
                if has_filters and place_type:
                    text_query = None
                    if requested_types:
                        type_name = requested_types[0].replace('_', ' ')
                        if city:
                            text_query = f"{type_name} in {city}, {country}" if country else f"{type_name} in {city}"
                        elif country:
                            text_query = f"{type_name} in {country}"
                        else:
                            text_query = type_name
                else:
                    text_query = query
                    if not has_filters:
                        if profile == 'tourist' and text_query:
                            text_query = f"{text_query} tourist attractions"
                        elif profile == 'local' and text_query:
                            text_query = f"{text_query} local spots"
                        elif profile == 'pro' and text_query:
                            text_query = f"{text_query} business"
                    if city:
                        text_query = f"{text_query} in {city}" if text_query else f"{city}"
                    elif country:
                        text_query = f"{text_query} in {country}" if text_query else f"{country}"
                results = google_places_service.search_places(query=text_query, location=None, radius=None, place_type=place_type)
            
            mapped = [AttractionsService._map_place_to_attraction(p, country_hint=country) for p in results]
        
        if requested_types:
            filtered_mapped = []
            for place in mapped:
                place_types = place.get('types', []) or []
                matches = False
                for req_type in requested_types:
                    req_lower = req_type.lower()
                    for pt in place_types:
                        pt_str = str(pt).lower()
                        if req_lower == pt_str or req_lower in pt_str or pt_str in req_lower:
                            matches = True
                            break
                    if matches:
                        break
                if matches:
                    filtered_mapped.append(place)
            
            logger.info(f"[Search] After category filtering: {len(filtered_mapped)} results remain (filtered out {len(mapped) - len(filtered_mapped)})")
            if filtered_mapped:
                sample_types_after = [place.get('types', [])[:3] for place in filtered_mapped[:3]]
                logger.info(f"[Search] Sample place types after category filtering: {sample_types_after}")
            mapped = filtered_mapped
        
        # Filter by minimum rating if specified (applies to both text and location-based searches)
        min_rating_value = None
        if min_rating:
            try:
                min_rating_value = float(min_rating)
                if min_rating_value > 0:
                    before_count = len(mapped)
                    mapped = [p for p in mapped if p.get('rating', 0) >= min_rating_value]
                    logger.info(f"[Search] Rating filter (>{min_rating_value}): {before_count} -> {len(mapped)} results")
            except (ValueError, TypeError):
                pass
        
        # Filter by maximum price level if specified (applies to both text and location-based searches)
        price_level_value = None
        if price_level:
            try:
                price_level_value = int(price_level)
                # Only filter if price level is less than 200 (meaningful filter)
                if price_level_value < 200:
                    before_count = len(mapped)
                    # Keep places with price_level <= filter OR places with no price_level (null)
                    mapped = [p for p in mapped if (p.get('price_level') is not None and p.get('price_level') <= price_level_value) or p.get('price_level') is None]
                    logger.info(f"[Search] Price filter (<={price_level_value}): {before_count} -> {len(mapped)} results")
            except (ValueError, TypeError):
                pass
        
        # Recalculate has_filters after parsing to ensure we have meaningful filter values
        has_filters = bool(
            requested_types or 
            (min_rating_value and min_rating_value > 0) or 
            (price_level_value and price_level_value < 200)
        )
        
        logger.info(f"[Search] Final filter status - has_filters={has_filters}, category_types={len(requested_types) if requested_types else 0}, min_rating={min_rating_value}, price_level={price_level_value}, location_search={location is not None}")
        logger.info(f"[Search] Final result count: {len(mapped)} attractions after all filters applied")
        
        # Apply ranking: use filter-based ranking if filters are applied, otherwise use profile-based ranking
        if has_filters:
            # Generic ranking: prioritize by rating and number of reviews when filters are used
            mapped.sort(key=lambda x: (
                -(x.get('rating', 0)),
                -(x.get('user_ratings_total', 0))
            ))
        else:
            if profile == 'tourist':
                tourist_types = ['tourist_attraction', 'point_of_interest', 'museum', 'art_gallery', 'church', 'park', 'zoo', 'amusement_park']
                mapped.sort(key=lambda x: (
                    -sum(1 for t in (x.get('types') or []) if any(tt in t.lower() for tt in tourist_types)),
                    -(x.get('rating', 0)),
                    -(x.get('user_ratings_total', 0))
                ))
            elif profile == 'local':
                local_types = ['restaurant', 'cafe', 'bar', 'park', 'gym', 'store', 'shopping_mall', 'supermarket', 'library', 'movie_theater']
                mapped.sort(key=lambda x: (
                    -sum(1 for t in (x.get('types') or []) if any(lt in t.lower() for lt in local_types)),
                    -(x.get('rating', 0)),
                    -(x.get('user_ratings_total', 0))
                ))
            elif profile == 'pro':
                pro_types = ['lodging', 'establishment', 'point_of_interest', 'train_station', 'airport', 'gas_station', 'bank', 'atm']
                mapped.sort(key=lambda x: (
                    -sum(1 for t in (x.get('types') or []) if any(pt in t.lower() for pt in pro_types)),
                    -(x.get('rating', 0)),
                    -(x.get('user_ratings_total', 0))
                ))
        
        _search_cache[cache_key] = (mapped, current_time)
        
        if len(_search_cache) > 50:
            sorted_cache = sorted(_search_cache.items(), key=lambda x: x[1][1])
            for old_key, _ in sorted_cache[:-50]:
                del _search_cache[old_key]
        
        return mapped

    @staticmethod
    def get_by_place_id(place_id: str):
        """Fetch place details from Google and map to API shape (no DB persistence)."""
        if not place_id:
            return None
        details = google_places_service.get_place_details(place_id)
        if not details:
            return None
        country = None
        for comp in details.get('address_components', []) or []:
            if 'country' in (comp.get('types') or []):
                country = comp.get('long_name')
                break
        return AttractionsService._map_place_to_attraction(details, country_hint=country)

    @staticmethod
    def similar_suggestions(place_id: str, limit: int = 10):
        """Compute similar suggestions using Google only (no DB)."""
        base = AttractionsService.get_by_place_id(place_id)
        if not base:
            return []
        mapped: list = []
        geometry = base.get('location')
        primary_type = (base.get('types') or [None])[0]
        if geometry and 'lat' in geometry and 'lng' in geometry:
            keyword = base.get('name', '').split(' ')[0] if base.get('name') else None
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
        return [m for m in mapped if m.get('place_id') != place_id][:limit]

    @staticmethod
    def sync_from_google(country: str, limit: int = 20):
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
            attraction.opening_hours = AttractionsService._filter_opening_hours(details.get('opening_hours'))
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
        attraction.opening_hours = AttractionsService._filter_opening_hours(details.get('opening_hours'))
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


