from __future__ import annotations

from typing import Any, Dict

from rest_framework.exceptions import ValidationError, NotFound

from ..models import Attraction, Compilation, CompilationItem
from ..serializers import CompilationSerializer


class CompilationsController:
    @staticmethod
    def add_item(compilation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        attraction_id = payload.get('attraction_id') or payload.get('attraction')
        if not attraction_id:
            raise ValidationError({'error': 'attraction_id required'})

        try:
            compilation = Compilation.objects.get(id=compilation_id)
        except Compilation.DoesNotExist:
            raise NotFound('Compilation not found')

        try:
            attraction = Attraction.objects.get(id=attraction_id)
        except Attraction.DoesNotExist:
            raise NotFound('Attraction not found')

        # Prevent duplicates
        for item in compilation.items:
            if getattr(item.attraction, 'id', None) == getattr(attraction, 'id', None):
                raise ValidationError({'error': 'Attraction already in compilation'})

        new_item = CompilationItem(attraction=attraction, order_index=payload.get('order_index', 0))
        compilation.items.append(new_item)
        compilation.save()

        return CompilationSerializer(compilation).data

    @staticmethod
    def remove_item(compilation_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        import logging
        logger = logging.getLogger(__name__)
        
        attraction_id = payload.get('attraction_id') or payload.get('attraction')
        if not attraction_id:
            raise ValidationError({'error': 'attraction_id required'})

        logger.debug(f"remove_item: compilation_id={compilation_id}, attraction_id={attraction_id}")

        try:
            compilation = Compilation.objects.get(id=compilation_id)
            logger.debug(f"Found compilation with {len(compilation.items)} items")
        except Compilation.DoesNotExist:
            raise NotFound('Compilation not found')

        # Remove matching embedded items
        original_len = len(compilation.items)
        # Normalize attraction_id for comparison (can be string, ObjectId, or number)
        attraction_id_normalized = str(attraction_id).strip()
        
        # Filter items: keep only those that don't match the attraction_id
        filtered_items = []
        for item in compilation.items:
            try:
                # Safely get attraction ID
                item_attraction = getattr(item, 'attraction', None)
                if item_attraction is None:
                    # Skip items with no attraction reference
                    continue
                
                # Try to get the ID - this may fail if reference is broken
                try:
                    item_attraction_id = getattr(item_attraction, 'id', None)
                    if item_attraction_id is None:
                        item_attraction_id_str = None
                    else:
                        # Normalize to string for comparison
                        item_attraction_id_str = str(item_attraction_id).strip()
                except Exception as e:
                    # Reference is broken, skip this item
                    logger.debug(f"Skipping item with broken reference: {e}")
                    continue
                
                # Also try place_id as fallback
                item_place_id = None
                try:
                    item_place_id = str(getattr(item_attraction, 'place_id', None) or '').strip()
                except Exception:
                    pass
                
                # Compare both id and place_id
                matches_id = item_attraction_id_str and item_attraction_id_str == attraction_id_normalized
                matches_place_id = item_place_id and item_place_id == attraction_id_normalized
                
                if not (matches_id or matches_place_id):
                    filtered_items.append(item)
                else:
                    logger.debug(f"Removing item: id={item_attraction_id_str}, place_id={item_place_id}, matches={matches_id or matches_place_id}")
            except Exception as e:
                # If anything fails, skip this item but log it
                logger.debug(f"Error processing item: {e}")
                continue
        
        compilation.items = filtered_items
        logger.debug(f"After filtering: {len(compilation.items)} items remain (was {original_len})")
        
        if len(compilation.items) != original_len:
            compilation.save()
            logger.debug("Compilation saved successfully")
            # Note: We don't delete the attraction itself as it may be used in other compilations
            # If you need to delete it, check if it's used elsewhere first

        # Refresh the compilation from DB to ensure references are valid
        try:
            compilation.reload()
        except Exception as e:
            logger.warning(f"Failed to reload compilation: {e}")

        # Serialize after all modifications with error handling
        try:
            # Get serialized data
            result = CompilationSerializer(compilation).data
            
            # Final cleanup: ensure all ObjectIds are converted to strings
            def clean_objectids(obj):
                """Final cleanup pass for ObjectIds."""
                if obj is None:
                    return None
                
                # Try to import bson for proper isinstance check
                try:
                    from bson import ObjectId as BsonObjectId
                    if isinstance(obj, BsonObjectId):
                        return str(obj)
                except:
                    pass
                
                # Check for ObjectId by class name
                if hasattr(obj, '__class__'):
                    class_name = obj.__class__.__name__
                    type_str = str(type(obj)).lower()
                    if class_name == 'ObjectId' or 'ObjectId' in type_str:
                        return str(obj)
                
                # Check for MongoEngine BaseList and similar special types (must be before list check)
                if hasattr(obj, '__class__'):
                    type_str = str(type(obj)).lower()
                    class_name = obj.__class__.__name__
                    # MongoEngine BaseList, EmbeddedDocumentList, etc. need special handling
                    if 'mongoengine' in type_str and ('baselist' in class_name.lower() or 'list' in class_name.lower()):
                        # Convert MongoEngine list-like types to Python list
                        return [clean_objectids(item) for item in obj]
                
                # Handle dictionaries
                if isinstance(obj, dict):
                    return {k: clean_objectids(v) for k, v in obj.items()}
                
                # Handle regular Python lists
                if isinstance(obj, list):
                    return [clean_objectids(item) for item in obj]
                
                # Handle sets
                if isinstance(obj, set):
                    return {clean_objectids(item) for item in obj}
                
                # Handle other iterables (tuples, etc.) - but skip strings and bytes
                if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
                    try:
                        # Convert to list for safety (handles BaseList and similar)
                        return [clean_objectids(item) for item in obj]
                    except (TypeError, AttributeError):
                        # If iteration fails, return as-is
                        return obj
                
                return obj
            
            result = clean_objectids(result)
            logger.debug(f"Serialization successful, returning {len(result.get('items', []))} items")
            return result
        except Exception as e:
            # If serialization fails, try manual serialization
            import traceback
            logger.error(f"Serialization error in remove_item: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Fallback: return minimal data with manual sanitization
            try:
                return {
                    'id': str(compilation.id),
                    'name': str(compilation.name) if compilation.name else '',
                    'profile': str(compilation.profile) if compilation.profile else '',
                    'country': str(compilation.country) if compilation.country else '',
                    'items': [],  # Empty items on error
                }
            except Exception:
                # Ultimate fallback
                return {'id': '', 'name': '', 'profile': '', 'country': '', 'items': []}



