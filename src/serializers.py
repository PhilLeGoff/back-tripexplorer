from rest_framework import serializers

try:
    from rest_framework_mongoengine.serializers import DocumentSerializer
    MONGOENGINE_SERIALIZER_AVAILABLE = True
except Exception:
    DocumentSerializer = None
    MONGOENGINE_SERIALIZER_AVAILABLE = False

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

        def to_representation(self, obj):
            data = super().to_representation(obj)
            # Ensure nested attraction is fully serialized (not ObjectId)
            try:
                if getattr(obj, 'attraction', None) is not None:
                    data['attraction'] = AttractionSerializer(obj.attraction).data
            except Exception:
                pass
            return data

    class CompilationSerializer(DocumentSerializer):
        items = CompilationItemSerializer(many=True, read_only=True)

        class Meta:
            model = Compilation
            fields = ('id', 'name', 'profile', 'country', 'items', 'created_at', 'updated_at')

        def to_representation(self, obj):
            data = super().to_representation(obj)
            # Ensure id is a string for JSON encoding
            if 'id' in data and data['id'] is not None:
                data['id'] = str(data['id'])
            # Normalize items using our item serializer to avoid raw ObjectIds
            try:
                data['items'] = [CompilationItemSerializer(item).data for item in getattr(obj, 'items', [])]
            except Exception:
                pass
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

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class SignInSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)



