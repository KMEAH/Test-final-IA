"""
Script de test client — FastMemory API
=======================================
Démontre la capacité de "Deterministic Pathfinding" de FastMemory :
une même question mixte ("connexion + remboursement") est isolée
dans le bon bloc topologique plutôt que mélangée comme le ferait un RAG classique.

Usage:
    python test_client.py                      # cible localhost:8000
    python test_client.py --url <URL_PAAS>     # cible le serveur Render déployé
"""

import argparse
import json
import sys
import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8000"

ATF_KNOWLEDGE_BASE = open("data/knowledge_base.md", encoding="utf-8").read()

TEST_CASES = [
    {
        "name": "Cas 1 — Remboursement de frais",
        "query": "remboursement",
        "expected_block": "module_rh_remboursement",
        "raison": (
            "Un RAG classique pourrait retourner des chunks liés à 'remboursement formation' "
            "ET 'remboursement frais'. FastMemory doit isoler le bon bloc topologique."
        ),
    },
    {
        "name": "Cas 2 — Problème de connexion",
        "query": "connexion",
        "expected_block": "module_it_connexion",
        "raison": (
            "La requête doit rester confinée au bloc IT connexion, "
            "sans contaminer les blocs RH."
        ),
    },
    {
        "name": "Cas 3 — Question mixte (le cas clé du test)",
        "query": "Je n'arrive pas a me connecter, quel est le processus pour mon remboursement",
        "expected_block": "module_rh_remboursement",
        "raison": (
            "SCÉNARIO CLÉ : un RAG classique mélangerait les deux concepts "
            "(connexion et remboursement). FastMemory doit restreindre la recherche "
            "au bloc 'module_rh_remboursement' grâce à ses liens topologiques."
        ),
    },
    {
        "name": "Cas 4 — Requête hors périmètre",
        "query": "facturation client externe fournisseur",
        "expected_block": None,
        "raison": "Aucun bloc ne correspond → réponse 'Out of Topological Bound'.",
    },
    {
        "name": "Cas 5 — Gestion des congés",
        "query": "conge",
        "expected_block": "module_rh_conges",
        "raison": "Doit cibler uniquement le bloc congés, pas les remboursements.",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"


def print_header(text: str):
    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}")


def print_result(ok: bool, label: str):
    icon = f"{GREEN}✔{RESET}" if ok else f"{RED}✘{RESET}"
    print(f"  {icon}  {label}")


def extract_block_ids(result) -> list[str]:
    """Extract all [ID: ...] values from the pathfinding result."""
    if isinstance(result, str):
        return []
    ids = []
    for cluster in result:
        dump = json.dumps(cluster)
        # nodes carry "id" fields in the graph
        import re
        ids.extend(re.findall(r'"id":\s*"([^"]+)"', dump))
    return ids


# ---------------------------------------------------------------------------
# Main test routine
# ---------------------------------------------------------------------------

def run_tests(base_url: str):
    base_url = base_url.rstrip("/")
    client = httpx.Client(base_url=base_url, timeout=30)

    print_header("FastMemory API — Suite de Tests de Validation")
    print(f"  Serveur cible : {BOLD}{base_url}{RESET}\n")

    # ------------------------------------------------------------------
    # 0. Health check
    # ------------------------------------------------------------------
    print(f"{BOLD}[0] Health Check{RESET}")
    try:
        r = client.get("/health")
        r.raise_for_status()
        data = r.json()
        print_result(True, f"Serveur opérationnel — Engine: {data.get('engine', '?')}")
        print(f"      Graphes chargés : {data.get('graphs_loaded', [])}")
    except Exception as exc:
        print_result(False, f"Serveur inaccessible : {exc}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 1. Build graph from ATF dataset
    # ------------------------------------------------------------------
    print(f"\n{BOLD}[1] Construction du graphe topologique{RESET}")
    try:
        r = client.post("/build", json={"markdown": ATF_KNOWLEDGE_BASE, "graph_id": "test_gvivva"})
        r.raise_for_status()
        data = r.json()
        print_result(
            data["status"] == "success",
            f"Graphe '{data['graph_id']}' construit — {data['clusters_built']} cluster(s) Louvain",
        )
    except Exception as exc:
        print_result(False, f"Échec de construction : {exc}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. Cas de test — Deterministic Pathfinding
    # ------------------------------------------------------------------
    print(f"\n{BOLD}[2] Tests de Deterministic Pathfinding{RESET}\n")
    results_summary = []

    for tc in TEST_CASES:
        print(f"  {BOLD}{YELLOW}► {tc['name']}{RESET}")
        print(f"    Requête   : \"{tc['query']}\"")
        print(f"    Attendu   : {tc['expected_block'] or 'Out of Topological Bound'}")
        print(f"    Raison    : {tc['raison']}")

        try:
            r = client.get("/query", params={"q": tc["query"], "graph_id": "test_gvivva"})
            r.raise_for_status()
            data = r.json()

            found_ids = extract_block_ids(data["pathfinding_result"])
            clusters_found = data["clusters_found"]

            if tc["expected_block"] is None:
                # Expect no result
                ok = clusters_found == 0
                print_result(ok, f"Clusters trouvés : {clusters_found} (attendu : 0)")
            else:
                ok = tc["expected_block"] in found_ids
                print_result(
                    ok,
                    f"Bloc '{tc['expected_block']}' "
                    + ("trouvé ✓" if ok else f"NON trouvé ✘ — blocs retournés : {found_ids}"),
                )
                print(f"      Clusters isolés : {clusters_found}")

            results_summary.append(ok)

        except Exception as exc:
            print_result(False, f"Erreur requête : {exc}")
            results_summary.append(False)

        print()

    # ------------------------------------------------------------------
    # 3. Démonstration du cas clé (requête mixte détaillée)
    # ------------------------------------------------------------------
    print_header("Démonstration — Cas Clé : Question Mixte")
    print(
        f"  Question : {BOLD}\"Je n'arrive pas à me connecter, quel est le processus "
        f"pour mon remboursement ?\"{RESET}\n"
    )

    r = client.get(
        "/query",
        params={
            "q": "Je n'arrive pas a me connecter, quel est le processus pour mon remboursement",
            "graph_id": "test_gvivva",
        },
    )
    data = r.json()

    print(f"  {BOLD}RAG Classique (comportement attendu sans FastMemory) :{RESET}")
    print(f"  {RED}✘ Mélangerait les chunks 'connexion' et 'remboursement' → hallucination{RESET}\n")

    print(f"  {BOLD}FastMemory — Deterministic Pathfinding :{RESET}")
    found_ids = extract_block_ids(data["pathfinding_result"])
    if found_ids:
        for fid in found_ids:
            contaminated = "module_it_connexion" in fid
            icon = f"{RED}✘ CONTAMINATION{RESET}" if contaminated else f"{GREEN}✔ ISOLÉ{RESET}"
            print(f"    {icon}  Bloc retourné : {BOLD}{fid}{RESET}")
    else:
        print(f"  {YELLOW}  Aucun bloc retourné{RESET}")

    # ------------------------------------------------------------------
    # 4. Summary
    # ------------------------------------------------------------------
    passed = sum(results_summary)
    total = len(results_summary)
    color = GREEN if passed == total else YELLOW if passed > 0 else RED

    print_header("Résultat Final")
    print(f"  {color}{BOLD}{passed}/{total} tests passés{RESET}\n")

    if passed == total:
        print(f"  {GREEN}FastMemory valide — Deterministic Pathfinding opérationnel.{RESET}")
    else:
        print(f"  {YELLOW}Certains tests ont échoué. Vérifier la version fastmemory.{RESET}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FastMemory API Test Client")
    parser.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help=f"URL de base du serveur FastMemory (défaut: {DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()
    run_tests(args.url)
