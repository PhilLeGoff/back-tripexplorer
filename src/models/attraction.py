import mongoengine as me
from datetime import datetime
from .user import User


class Attraction(me.Document):
    place_id = me.StringField(required=True, unique=True)
    name = me.StringField(required=True)
    formatted_address = me.StringField(default='')
    country = me.StringField(required=True)
    # Track the owner user who saved this attraction
    owner = me.ReferenceField(User, required=False)
    city = me.StringField(default='')
    category = me.StringField(default='')
    types = me.ListField(me.StringField(), default=list)
    rating = me.FloatField(default=0)
    user_ratings_total = me.IntField(default=0)
    price_level = me.IntField(null=True)
    # GEO field
    location = me.PointField(auto_index=False)
    description = me.StringField(default='')
    website = me.StringField(default='')
    phone_number = me.StringField(default='')
    photo_reference = me.StringField(default='')
    photos_count = me.IntField(default=0)
    opening_hours = me.DictField(default=dict)
    reviews = me.ListField(me.DictField(), default=list)
    likes = me.IntField(default=0)
    is_featured = me.BooleanField(default=False)
    raw_data = me.DictField(default=dict)
    created_at = me.DateTimeField(default=datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.utcnow)

    meta = {
        'indexes': [
            {'fields': ['$name', "$formatted_address", "$city", "$country"]},
            {'fields': ['country', 'rating']},
            {'fields': ['city', 'category']},
            {'fields': ['is_featured', 'likes']},
            {'fields': [('location', '2dsphere')]}
        ],
        'ordering': ['-likes', '-rating', '-user_ratings_total']
    }

    def __str__(self) -> str:
        return f"{self.name} ({self.city or self.country})"
    
    @property
    def price_level_display(self):
        """Convert numeric price level to $ symbols"""
        if self.price_level is None:
            return ""
        return "$" * (self.price_level + 1)
    
    @property
    def primary_type(self):
        """Get the primary type from Google Places types"""
        if not self.types:
            return self.category or "attraction"
        
        # Priority order for display
        priority_types = [
            'tourist_attraction', 'museum', 'park', 'restaurant', 
            'lodging', 'shopping_mall', 'amusement_park', 'zoo'
        ]
        
        for ptype in priority_types:
            if ptype in self.types:
                return ptype.replace('_', ' ').title()
        
        return self.types[0].replace('_', ' ').title()


