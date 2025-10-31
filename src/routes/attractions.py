from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from ..models import Attraction, Compilation
from ..serializers import AttractionSerializer, CompilationSerializer
from ..controllers.attractions_controller import AttractionsController
from ..controllers.compilations_controller import CompilationsController


class AttractionViewSet(viewsets.ViewSet):
    """Simple ViewSet using MongoEngine queries via controllers/repositories.
    Implements common endpoints: list, retrieve, popular, search, sync_from_google, similar.
    """
    serializer_class = AttractionSerializer
    # Make public by default; protect only mutating endpoints explicitly
    permission_classes = [AllowAny]

    def list(self, request):
        try:
            # If no explicit search query or location provided, return popular results
            params = request.query_params
            q = params.get('q') or params.get('query')
            lat = params.get('lat') or params.get('latitude') or params.get('location')
            country = params.get('country')

            if not q and not lat:
                country = country or 'France'
                limit = int(params.get('limit', 20))
                qs = AttractionsController.popular_by_country(country, limit)
                if qs and isinstance(qs, list) and len(qs) and isinstance(qs[0], dict):
                    return Response(qs, status=status.HTTP_200_OK)
                attractions = list(qs)
                serializer = self.serializer_class(attractions, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)

            # Use search service for browsing — this will hit Google Places when no DB filters
            results = AttractionsController.search(request.query_params)
            # If service returned plain dicts (from Google Places mapping), return directly
            if results and isinstance(results, list) and len(results) and isinstance(results[0], dict):
                return Response(results, status=status.HTTP_200_OK)

            # Otherwise assume a queryset/list of documents
            attractions = list(results)
            serializer = self.serializer_class(attractions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            import traceback
            return Response({'error': str(e), 'details': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, pk=None):
        try:
            # Return details from Google (no DB persistence)
            details = AttractionsController.get_by_place_id(pk)
            if details:
                return Response(details, status=status.HTTP_200_OK)
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            import traceback
            return Response({'error': str(e), 'details': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def popular(self, request):
        try:
            country = request.query_params.get('country', 'France')
            limit = int(request.query_params.get('limit', 20))
            qs = AttractionsController.popular_by_country(country, limit)
            # popular_by_country returns mapped dicts from Google Places
            if qs and isinstance(qs, list) and len(qs) and isinstance(qs[0], dict):
                return Response(qs, status=status.HTTP_200_OK)
            attractions = list(qs)
            serializer = self.serializer_class(attractions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            import traceback
            return Response({'error': str(e), 'details': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def search(self, request):
        try:
            # If no query and no location provided, fall back to popular results to populate UI
            params = request.query_params
            q = params.get('q') or params.get('query')
            lat = params.get('lat') or params.get('latitude') or params.get('location')
            country = params.get('country')

            if not q and not lat:
                country = country or 'France'
                limit = int(params.get('limit', 20))
                qs = AttractionsController.popular_by_country(country, limit)
                if qs and isinstance(qs, list) and len(qs) and isinstance(qs[0], dict):
                    return Response(qs, status=status.HTTP_200_OK)
                attractions = list(qs)
                serializer = self.serializer_class(attractions, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)

            results = AttractionsController.search(request.query_params)
            if results and isinstance(results, list) and len(results) and isinstance(results[0], dict):
                return Response(results, status=status.HTTP_200_OK)
            attractions = list(results)
            serializer = self.serializer_class(attractions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            import traceback
            return Response({'error': str(e), 'details': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def sync_from_google(self, request):
        try:
            country = request.data.get('country', 'France')
            limit = int(request.data.get('limit', 20))
            synced, total = AttractionsController.sync_from_google(country, limit)
            if total == 0:
                return Response({'error': 'No places found'}, status=400)
            return Response({'message': f'Synced {synced} new attractions from Google Places', 'total_found': total})
        except Exception as e:
            import traceback
            return Response({'error': str(e), 'details': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def similar(self, request, pk=None):
        try:
            limit = int(request.query_params.get('limit', 10))
            # Use Google-only similar suggestions based on place details
            results = AttractionsController.similar_suggestions(pk, limit)
            return Response(results)
        except Exception as e:
            import traceback
            return Response({'error': str(e), 'details': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def save(self, request):
        try:
            place_id = request.data.get('place_id')
            if not place_id:
                return Response({'error': 'place_id required'}, status=status.HTTP_400_BAD_REQUEST)
            compilation_id = request.data.get('compilation_id')
            compilation_name = request.data.get('compilation_name')
            from ..controllers.attractions_controller import AttractionsController as AC
            compilation = AC.save_place_to_user(request.user, place_id, compilation_id=compilation_id, compilation_name=compilation_name)
            # Return JSON-safe compilation representation
            def sanitize(value):
                try:
                    import datetime
                    if getattr(value, '__class__', None) and value.__class__.__name__ == 'ObjectId':
                        return str(value)
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        return value
                    if isinstance(value, datetime.datetime):
                        return value.isoformat()
                    if isinstance(value, list):
                        return [sanitize(v) for v in value]
                    if isinstance(value, dict):
                        return {k: sanitize(v) for k, v in value.items()}
                except Exception:
                    return value
                return value

            from ..serializers import AttractionSerializer as AttSer
            items = []
            for it in getattr(compilation, 'items', []) or []:
                att_payload = None
                try:
                    if getattr(it, 'attraction', None) is not None:
                        att_payload = AttSer(it.attraction).data
                except Exception:
                    att_payload = None
                items.append(sanitize({
                    'attraction': att_payload,
                    'order_index': getattr(it, 'order_index', 0),
                    'added_at': getattr(it, 'added_at', None),
                }))

            payload = sanitize({
                'id': str(getattr(compilation, 'id', '')),
                'name': getattr(compilation, 'name', ''),
                'profile': getattr(compilation, 'profile', ''),
                'country': getattr(compilation, 'country', ''),
                'items': items,
                'created_at': getattr(compilation, 'created_at', None),
                'updated_at': getattr(compilation, 'updated_at', None),
            })
            return Response(payload, status=status.HTTP_201_CREATED)
        except PermissionError as pe:
            return Response({'error': str(pe)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            import traceback
            return Response({'error': str(e), 'details': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CompilationViewSet(viewsets.ViewSet):
    serializer_class = CompilationSerializer

    @staticmethod
    def _sanitize(value):
        try:
            import datetime
            # Convert Mongo ObjectId to string without importing bson
            if getattr(value, '__class__', None) and value.__class__.__name__ == 'ObjectId':
                return str(value)
            if isinstance(value, (str, int, float, bool)) or value is None:
                return value
            if isinstance(value, datetime.datetime):
                return value.isoformat()
            if isinstance(value, list):
                return [CompilationViewSet._sanitize(v) for v in value]
            if isinstance(value, dict):
                return {k: CompilationViewSet._sanitize(v) for k, v in value.items()}
        except Exception:
            return value
        return value

    @staticmethod
    def _to_safe_compilation_dict(comp):
        # Build a JSON-serializable dict with string ids and nested attraction payloads
        try:
            items = []
            for it in getattr(comp, 'items', []) or []:
                try:
                    from ..serializers import AttractionSerializer as AttSer
                    att_payload = AttSer(getattr(it, 'attraction', None)).data if getattr(it, 'attraction', None) else None
                except Exception:
                    att_payload = None
                item_dict = {
                    'attraction': att_payload,
                    'order_index': getattr(it, 'order_index', 0),
                    'added_at': getattr(it, 'added_at', None),
                }
                items.append(CompilationViewSet._sanitize(item_dict))
        except Exception:
            items = []

        payload = {
            'id': str(getattr(comp, 'id', '')),
            'name': getattr(comp, 'name', ''),
            'profile': getattr(comp, 'profile', ''),
            'country': getattr(comp, 'country', ''),
            'items': items,
            'created_at': getattr(comp, 'created_at', None),
            'updated_at': getattr(comp, 'updated_at', None),
        }
        # Include owner if present, but as string id
        try:
            owner = getattr(comp, 'owner', None)
            if owner is not None:
                payload['owner'] = str(getattr(owner, 'id', owner))
        except Exception:
            pass
        return CompilationViewSet._sanitize(payload)

    def list(self, request):
        try:
            # Only return compilations for the authenticated user
            user = getattr(request, 'user', None)
            if not user or not getattr(user, 'id', None):
                return Response([], status=status.HTTP_200_OK)
            qs = Compilation.objects(owner=user).order_by('-updated_at')
            comps = list(qs)
            # Manually serialize to avoid any ObjectId leakage
            data = [self._to_safe_compilation_dict(comp) for comp in comps]
            return Response(data)
        except Exception as e:
            import traceback
            return Response({'error': str(e), 'details': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, pk=None):
        try:
            user = getattr(request, 'user', None)
            comp = Compilation.objects.get(id=pk)
            # Enforce ownership
            try:
                if user and getattr(comp, 'owner', None) and str(getattr(comp.owner, 'id', '')) != str(getattr(user, 'id', '')):
                    return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
            except Exception:
                pass
            data = self._to_safe_compilation_dict(comp)
            return Response(data)
        except Exception as e:
            return Response({'error': 'Not found', 'details': str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        try:
            # Enforce ownership
            try:
                comp = Compilation.objects.get(id=pk)
                user = getattr(request, 'user', None)
                if user and getattr(comp, 'owner', None) and str(getattr(comp.owner, 'id', '')) != str(getattr(user, 'id', '')):
                    return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
            except Exception:
                pass
            data = CompilationsController.add_item(pk, request.data)
            return Response(data)
        except Exception as e:
            import traceback
            return Response({'error': str(e), 'details': traceback.format_exc()}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def remove_item(self, request, pk=None):
        try:
            # Enforce ownership
            try:
                comp = Compilation.objects.get(id=pk)
                user = getattr(request, 'user', None)
                if user and getattr(comp, 'owner', None) and str(getattr(comp.owner, 'id', '')) != str(getattr(user, 'id', '')):
                    return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
            except Exception:
                pass
            data = CompilationsController.remove_item(pk, request.data)
            return Response(data)
        except Exception as e:
            import traceback
            return Response({'error': str(e), 'details': traceback.format_exc()}, status=status.HTTP_400_BAD_REQUEST)


