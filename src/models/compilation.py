import mongoengine as me
from datetime import datetime
from .attraction import Attraction
from .user import User

class CompilationItem(me.EmbeddedDocument):
    """Embedded item for a compilation to preserve order and extra metadata.
    Stores a reference to an Attraction and ordering information."""
    attraction = me.ReferenceField(Attraction, required=True)
    order_index = me.IntField(default=0)
    added_at = me.DateTimeField(default=datetime.utcnow)

    def __str__(self) -> str:
        # Be defensive in case the reference is missing
        try:
            name = self.attraction.name
        except Exception:
            name = str(self.attraction.id) if getattr(self.attraction, 'id', None) else 'unknown'
        return f"{name} (order: {self.order_index})"

class Compilation(me.Document):
    name = me.StringField(max_length=120, default="Ma compilation")
    profile = me.StringField(max_length=20, default="tourist")  # local/tourist/pro
    country = me.StringField(max_length=100, required=True)
    # Added owner reference to link compilation to a user
    owner = me.ReferenceField(User, required=False)
    # Embedded list preserves ordering and extra fields (order_index, added_at)
    items = me.EmbeddedDocumentListField(CompilationItem, default=list)
    created_at = me.DateTimeField(default=datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.utcnow)

    meta = {
        'ordering': ['-updated_at']
    }

    def __str__(self) -> str:
        return f"Compilation {self.name} - {self.country}"
    
    @property
    def total_budget(self):
        """Calculate total budget based on price levels of referenced attractions"""
        total = 0
        for item in self.items:
            try:
                if item.attraction and item.attraction.price_level is not None:
                    total += item.attraction.price_level + 1
            except Exception:
                # if the reference can't be resolved, skip
                continue
        return total
