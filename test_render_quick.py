"""Quick test against Render deployment (ASCII output for Windows)."""
import json
import re
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://fastmemory-api.onrender.com"
client = httpx.Client(base_url=BASE.rstrip("/"), timeout=90.0)

r = client.get("/health")
print("HEALTH:", r.status_code, r.json())

md = open("data/knowledge_base.md", encoding="utf-8").read()
r = client.post("/build", json={"markdown": md, "graph_id": "test_gvivva"})
print("BUILD:", r.status_code, r.json())

tests = [
    ("remboursement", "module_rh_remboursement"),
    ("connexion", "module_it_connexion"),
    ("conge", "module_rh_conges"),
    ("facturation client externe", None),
]
passed = 0
for q, expected in tests:
    r = client.get("/query", params={"q": q, "graph_id": "test_gvivva"})
    data = r.json()
    ids = re.findall(r'"id":\s*"([^"]+)"', json.dumps(data.get("pathfinding_result", "")))
    ok = data["clusters_found"] == 0 if expected is None else expected in ids
    passed += int(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {q}")

q = "Je n'arrive pas a me connecter, quel est le processus pour mon remboursement"
r = client.get("/query", params={"q": q, "graph_id": "test_gvivva"})
data = r.json()
ids = re.findall(r'"id":\s*"([^"]+)"', json.dumps(data.get("pathfinding_result", "")))
ok = "module_rh_remboursement" in ids
passed += int(ok)
print(f"[{'PASS' if ok else 'FAIL'}] question mixte (clusters={data['clusters_found']})")

print(f"\nResult: {passed}/5 tests passed")
print(f"API URL: {BASE}")
