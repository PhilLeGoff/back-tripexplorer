import googlemaps
from django.conf import settings
import logging
import traceback

logger = logging.getLogger(__name__)

class GooglePlacesService:
    def __init__(self):
        self.api_key = settings.GOOGLE_PLACES_API_KEY
        if not self.api_key:
            logger.warning("Google Places API key not configured")
            self.client = None
        else:
            try:
                self.client = googlemaps.Client(key=self.api_key)
                logger.info("Google Places client initialized")
            except Exception as e:
                logger.exception("Failed to initialize googlemaps.Client: %s", e)
                self.client = None
    
    def search_places(self, query, location=None, radius=None, place_type=None):
        logger.debug("GooglePlacesService.search_places called with query=%r, location=%r, radius=%r, place_type=%r",
                     query, location, radius, place_type)
        if not self.client:
            logger.warning("GooglePlacesService.client is None — returning empty list")
            return []
        try:
            if location:
                logger.debug("Calling places_nearby with location=%r radius=%r type=%r keyword=%r", location, radius or 5000, place_type, query)
                places_result = self.client.places_nearby(
                    location=location,
                    radius=radius or 5000,
                    type=place_type,
                    keyword=query
                )
            else:
                logger.debug("Calling places (text search) with query=%r type=%r", query, place_type)
                # IMPORTANT: Google Places API text search (places method) does NOT directly support 'type' parameter
                # The 'type' parameter only works with places_nearby() method
                # For text search, we include the type in the query string and filter results afterward
                if place_type:
                    # Ensure place_type is in the query for better results
                    # But we'll still need to filter by type in the results
                    if query and place_type.lower() not in query.lower():
                        # Type not explicitly in query - enhance query
                        query_with_type = f"{place_type.replace('_', ' ')} {query}"
                        logger.debug(f"Enhancing query: '{query}' -> '{query_with_type}' for type={place_type}")
                        query = query_with_type
                
                # Call API - type filtering will happen in post-processing
                places_result = self.client.places(query=query)
                
                # Filter by place_type if specified (since API doesn't support it in text search)
                if place_type:
                    results_before = places_result.get('results', [])
                    filtered_results = []
                    for place in results_before:
                        place_types = place.get('types', []) or []
                        # Check if place_type matches any of the place's types
                        if any(place_type.lower() == str(pt).lower() or place_type.lower() in str(pt).lower() 
                               for pt in place_types):
                            filtered_results.append(place)
                    places_result['results'] = filtered_results
                    logger.info(f"Filtered results by type '{place_type}': {len(results_before)} -> {len(filtered_results)}")
            results = places_result.get('results', [])
            logger.info("Google Places returned %d results for query=%r", len(results), query)
            # Log a small sample of place_ids for inspection
            sample_ids = [r.get('place_id') for r in results[:5]]
            logger.debug("Sample place_ids: %s", sample_ids)
            return results
        except Exception as e:
            logger.error(f"Google Places API error: {e}")
            logger.debug(traceback.format_exc())
            return []
    
    def get_place_details(self, place_id, fields=None):
        logger.debug("GooglePlacesService.get_place_details called for place_id=%r fields=%r", place_id, fields)
        if not self.client:
            logger.warning("GooglePlacesService.client is None — cannot fetch place details")
            return None
        try:
            default_fields = [
                'place_id', 'name', 'formatted_address', 'geometry',
                'rating', 'user_ratings_total', 'price_level', 'type',
                'opening_hours', 'photo', 'reviews', 'website', 'formatted_phone_number'
            ]
            fields_to_request = fields or default_fields
            logger.debug("Requesting place details for %s fields=%s", place_id, fields_to_request)
            place_details = self.client.place(
                place_id=place_id,
                fields=fields_to_request
            )
            result = place_details.get('result', {})
            if result:
                logger.info("Fetched details for place_id=%s (name=%s)", place_id, result.get('name'))
            else:
                logger.warning("No details returned for place_id=%s — raw response keys: %s", place_id, list(place_details.keys()))
            return result
        except Exception as e:
            logger.error(f"Google Places Details API error for {place_id}: {e}")
            logger.debug(traceback.format_exc())
            return None
    
    def search_attractions_by_country(self, country, limit=20, profile='tourist', city=None):
        logger.debug("GooglePlacesService.search_attractions_by_country called for country=%r city=%r limit=%s profile=%s", country, city, limit, profile)
        if not self.client:
            logger.warning("GooglePlacesService.client is None — returning empty list for country search")
            return []
        try:
            # Build location string (city takes precedence if provided)
            location_str = f"{city}, {country}" if city else country
            
            # Adjust query and type based on profile
            if profile == 'tourist':
                query = f"tourist attractions in {location_str}"
                place_type = "tourist_attraction"
            elif profile == 'local':
                query = f"local favorites restaurants cafes in {location_str}"
                place_type = None  # Let Google suggest local spots
            elif profile == 'pro':
                query = f"business hotels airports train stations in {location_str}"
                place_type = None  # Let Google suggest business amenities
            else:
                query = f"attractions in {location_str}"
                place_type = "tourist_attraction"
            
            logger.debug("Calling places text search for profile=%s in %s: query=%r type=%r", profile, location_str, query, place_type)
            places_result = self.client.places(
                query=query,
                type=place_type
            )
            results = places_result.get('results', [])
            logger.info("Google Places country/city search returned %d results for %s (profile=%s)", len(results), location_str, profile)
            sample_ids = [r.get('place_id') for r in results[:5]]
            logger.debug("Sample place_ids for %s: %s", location_str, sample_ids)
            return results[:limit]
        except Exception as e:
            logger.error(f"Google Places country search error: {e}")
            logger.debug(traceback.format_exc())
            return []
    
    def search_restaurants_by_location(self, location, radius=5000, limit=20):
        logger.debug("search_restaurants_by_location called with location=%r radius=%s limit=%s", location, radius, limit)
        if not self.client:
            logger.warning("GooglePlacesService.client is None — returning empty list for restaurant search")
            return []
        try:
            places_result = self.client.places_nearby(
                location=location,
                radius=radius,
                type="restaurant"
            )
            results = places_result.get('results', [])
            logger.info("Google Places restaurant search returned %d results", len(results))
            return results[:limit]
        except Exception as e:
            logger.error(f"Google Places restaurant search error: {e}")
            logger.debug(traceback.format_exc())
            return []
    
    def search_hotels_by_location(self, location, radius=10000, limit=20):
        logger.debug("search_hotels_by_location called with location=%r radius=%s limit=%s", location, radius, limit)
        if not self.client:
            logger.warning("GooglePlacesService.client is None — returning empty list for hotel search")
            return []
        try:
            places_result = self.client.places_nearby(
                location=location,
                radius=radius,
                type="lodging"
            )
            results = places_result.get('results', [])
            logger.info("Google Places hotel search returned %d results", len(results))
            return results[:limit]
        except Exception as e:
            logger.error(f"Google Places hotel search error: {e}")
            logger.debug(traceback.format_exc())
            return []

# Global instance
google_places_service = GooglePlacesService()


