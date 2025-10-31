TripExplorer – Backend (Django/DRF)

Stack
- Django 5 • Django REST Framework
- MongoEngine (MongoDB)
- SimpleJWT (auth)
- Google Places (recherche/détails) via googlemaps

Prérequis
- Python 3.11+
- MongoDB 6+
- Virtualenv recommandé

Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configuration
- Variables d’environnement (ex: .env ou export):
```
GOOGLE_PLACES_API_KEY=xxxxx
MONGODB_HOST=mongodb://localhost:27017/tripadvisor
```
- Paramètres DRF/JWT déjà configurés (voir backend/settings.py).

Lancement
```bash
python manage.py runserver 0.0.0.0:8000
# API: http://localhost:8000/api/
```

EndPoints (extraits)
- POST /api/auth/signup, /api/auth/signin
- GET /api/attractions/ (list/search/popular/similar)
- GET /api/attractions/{place_id}/ (détails)
- POST /api/attractions/save/ { place_id, compilation_id?, compilation_name? }
- GET /api/compilations/ (du user), POST /api/compilations/{id}/add_item, remove_item

Données & modèles
- User, Attraction, Compilation (+ CompilationItem).
- Normalisation: location → {lat,lng}; id stable = place_id.

Notes
- Si Google Places ne renvoie pas de détails complets, fallback minimal pour permettre l’ajout à une compilation.
- Le serializer tente de dériver photo_reference depuis raw_data.photos si absent.

Tests & Dev
- Activez le logging dans settings pour diagnostiquer.
- Pensez à lancer MongoDB avant l’API.


