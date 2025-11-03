from rest_framework import serializers

try:
    from rest_framework_mongoengine.serializers import DocumentSerializer
    MONGOENGINE_SERIALIZER_AVAILABLE = True
except Exception:
    DocumentSerializer = None
    MONGOENGINE_SERIALIZER_AVAILABLE = False

try:
    from bson import ObjectId
    BSON_AVAILABLE = True
except ImportError:
    ObjectId = None
    BSON_AVAILABLE = False

from .models import Attraction, Compilation, CompilationItem, User


if MONGOENGINE_SERIALIZER_AVAILABLE:
    from rest_framework import serializers as drf_serializers

    class AttractionSerializer(DocumentSerializer):
        location = drf_serializers.SerializerMethodField()

        class Meta:
            model = Attraction
            fields = '__all__'

        def get_location(self, obj):
            loc = getattr(obj, 'location', None)
            if not loc:
                return None
            # MongoEngine may return PointField as dict-like or as pymongo SON
            try:
                coords = loc.get('coordinates') if isinstance(loc, dict) else (getattr(loc, 'coordinates', None) or [])
            except Exception:
                coords = []
            if coords and len(coords) >= 2:
                return {'lat': coords[1], 'lng': coords[0]}
            return None

        def to_representation(self, obj):
            """Normalize output so frontend has stable fields.

            - Ensure `location` is {lat,lng}
            - Expose a stable `id` equal to `place_id` for API consumers
            """
            data = super().to_representation(obj)
            # Normalize location already handled via get_location
            # Stable id for clients
            data['id'] = data.get('place_id') or getattr(obj, 'place_id', None)
            # Mirror pk to id (string) and strip raw ObjectIds
            if 'pk' in data:
                data['pk'] = data['id']
            # Coerce any stray ObjectId-like values to string
            try:
                for k, v in list(data.items()):
                    if getattr(v, '__class__', None) and v.__class__.__name__ == 'ObjectId':
                        data[k] = str(v)
            except Exception:
                pass
            # Fallback: derive photo_reference from raw_data.photos if missing
            try:
                if not data.get('photo_reference'):
                    photos = (data.get('raw_data') or {}).get('photos') or []
                    if photos and isinstance(photos, list):
                        ref = (photos[0] or {}).get('photo_reference')
                        if ref:
                            data['photo_reference'] = ref
            except Exception:
                pass
            return data

    class CompilationItemSerializer(DocumentSerializer):
        attraction = AttractionSerializer(read_only=True)

        class Meta:
            model = CompilationItem
            fields = ('attraction', 'order_index', 'added_at')

        def _sanitize_objectids(self, obj):
            """Recursively convert ObjectId instances to strings."""
            if obj is None:
                return None
            # Check if it's an ObjectId - use isinstance if available
            if BSON_AVAILABLE and isinstance(obj, ObjectId):
                return str(obj)
            # Fallback: check by class name
            obj_class_name = getattr(obj, '__class__', None)
            if obj_class_name:
                class_name = getattr(obj_class_name, '__name__', '')
                if class_name == 'ObjectId' or 'ObjectId' in str(type(obj)):
                    return str(obj)
            if isinstance(obj, dict):
                return {k: self._sanitize_objectids(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [self._sanitize_objectids(item) for item in obj]
            if isinstance(obj, tuple):
                return tuple(self._sanitize_objectids(item) for item in obj)
            if isinstance(obj, set):
                return {self._sanitize_objectids(item) for item in obj}
            return obj

        def to_representation(self, obj):
            data = super().to_representation(obj)
            
            # Immediately sanitize the raw data from super() to catch any ObjectIds
            data = self._sanitize_objectids(data)
            
            # Ensure nested attraction is fully serialized (not ObjectId)
            try:
                attraction = getattr(obj, 'attraction', None)
                if attraction is not None:
                    # Try to access the attraction to see if reference is valid
                    try:
                        _ = attraction.id  # Force dereference to check if valid
                        attraction_data = AttractionSerializer(attraction).data
                        # Sanitize any ObjectIds in attraction data
                        data['attraction'] = self._sanitize_objectids(attraction_data)
                    except Exception:
                        # Reference is broken or attraction doesn't exist
                        # Keep only the ID if available
                        try:
                            att_id = str(attraction.id) if hasattr(attraction, 'id') else None
                            data['attraction'] = {'id': att_id} if att_id else None
                        except Exception:
                            data['attraction'] = None
            except Exception as e:
                # If anything fails, set attraction to None
                data['attraction'] = None
            
            # Final sanitization pass (double pass for safety)
            data = self._sanitize_objectids(data)
            return data

    class CompilationSerializer(DocumentSerializer):
        items = CompilationItemSerializer(many=True, read_only=True)

        class Meta:
            model = Compilation
            fields = ('id', 'name', 'profile', 'country', 'items', 'created_at', 'updated_at')

        def _sanitize_objectids(self, obj):
            """Recursively convert ObjectId instances to strings."""
            if obj is None:
                return None
            # Check if it's an ObjectId - use isinstance if available
            if BSON_AVAILABLE and isinstance(obj, ObjectId):
                return str(obj)
            # Fallback: check by class name
            obj_class_name = getattr(obj, '__class__', None)
            if obj_class_name:
                class_name = getattr(obj_class_name, '__name__', '')
                if class_name == 'ObjectId' or 'ObjectId' in str(type(obj)):
                    return str(obj)
            # Handle dictionaries
            if isinstance(obj, dict):
                return {k: self._sanitize_objectids(v) for k, v in obj.items()}
            # Handle lists
            if isinstance(obj, list):
                return [self._sanitize_objectids(item) for item in obj]
            # Handle tuples
            if isinstance(obj, tuple):
                return tuple(self._sanitize_objectids(item) for item in obj)
            # Handle sets
            if isinstance(obj, set):
                return {self._sanitize_objectids(item) for item in obj}
            return obj

        def to_representation(self, obj):
            data = super().to_representation(obj)
            # Ensure id is a string for JSON encoding (must be done before sanitization)
            if 'id' in data:
                if data['id'] is not None:
                    data['id'] = str(data['id'])
                else:
                    data['id'] = None
            
            # Normalize items using our item serializer to avoid raw ObjectIds
            try:
                items_data = []
                for item in getattr(obj, 'items', []):
                    try:
                        item_data = CompilationItemSerializer(item).data
                        # Sanitize any ObjectIds in the item data
                        item_data = self._sanitize_objectids(item_data)
                        items_data.append(item_data)
                    except Exception:
                        # Skip items that can't be serialized
                        continue
                data['items'] = items_data
            except Exception:
                data['items'] = []
            
            # Final pass: sanitize all ObjectIds in the entire data structure
            # This must be done recursively and comprehensively
            data = self._sanitize_objectids(data)
            
            # Extra safety: manually check and convert any remaining ObjectIds
            def deep_sanitize(d):
                """Deep recursive sanitization as final safety net."""
                if d is None:
                    return None
                if BSON_AVAILABLE and isinstance(d, ObjectId):
                    return str(d)
                if isinstance(d, dict):
                    return {k: deep_sanitize(v) for k, v in d.items()}
                if isinstance(d, (list, tuple)):
                    return type(d)(deep_sanitize(item) for item in d)
                if isinstance(d, set):
                    return {deep_sanitize(item) for item in d}
                # Last resort: check if it looks like an ObjectId
                if hasattr(d, '__class__') and 'ObjectId' in str(type(d)):
                    return str(d)
                return d
            
            data = deep_sanitize(data)
            return data

else:
    # Fallback manual serializers
    class AttractionSerializer(serializers.Serializer):
        id = serializers.CharField(read_only=True)
        place_id = serializers.CharField()
        name = serializers.CharField()
        formatted_address = serializers.CharField(allow_blank=True)
        country = serializers.CharField()
        city = serializers.CharField(allow_blank=True)
        category = serializers.CharField(allow_blank=True)
        types = serializers.ListField(child=serializers.CharField(), allow_empty=True, default=list)
        rating = serializers.FloatField(default=0)
        user_ratings_total = serializers.IntegerField(default=0)
        price_level = serializers.IntegerField(allow_null=True, required=False)
        location = serializers.DictField(allow_null=True, required=False)
        description = serializers.CharField(allow_blank=True, required=False)
        website = serializers.CharField(allow_blank=True, required=False)
        phone_number = serializers.CharField(allow_blank=True, required=False)
        photo_reference = serializers.CharField(allow_blank=True, required=False)
        photos_count = serializers.IntegerField(default=0)
        opening_hours = serializers.DictField(default=dict)
        reviews = serializers.ListField(child=serializers.DictField(), default=list)
        likes = serializers.IntegerField(default=0)
        is_featured = serializers.BooleanField(default=False)
        raw_data = serializers.DictField(default=dict)
        created_at = serializers.DateTimeField(read_only=True)
        updated_at = serializers.DateTimeField(read_only=True)

        def create(self, validated_data):
            # Ensure location saved as GeoJSON Point if present
            loc = validated_data.get('location')
            if loc and isinstance(loc, dict) and 'lat' in loc and 'lng' in loc:
                validated_data['location'] = {'type': 'Point', 'coordinates': [loc['lng'], loc['lat']]}
            att = Attraction(**validated_data)
            att.save()
            return att

        def to_representation(self, instance):
            data = {}
            for field in ('id','place_id','name','formatted_address','country','city','category','types',
                          'rating','user_ratings_total','price_level','description','website','phone_number',
                          'photo_reference','photos_count','opening_hours','reviews','likes','is_featured','raw_data',
                          'created_at','updated_at'):
                data[field] = getattr(instance, field, None)
            # location: convert GeoJSON to {lat,lng}
            loc = getattr(instance, 'location', None)
            if loc and isinstance(loc, dict):
                coords = loc.get('coordinates') or []
                if len(coords) >= 2:
                    data['location'] = {'lat': coords[1], 'lng': coords[0]}
                else:
                    data['location'] = None
            else:
                data['location'] = None
            # Fallback: derive photo_reference from raw_data.photos if missing
            try:
                if not data.get('photo_reference'):
                    photos = (data.get('raw_data') or {}).get('photos') or []
                    if photos and isinstance(photos, list):
                        ref = (photos[0] or {}).get('photo_reference')
                        if ref:
                            data['photo_reference'] = ref
            except Exception:
                pass
            return data

    class CompilationItemSerializer(serializers.Serializer):
        attraction = AttractionSerializer(read_only=True)
        attraction_id = serializers.CharField(write_only=True)
        order_index = serializers.IntegerField(default=0)
        added_at = serializers.DateTimeField(read_only=True)

    class CompilationSerializer(serializers.Serializer):
        id = serializers.CharField(read_only=True)
        name = serializers.CharField()
        profile = serializers.CharField()
        country = serializers.CharField()
        items = CompilationItemSerializer(many=True, read_only=True)
        created_at = serializers.DateTimeField(read_only=True)
        updated_at = serializers.DateTimeField(read_only=True)


class SignUpSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    email = serializers.EmailField()
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    profile = serializers.ChoiceField(choices=['tourist', 'local', 'pro'], required=False, default='tourist')
    selected_country = serializers.CharField(required=False, default='France')
    selected_city = serializers.CharField(required=False, allow_blank=True, default='')
    selected_profile = serializers.CharField(read_only=True)
    selected_country_serialized = serializers.CharField(read_only=True, source='selected_country')

    def to_representation(self, instance):
        """Return user data including profile, country, and city."""
        return {
            'id': str(getattr(instance, 'id', '')),
            'email': getattr(instance, 'email', ''),
            'first_name': getattr(instance, 'first_name', ''),
            'last_name': getattr(instance, 'last_name', ''),
            'selected_profile': getattr(instance, 'selected_profile', 'tourist'),
            'selected_country': getattr(instance, 'selected_country', 'France'),
            'selected_city': getattr(instance, 'selected_city', ''),
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        profile = validated_data.pop('profile', 'tourist')
        selected_country = validated_data.pop('selected_country', 'France')
        selected_city = validated_data.pop('selected_city', '')
        user = User(**validated_data)
        user.selected_profile = profile
        user.selected_country = selected_country
        user.selected_city = selected_city
        user.set_password(password)
        user.save()
        return user


class SignInSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)



