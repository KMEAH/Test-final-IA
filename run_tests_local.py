"""
Test runner local — utilise le client ASGI httpx pour tester sans serveur réel.
"""
import asyncio
import json
import re

from httpx import AsyncClient, ASGITransport
from app import app, startup_event


async def run():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        await startup_event()

        # --- Health ---
        r = await client.get("/health")
        h = r.json()
        print(f"HEALTH: status={h['status']} | engine={h['engine']}")
        print(f"  Graphs: {h['graphs_loaded']}")

        print()

        # --- Build custom graph ---
        with open("data/knowledge_base.md", encoding="utf-8") as f:
            md = f.read()
        r = await client.post("/build", json={"markdown": md, "graph_id": "test_gvivva"})
        b = r.json()
        print(f"BUILD: {b['status']} | graph_id={b['graph_id']} | clusters={b['clusters_built']} | engine={b['engine']}")

        print()

        # --- Test cases ---
        tests = [
            ("remboursement", "module_rh_remboursement", "test_gvivva"),
            ("connexion", "module_it_connexion", "test_gvivva"),
            ("conge", "module_rh_conges", "test_gvivva"),
            ("facturation client externe fournisseur", None, "test_gvivva"),
            ("Je n'arrive pas a me connecter, quel est le processus pour mon remboursement",
             "module_rh_remboursement", "test_gvivva"),
        ]

        passed = 0
        for query, expected_id, gid in tests:
            r = await client.get("/query", params={"q": query, "graph_id": gid})
            data = r.json()
            result = data["pathfinding_result"]
            found_ids = re.findall(r'"id":\s*"([^"]+)"', json.dumps(result))

            if expected_id is None:
                ok = data["clusters_found"] == 0
            else:
                ok = expected_id in found_ids

            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            print(f"[{status}] '{query[:60]}...' " if len(query) > 60 else f"[{status}] '{query}'")
            print(f"       Expected: {expected_id or 'Out of Bound'} | Found IDs: {found_ids or data['clusters_found']}")

        print()
        print(f"Results: {passed}/{len(tests)} tests passed")

        # --- Detailed mixed query demo ---
        print()
        print("=" * 60)
        print("DEMO: Question mixte (connexion + remboursement)")
        print("=" * 60)
        q = "Je n'arrive pas a me connecter, quel est le processus pour mon remboursement"
        r = await client.get("/query", params={"q": q, "graph_id": "test_gvivva"})
        data = r.json()
        result = data["pathfinding_result"]
        found_ids = re.findall(r'"id":\s*"([^"]+)"', json.dumps(result))
        print(f"Clusters trouvés: {data['clusters_found']}")
        print(f"Block IDs retournés: {found_ids}")
        contaminated = any("module_it_connexion" in fid for fid in found_ids)
        if contaminated:
            print("CONTAMINATION detectee - module_it_connexion retourne aussi")
        else:
            print("OK: Pas de contamination cross-cluster - seul le bon bloc RH est retourne")


if __name__ == "__main__":
    asyncio.run(run())
