from django.core.management.base import BaseCommand
from src.models import Attraction
from src.external_services import google_places_service
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Populate attractions from Google Places API'

    def add_arguments(self, parser):
        parser.add_argument('--country', type=str, default='France', help='Country to search attractions for')
        parser.add_argument('--limit', type=int, default=20, help='Number of attractions to fetch')
        parser.add_argument('--type', type=str, default='tourist_attraction', help='Place type to search for')

    def handle(self, *args, **options):
        country = options['country']
        limit = options['limit']
        place_type = options['type']
        
        self.stdout.write(f'Searching for {place_type} in {country}...')
        
        # Search for attractions
        places = google_places_service.search_attractions_by_country(country, limit)
        
        if not places:
            self.stdout.write(self.style.ERROR('No places found. Check your API key and internet connection.'))
            return
        
        created_count = 0
        updated_count = 0
        
        for place in places:
            place_id = place.get('place_id')
            if not place_id:
                continue
            
            # Get detailed information
            details = google_places_service.get_place_details(place_id)
            if not details:
                continue
            
            # Extract location info
            geometry = details.get('geometry', {})
            location = geometry.get('location', {})
            latitude = location.get('lat')
            longitude = location.get('lng')
            
            # Extract address components
            address_components = details.get('address_components', [])
            country_name = country
            city_name = ''
            
            for component in address_components:
                types = component.get('types', [])
                if 'country' in types:
                    country_name = component.get('long_name', country)
                elif 'locality' in types or 'administrative_area_level_1' in types:
                    city_name = component.get('long_name', '')
            
            # Create or update attraction
            attraction, created = Attraction.objects.get_or_create(
                place_id=place_id,
                defaults={
                    'name': details.get('name', ''),
                    'formatted_address': details.get('formatted_address', ''),
                    'country': country_name,
                    'city': city_name,
                    'category': place_type.replace('_', ' ').title(),
                    'types': details.get('types', []),
                    'rating': details.get('rating', 0),
                    'user_ratings_total': details.get('user_ratings_total', 0),
                    'price_level': details.get('price_level'),
                    'latitude': latitude,
                    'longitude': longitude,
                    'website': details.get('website', ''),
                    'phone_number': details.get('formatted_phone_number', ''),
                    'opening_hours': details.get('opening_hours', {}),
                    'reviews': details.get('reviews', []),
                    'raw_data': details,
                    'is_featured': details.get('rating', 0) >= 4.0,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'Created: {attraction.name}')
            else:
                # Update existing attraction
                attraction.name = details.get('name', attraction.name)
                attraction.rating = details.get('rating', attraction.rating)
                attraction.user_ratings_total = details.get('user_ratings_total', attraction.user_ratings_total)
                attraction.price_level = details.get('price_level', attraction.price_level)
                attraction.raw_data = details
                attraction.save()
                updated_count += 1
                self.stdout.write(f'Updated: {attraction.name}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully processed {len(places)} places. '
                f'Created: {created_count}, Updated: {updated_count}'
            )
        )


