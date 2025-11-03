from rest_framework.renderers import JSONRenderer
from rest_framework.utils import encoders
import json

try:
    from bson import ObjectId
    BSON_AVAILABLE = True
except ImportError:
    ObjectId = None
    BSON_AVAILABLE = False


class MongoJSONEncoder(encoders.JSONEncoder):
    """Custom JSON encoder that handles MongoDB ObjectId."""
    
    def default(self, obj):
        # Handle ObjectId
        if BSON_AVAILABLE and isinstance(obj, ObjectId):
            return str(obj)
        # Fallback: check by class name
        if hasattr(obj, '__class__'):
            class_name = obj.__class__.__name__
            if class_name == 'ObjectId' or 'ObjectId' in str(type(obj)):
                return str(obj)
        # Fallback to parent
        return super().default(obj)


class MongoJSONRenderer(JSONRenderer):
    """Custom JSON renderer that uses MongoJSONEncoder."""
    encoder_class = MongoJSONEncoder

