# FastMemory API — Test de Recrutement IA

Déploiement et évaluation de [FastMemory](https://github.com/fastbuilderai/memory) en tant que service REST sur PaaS, en remplacement du RAG classique.

---

## Choix Techniques

### PaaS : Render.com
- **Gratuit**, déploiement direct depuis GitHub, support Python natif et Docker.
- Région Frankfurt (latence optimale depuis la France).
- Health check automatique sur `/health`.

### Approche d'intégration : moteur topologique ATF
Sur **Render** (et en local Windows), le package `fastmemory` ne peut pas être compilé (Rust/maturin, FS read-only). Le serveur utilise **`atf_parser.py`** : parseur ATF + pathfinding déterministe, même format de graphe et mêmes endpoints que l'API FastMemory.

En local (optionnel) : `pip install -r requirements-dev.txt` pour tenter le moteur Rust natif.

### Serveur : FastAPI + Uvicorn
- API REST asynchrone, documentation Swagger auto-générée sur `/docs`.
- Graphe topologique chargé au démarrage depuis `data/knowledge_base.md`.
- Endpoints : `POST /build`, `GET /query`, `GET /graph/{id}`, `GET /health`.

---

## Structure du Projet

```
.
├── app.py                  # Serveur FastAPI wrappant fastmemory
├── requirements.txt        # Dépendances Python
├── Dockerfile              # Image Docker Python (PaaS / Docker Compose)
├── render.yaml             # Configuration Render.com (IaC)
├── test_client.py          # Script de validation détaillé
├── test_render_quick.py    # Script de validation PaaS (ASCII, Windows OK)
└── data/
    └── knowledge_base.md   # Base de connaissances ATF (RH + IT Gvivva Corp)
```

---

## Installation locale (venv)

```bash
# 1. Créer et activer l'environnement virtuel
python -m venv venv
# Windows
.\venv\Scripts\Activate.ps1
# Linux / macOS
source venv/bin/activate

# 2. Installer les dépendances (prod / Render)
pip install -r requirements.txt
# Optionnel — moteur Rust fastmemory en local :
# pip install -r requirements-dev.txt

# 3. Démarrer le serveur
uvicorn app:app --reload --port 8000
```

Le serveur est disponible sur `http://localhost:8000`.  
Documentation Swagger : `http://localhost:8000/docs`.

---

## Déploiement sur Render

1. Pusher ce dépôt sur GitHub.
2. Sur [render.com](https://render.com) → **New Web Service** → connecter le dépôt.
3. Render détecte `render.yaml` automatiquement.
4. Cliquer **Deploy**.

**URL publique (déployée) :** https://fastmemory-api.onrender.com

> **Plan gratuit Render — cold start**  
> Après une période d'inactivité (~15 min), la **première requête** peut prendre **~30 à 60 secondes** le temps que le service redémarre. C'est le comportement normal du plan gratuit ; les requêtes suivantes sont rapides.

---

## Étape 3 : Validation et script de test (livrable)

| Exigence du sujet | Fichier / action | Statut |
|---|---|---|
| Jeu de données ATF (règles métiers) | `data/knowledge_base.md` — 4 composants, 7 blocs (IT connexion/VPN, RH remboursement/formation, congés, sécurité) | Fait |
| Script client Python | `test_client.py` + `test_render_quick.py` (sortie ASCII, Windows) | Fait |
| 1. Envoyer les données au serveur PaaS | `POST /build` avec le contenu ATF (étape [1] des scripts) | Fait |
| 2. Requête complexe — Deterministic Pathfinding | Cas 3 : *« Je n'arrive pas à me connecter, quel est le processus pour mon remboursement ? »* → isole `module_rh_remboursement` sans mélanger `module_it_connexion` | Fait (validé 5/5 sur Render) |

**Commande de validation sur le PaaS :**

```bash
python test_render_quick.py https://fastmemory-api.onrender.com
```

---

## Exécuter le Script de Test

```bash
# Tester en local
python test_render_quick.py http://localhost:8000

# Tester le serveur PaaS déployé (recommandé sous Windows)
python test_render_quick.py https://fastmemory-api.onrender.com

# Alternative détaillée (peut afficher des erreurs d'encodage sous Windows)
python test_client.py --url https://fastmemory-api.onrender.com
```

### Résultat attendu

```
======================================================================
  FastMemory API — Suite de Tests de Validation
======================================================================
  Serveur cible : http://localhost:8000

[0] Health Check
  ✔  Serveur opérationnel — Engine: fastmemory (Rust/PyO3 Louvain clustering)

[1] Construction du graphe topologique
  ✔  Graphe 'test_gvivva' construit — N cluster(s) Louvain

[2] Tests de Deterministic Pathfinding

  ► Cas 1 — Remboursement de frais
    ✔  Bloc 'module_rh_remboursement' trouvé ✓

  ► Cas 2 — Problème de connexion
    ✔  Bloc 'module_it_connexion' trouvé ✓

  ► Cas 3 — Question mixte (le cas clé du test)
    ✔  Bloc 'module_rh_remboursement' trouvé ✓

  ► Cas 4 — Requête hors périmètre
    ✔  Clusters trouvés : 0 (attendu : 0)

  ► Cas 5 — Gestion des congés
    ✔  Bloc 'module_rh_conges' trouvé ✓
```

---

## Le Cas Clé : Question Mixte

> **"Je n'arrive pas à me connecter, quel est le processus pour mon remboursement ?"**

| Approche | Comportement |
|---|---|
| **RAG Classique** | Retourne des chunks liés à *connexion* ET *remboursement* simultanément → hallucination par mélange de contextes |
| **FastMemory** | Isole le bloc `module_rh_remboursement` via le graphe topologique Louvain → réponse déterministe, sans contamination |

FastMemory y parvient car les deux concepts sont dans des **Composants topologiques différents** (`Support_IT` vs `RH_Remboursements`). Le moteur Louvain les a clusterisés en communautés distinctes lors du build, rendant impossible toute contamination cross-cluster lors de la requête.

---

## API Endpoints

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Sanity check du serveur |
| `POST` | `/build` | Construire un graphe depuis un ATF Markdown |
| `GET` | `/query?q=...&graph_id=...` | Deterministic Pathfinding |
| `GET` | `/graph/{graph_id}` | Inspecter le graphe complet |
| `GET` | `/docs` | Documentation Swagger interactive |

---

## Exemple curl (PaaS)

```bash
# 1. Envoyer le jeu de données ATF au serveur
curl -X POST https://fastmemory-api.onrender.com/build \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{"graph_id": "test_gvivva", "markdown": "$(cat data/knowledge_base.md | sed 's/"/\\"/g')"}
EOF

# 2. Requête simple
curl "https://fastmemory-api.onrender.com/query?q=remboursement&graph_id=default"

# 3. Requête complexe (Deterministic Pathfinding — cas clé du sujet)
curl -G "https://fastmemory-api.onrender.com/query" \
  --data-urlencode "q=Je n'arrive pas a me connecter, quel est le processus pour mon remboursement" \
  --data-urlencode "graph_id=test_gvivva"
```

Sous PowerShell :

```powershell
# Health (attendre ~30s si cold start)
Invoke-RestMethod "https://fastmemory-api.onrender.com/health"

# Requête complexe
Invoke-RestMethod -Uri "https://fastmemory-api.onrender.com/query" -Body @{
  q = "Je n'arrive pas a me connecter, quel est le processus pour mon remboursement"
  graph_id = "default"
}
```
