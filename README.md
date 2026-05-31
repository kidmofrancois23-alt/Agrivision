# 🌿 AgriVision AI — Cameroun

Application mobile web Python (Flask) dédiée aux cultures agricoles du Cameroun.

## Fonctionnalités

| Module | Description |
|--------|-------------|
| 📷 Scanner | Caméra temps réel — diagnostic de maladies de plantes camerounaises |
| 🌦 Météo | Analyse climatique et impact sur les cultures par zone agro-écologique |
| 🤖 Conseil | Agent IA expert des cultures camerounaises — chat 24h/24 |

## Cultures gérées

Maïs, Manioc, Plantain, Igname, Macabo, Taro, Patate douce, Arachide, Sorgho, Mil, Riz,
Haricot, Tomate, Gombo, Aubergine africaine, Poivron, Piment, Oignon, Gingembre, Moringa,
Cacao, Café robusta, Café arabica, Palmier à huile, Coton, Hévéa, Canne à sucre,
Ananas, Papaye, Mangue, Avocat, Goyave, Orange, Safou, Poivre blanc de Penja, Ndolé, Eru…

## Lancement local

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Définir la clé API Anthropic
export ANTHROPIC_API_KEY=sk-ant-votre-cle

# 3. Lancer le serveur
python app.py

# 4. Ouvrir dans le navigateur
# http://localhost:5000
```

## Déploiement sur Render (gratuit)

1. Créer un compte sur https://render.com
2. New → Web Service → connecter votre dépôt GitHub
3. **Build Command** : `pip install -r requirements.txt`
4. **Start Command** : `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
5. Variables d'environnement → ajouter `ANTHROPIC_API_KEY`
6. Deploy → votre URL publique est prête

## Déploiement sur Railway

```bash
# Installer Railway CLI
npm install -g @railway/cli

# Déployer
railway login
railway init
railway up

# Ajouter la clé API dans Railway Dashboard → Variables
ANTHROPIC_API_KEY=sk-ant-votre-cle
```

## Structure du projet

```
agrivision_final/
├── app.py              # Serveur Flask — routes API
├── templates/
│   └── index.html      # Interface mobile PWA
├── requirements.txt    # Dépendances Python
├── Procfile            # Pour Heroku/Render
├── render.yaml         # Config Render automatique
└── README.md
```

## API Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `GET /` | GET | Interface mobile |
| `POST /api/diagnostic` | POST | Analyse image plante |
| `POST /api/meteo` | POST | Analyse météo agricole |
| `POST /api/conseil` | POST | Agent conseil culture |
| `GET /api/cultures` | GET | Liste cultures gérées |

### Exemple /api/diagnostic
```json
POST /api/diagnostic
Header: X-API-Key: sk-ant-...
Body: { "image": "<base64>", "mime": "image/jpeg" }

Réponse:
{ "type": "diagnostic", "etat": "malade", "texte": "## Plante identifiée..." }
{ "type": "non_plante",  "message": "C'est un animal" }
{ "type": "non_cameroun","message": "Blé détecté" }
```

## Crédit

PPE 212 | Groupe 25 membres | Chef de projet : NATOLO Junior | 2026
