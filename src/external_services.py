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
                places_result = self.client.places(
                    query=query,
                    type=place_type
                )
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
    
    def search_attractions_by_country(self, country, limit=20):
        logger.debug("GooglePlacesService.search_attractions_by_country called for country=%r limit=%s", country, limit)
        if not self.client:
            logger.warning("GooglePlacesService.client is None — returning empty list for country search")
            return []
        try:
            logger.debug("Calling places text search for tourist attractions in %s", country)
            places_result = self.client.places(
                query=f"tourist attractions in {country}",
                type="tourist_attraction"
            )
            results = places_result.get('results', [])
            logger.info("Google Places country search returned %d results for %s", len(results), country)
            sample_ids = [r.get('place_id') for r in results[:5]]
            logger.debug("Sample place_ids for country %s: %s", country, sample_ids)
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


