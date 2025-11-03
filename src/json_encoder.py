import json
from rest_framework.utils.encoders import JSONEncoder

try:
    from bson import ObjectId
    BSON_AVAILABLE = True
except ImportError:
    ObjectId = None
    BSON_AVAILABLE = False


class MongoJSONEncoder(JSONEncoder):
    """Custom JSON encoder that handles MongoDB ObjectId and other non-serializable types."""
    
    def default(self, obj):
        # Handle ObjectId
        if BSON_AVAILABLE and isinstance(obj, ObjectId):
            return str(obj)
        # Fallback: check by class name
        if hasattr(obj, '__class__'):
            class_name = obj.__class__.__name__
            if class_name == 'ObjectId' or 'ObjectId' in str(type(obj)):
                return str(obj)
        # Try parent encoder
        try:
            return super().default(obj)
        except TypeError:
            # If parent also fails, try to convert to string as last resort
            return str(obj)

