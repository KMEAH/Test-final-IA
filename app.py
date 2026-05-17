"""
FastMemory API Server — Gvivva Recruitment Test
================================================
Wraps the fastmemory Python module (PyO3/Rust) behind a FastAPI REST server.

Engine priority:
  1. fastmemory.process_markdown()  — Rust/Louvain native (si pip install fastmemory OK)
  2. atf_parser.parse_atf_markdown() — Parseur ATF Python (Render / Windows / PaaS)
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine detection
# ---------------------------------------------------------------------------

try:
    import fastmemory as _fm

    def _test_engine() -> bool:
        result = _fm.process_markdown("## [ID: probe]\n**Action:** Test\n")
        return isinstance(result, str) and len(result) > 2

    _USE_NATIVE = _test_engine()
except Exception:
    _USE_NATIVE = False

if _USE_NATIVE:
    logger.info("Engine: fastmemory native (Rust/Louvain)")
else:
    logger.info(
        "Using Python ATF topology engine (fastmemory optional — "
        "install via requirements-dev.txt for local Rust engine)."
    )
    from atf_parser import parse_atf_markdown, query_topology


def build_topology(markdown_text: str) -> list[dict[str, Any]]:
    """Build topology graph from ATF Markdown — native or fallback."""
    if _USE_NATIVE:
        raw = _fm.process_markdown(markdown_text)
        return json.loads(raw)
    return parse_atf_markdown(markdown_text)


def search_topology(graph: list[dict], keyword: str) -> list[dict]:
    """
    Deterministic Pathfinding: return the isolated cluster(s) containing the concept.

    For multi-word queries (natural language), the function:
    1. Tries exact phrase match first.
    2. Falls back to per-word scoring: each cluster is scored by how many
       query words appear in it. Only the highest-scoring cluster(s) are returned.
       Matches in node IDs / Action fields are weighted 3× vs logic text matches.

    This prevents cross-cluster contamination: a query mixing "connexion" and
    "remboursement" resolves to the cluster with the highest total relevance score.
    """
    kw_full = keyword.lower()
    words = [w for w in re.split(r'\W+', kw_full) if len(w) > 3]

    # --- Pass 1: exact phrase ---
    exact = [c for c in graph if kw_full in json.dumps(c, ensure_ascii=False).lower()]
    if exact:
        return exact

    # --- Pass 2: per-word scoring ---
    scores: list[tuple[int, dict]] = []
    for cluster in graph:
        cluster_json = json.dumps(cluster, ensure_ascii=False).lower()
        score = 0
        for word in words:
            if word in cluster_json:
                # Higher weight for matches in node IDs or action names
                id_text = " ".join(
                    n.get("id", "") + " " + (n.get("action") or "")
                    for n in cluster.get("nodes", [])
                ).lower()
                score += 3 if word in id_text else 1
        scores.append((score, cluster))

    if not scores:
        return []

    max_score = max(s for s, _ in scores)
    if max_score == 0:
        return []

    # Return only clusters that reach the top score (topological isolation)
    return [c for s, c in scores if s == max_score]


# ---------------------------------------------------------------------------
# App & config
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FastMemory API Server",
    description=(
        "API REST wrappant FastMemory (Louvain clustering Rust/PyO3) "
        "pour remplacer le RAG classique par un graphe de mémoire topologique déterministe."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory graph store: graph_id -> list of clusters
graph_store: dict[str, list] = {}

DEFAULT_GRAPH_ID = "default"
DEFAULT_DATA_PATH = Path(__file__).parent / "data" / "knowledge_base.md"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class BuildRequest(BaseModel):
    markdown: str
    graph_id: str = DEFAULT_GRAPH_ID

    model_config = {
        "json_schema_extra": {
            "example": {
                "graph_id": "demo",
                "markdown": (
                    "## [Component: RH]\n"
                    "### [ID: remboursement]\n"
                    "**Action:** Traiter_Remboursement\n"
                    "**Logic:** Soumettre la NDF avant le 25 du mois.\n"
                    "**Access:** Role_Employee\n"
                    "**Events:** NDF_Soumise\n"
                ),
            }
        }
    }


class BuildResponse(BaseModel):
    status: str
    graph_id: str
    clusters_built: int
    engine: str


class QueryResponse(BaseModel):
    query: str
    graph_id: str
    clusters_found: int
    pathfinding_result: list | str


# ---------------------------------------------------------------------------
# Startup: pre-load default knowledge base
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    if DEFAULT_DATA_PATH.exists():
        try:
            markdown_text = DEFAULT_DATA_PATH.read_text(encoding="utf-8")
            graph_store[DEFAULT_GRAPH_ID] = build_topology(markdown_text)
            n = len(graph_store[DEFAULT_GRAPH_ID])
            logger.info("Default KB loaded: %d clusters (graph_id='default')", n)
        except Exception as exc:
            logger.warning("Could not pre-load default KB: %s", exc)
    else:
        logger.warning("Default KB not found at %s", DEFAULT_DATA_PATH)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Monitoring"])
async def health_check():
    """Sanity check — retourne le statut du serveur et le moteur actif."""
    return {
        "status": "ok",
        "engine": "fastmemory native (Rust/Louvain)" if _USE_NATIVE else "Python ATF fallback",
        "graphs_loaded": list(graph_store.keys()),
        "clusters": {gid: len(g) for gid, g in graph_store.items()},
    }


@app.post("/build", response_model=BuildResponse, tags=["Graph Management"])
async def build_graph(request: BuildRequest):
    """
    Construire un graphe de mémoire topologique depuis un document ATF Markdown.
    Le graphe est stocké en mémoire sous `graph_id`.
    """
    try:
        graph = build_topology(request.markdown)
        graph_store[request.graph_id] = graph
        return BuildResponse(
            status="success",
            graph_id=request.graph_id,
            clusters_built=len(graph),
            engine="native" if _USE_NATIVE else "python-fallback",
        )
    except Exception as exc:
        logger.error("Build failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Graph build error: {exc}")


@app.get("/query", response_model=QueryResponse, tags=["Query"])
async def query_graph(
    q: str = Query(..., description="Mot-clé ou concept à rechercher dans le graphe"),
    graph_id: str = Query(DEFAULT_GRAPH_ID, description="Identifiant du graphe cible"),
):
    """
    **Deterministic Pathfinding** — requête topologique.

    Contrairement au RAG classique (similarité cosinus sur tous les chunks),
    FastMemory retourne le *bloc logique isolé* contenant le concept,
    évitant toute contamination inter-cluster.

    Exemple : `remboursement` retourne UNIQUEMENT le bloc RH Remboursement,
    et NON le bloc IT Connexion — même si les deux mentionnent "processus".
    """
    if graph_id not in graph_store:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Graph '{graph_id}' introuvable. "
                "POST /build d'abord, ou utilisez graph_id='default'."
            ),
        )

    matched = search_topology(graph_store[graph_id], q)

    if not matched:
        return QueryResponse(
            query=q,
            graph_id=graph_id,
            clusters_found=0,
            pathfinding_result="Out of Topological Bound: No matching logic block found.",
        )

    return QueryResponse(
        query=q,
        graph_id=graph_id,
        clusters_found=len(matched),
        pathfinding_result=matched,
    )


@app.get("/graph/{graph_id}", tags=["Graph Management"])
async def get_graph(graph_id: str):
    """Retourner le graphe topologique complet pour inspection."""
    if graph_id not in graph_store:
        raise HTTPException(status_code=404, detail=f"Graph '{graph_id}' introuvable.")
    return {
        "graph_id": graph_id,
        "engine": "native" if _USE_NATIVE else "python-fallback",
        "clusters": len(graph_store[graph_id]),
        "topology": graph_store[graph_id],
    }
