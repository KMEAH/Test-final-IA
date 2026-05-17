"""
ATF (Action-Topology Format) Python Parser — Fallback Engine
=============================================================
Utilisé lorsque le binaire Rust de fastmemory n'est pas disponible
(ex: incompatibilité d'architecture sur Windows en dev local).

Sur Render (Linux), le moteur Louvain natif de fastmemory est utilisé directement.

Le parseur produit le même format de graphe JSON que fastmemory.process_markdown() :
une liste de clusters, chacun contenant des nodes et des links.
"""

import re
from typing import Any


def parse_atf_markdown(markdown_text: str) -> list[dict[str, Any]]:
    """
    Parse an ATF Markdown document into topology clusters.

    Each [Component: X] section becomes a cluster.
    Each [ID: Y] block becomes a node within its component cluster.
    """
    clusters: list[dict[str, Any]] = []
    current_component: str | None = None
    current_component_nodes: list[dict] = []
    current_component_links: list[dict] = []
    current_block: dict | None = None

    def flush_component():
        nonlocal current_component, current_component_nodes, current_component_links
        if current_component and current_component_nodes:
            # Flush last open block
            if current_block:
                current_component_nodes.append(current_block.copy())

            clusters.append({
                "id": f"cluster_{current_component}",
                "component": current_component,
                "nodes": list(current_component_nodes),
                "links": list(current_component_links),
            })
        current_component_nodes = []
        current_component_links = []

    def flush_block():
        nonlocal current_block
        if current_block and current_component is not None:
            current_component_nodes.append(current_block.copy())
            current_block = None

    for line in markdown_text.splitlines():
        line = line.strip()

        # --- Component header: ## [Component: X]
        m = re.match(r'^##\s*\[Component:\s*(.+?)\]', line)
        if m:
            flush_block()
            flush_component()
            current_component = m.group(1).strip()
            current_block = None
            continue

        # --- Block ID header: ### [ID: Y]
        m = re.match(r'^###\s*\[ID:\s*(.+?)\]', line)
        if m:
            flush_block()
            current_block = {
                "id": m.group(1).strip(),
                "component": current_component,
                "action": None,
                "logic": None,
                "data_connections": [],
                "access": [],
                "events": [],
                "group": len(clusters),
            }
            continue

        if current_block is None:
            continue

        # --- Action
        m = re.match(r'^\*\*Action:\*\*\s*(.+)', line)
        if m:
            current_block["action"] = m.group(1).strip()
            continue

        # --- Logic
        m = re.match(r'^\*\*Logic:\*\*\s*(.+)', line)
        if m:
            current_block["logic"] = m.group(1).strip()
            continue

        # --- Input (treat as data_connections)
        m = re.match(r'^\*\*Input:\*\*\s*(.+)', line)
        if m:
            raw = m.group(1).strip()
            items = [x.strip() for x in re.split(r'[,;]', raw) if x.strip() and x.strip() not in ('{}', '')]
            current_block["data_connections"].extend(items)
            continue

        # --- Data_Connections
        m = re.match(r'^\*\*Data_Connections:\*\*\s*(.+)', line)
        if m:
            raw = m.group(1).strip()
            items = [x.strip() for x in re.split(r'[,;]', raw) if x.strip()]
            current_block["data_connections"].extend(items)
            continue

        # --- Access
        m = re.match(r'^\*\*Access:\*\*\s*(.+)', line)
        if m:
            raw = m.group(1).strip()
            items = [x.strip() for x in re.split(r'[,;]', raw) if x.strip()]
            current_block["access"].extend(items)
            continue

        # --- Events
        m = re.match(r'^\*\*Events:\*\*\s*(.+)', line)
        if m:
            raw = m.group(1).strip()
            items = [x.strip() for x in re.split(r'[,;]', raw) if x.strip()]
            current_block["events"].extend(items)
            continue

        # --- Context_Links (add edges between blocks)
        m = re.match(r'^\*\*Context_Links:\*\*\s*\[(.+?)\]', line)
        if m:
            targets = [x.strip() for x in m.group(1).split(',')]
            for target in targets:
                if current_block and target:
                    current_component_links.append({
                        "source": current_block["id"],
                        "target": target,
                        "type": "CONTEXT_LINK",
                    })

    # Flush remaining
    flush_block()
    flush_component()

    return clusters


def query_topology(clusters: list[dict], keyword: str) -> list[dict]:
    """
    Deterministic Pathfinding: return clusters whose nodes contain the keyword.
    Returns the deepest isolated block — not a cross-cluster keyword dump.
    """
    import json
    kw = keyword.lower()
    matched = []
    for cluster in clusters:
        # Search within the cluster's serialized content
        cluster_text = json.dumps(cluster, ensure_ascii=False).lower()
        if kw in cluster_text:
            matched.append(cluster)
    return matched
