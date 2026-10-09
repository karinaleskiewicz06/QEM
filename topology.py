"""Device topologies for the cross-topology routing study (plan_month_2.md, W1).

Single source of truth for the coupling maps of the three IQM tiers used in the
study, so ``noisy_sim`` / ``routing_sweep`` / ``run_hardware`` stop hardcoding the
5-qubit star:

  * **ODRA** (IQM Spark-class): 5-qubit **star**, hub = physical qubit 0.
  * **Garnet**: 20-qubit **square lattice** (4 x 5).
  * **Emerald**: 54-qubit **square lattice** (6 x 9).

A coupling map is a **bidirectional** list of ``[a, b]`` edges (Qiskit convention),
exactly what ``transpile(coupling_map=...)`` and ``AerSimulator(coupling_map=...)``
expect. ``star_coupling_map`` lives here now; ``noisy_sim`` re-exports it so existing
imports keep working and Month-1 behaviour is unchanged (the default device is ODRA).
"""

from __future__ import annotations

from collections import deque

CouplingMap = list[list[int]]


def star_coupling_map(num_qubits: int = 5, hub: int = 0) -> CouplingMap:
    """Bidirectional star coupling: every outer qubit connects only to the hub."""
    edges: CouplingMap = []
    for q in range(num_qubits):
        if q == hub:
            continue
        edges.append([hub, q])
        edges.append([q, hub])
    return edges


def grid_coupling_map(rows: int, cols: int) -> CouplingMap:
    """Bidirectional nearest-neighbour coupling on a ``rows`` x ``cols`` lattice.

    Physical qubit index is row-major: ``q = r * cols + c``. Each qubit connects
    to its right and down neighbours (both orientations added), giving the square
    lattice Garnet/Emerald expose (degree up to 4).
    """
    def idx(r: int, c: int) -> int:
        return r * cols + c

    edges: CouplingMap = []
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                a, b = idx(r, c), idx(r, c + 1)
                edges += [[a, b], [b, a]]
            if r + 1 < rows:
                a, b = idx(r, c), idx(r + 1, c)
                edges += [[a, b], [b, a]]
    return edges


# Device registry. ``hub`` is only meaningful for the star; grids carry rows/cols.
DEVICES: dict[str, dict] = {
    "odra": {"num_qubits": 5, "topology": "star", "hub": 0},
    "garnet": {"num_qubits": 20, "topology": "grid", "rows": 4, "cols": 5},
    "emerald": {"num_qubits": 54, "topology": "grid", "rows": 6, "cols": 9},
}
# ``star`` is an alias for the ODRA workhorse.
DEVICES["star"] = DEVICES["odra"]


def _resolve(name: str) -> dict:
    key = name.lower()
    if key not in DEVICES:
        raise ValueError(
            f"unknown device {name!r}; expected one of {sorted(DEVICES)}"
        )
    return DEVICES[key]


def device_num_qubits(name: str) -> int:
    """Number of physical qubits on the named device."""
    return _resolve(name)["num_qubits"]


def device_coupling_map(name: str) -> CouplingMap:
    """Coupling map for a named device (``odra``/``star``, ``garnet``, ``emerald``)."""
    spec = _resolve(name)
    if spec["topology"] == "star":
        return star_coupling_map(spec["num_qubits"], spec["hub"])
    return grid_coupling_map(spec["rows"], spec["cols"])


# Fixed, hand-picked physical placements for the locked 5-qubit VQC (W2).
# ``placement[logical] = physical``; logical 0 is the star pattern's hub, put at
# the centre of the compact cluster. ``optimal`` = a connected "plus" (hub +
# its 4 lattice neighbours, so the star pattern routes with zero SWAPs);
# ``adverse`` = a dispersed set (centre + the four lattice corners) that forces
# long routing. The star device has no layout freedom, so both are the identity.
PLACEMENTS: dict[str, dict[str, list[int]]] = {
    # ODRA 5q star: only one possible 5-qubit placement.
    "odra": {"optimal": [0, 1, 2, 3, 4], "adverse": [0, 1, 2, 3, 4]},
    # Garnet 4x5 grid (q = r*5 + c).
    #   optimal: centre (1,1)=6 + neighbours (0,1)=1,(2,1)=11,(1,0)=5,(1,2)=7
    #   adverse: centre (2,2)=12 + corners (0,0)=0,(0,4)=4,(3,0)=15,(3,4)=19
    "garnet": {"optimal": [6, 1, 11, 5, 7], "adverse": [12, 0, 4, 15, 19]},
    # Emerald 6x9 grid (q = r*9 + c).
    #   optimal: centre (2,4)=22 + neighbours (1,4)=13,(3,4)=31,(2,3)=21,(2,5)=23
    #   adverse: centre (2,4)=22 + corners (0,0)=0,(0,8)=8,(5,0)=45,(5,8)=53
    "emerald": {"optimal": [22, 13, 31, 21, 23], "adverse": [22, 0, 8, 45, 53]},
}
PLACEMENTS["star"] = PLACEMENTS["odra"]

PLACEMENT_STRATEGIES: tuple[str, ...] = ("optimal", "adverse")


def placement(device: str, n_logical: int = 5, strategy: str = "optimal") -> list[int]:
    """Physical qubits the ``n_logical`` VQC qubits map onto (an ``initial_layout``).

    ``strategy`` is ``optimal`` (compact cluster) or ``adverse`` (dispersed). Only
    the locked ``n_logical == 5`` placements are hand-picked; other sizes raise so
    a wrong layout can't slip through silently.
    """
    spec = _resolve(device)  # validates the device name
    key = device.lower()
    if strategy not in PLACEMENT_STRATEGIES:
        raise ValueError(
            f"unknown strategy {strategy!r}; expected {PLACEMENT_STRATEGIES}"
        )
    layout = PLACEMENTS[key][strategy]
    if n_logical != len(layout):
        raise ValueError(
            f"no hand-picked {strategy} placement for n_logical={n_logical} on "
            f"{device!r} (have {len(layout)}); add one to topology.PLACEMENTS."
        )
    if max(layout) >= spec["num_qubits"]:
        raise ValueError(f"placement {layout} out of range for {device!r}")
    return list(layout)


# Real-device placements — YOU fill these after inspecting the live backends
# (methodology_month_2.md §7). The idealized-grid PLACEMENTS above drive the
# simulator; on hardware the true connectivity is not a perfect grid, so hardware
# transpile uses the backend's live coupling map and these hand-picked physical
# qubit lists. Leave None until set; ``hardware_placement`` raises a clear error
# so an unfilled placement can never silently reach a real device.
HARDWARE_PLACEMENTS: dict[str, dict[str, list[int] | None]] = {
    # Locked from the LIVE Garnet coupling map (pull_garnet.py, 2026-08):
    #   optimal = compact plus, hub=QB3(idx3) + spokes 0,2,4,8 (all distance 1)
    #   adverse = dispersed across the device (min-pair spread 15)
    "garnet": {"optimal": [3, 0, 2, 4, 8], "adverse": [0, 16, 12, 5, 18]},
    # Emerald: CANDIDATES from derive_placements() on the idealized 54q map (2026-09-05) —
    #   optimal = compact cluster hub=10 (star 12 CZ, all_to_all 57 CZ)
    #   adverse = dispersed farthest-point set (star 75 CZ, all_to_all 129 CZ — highest routing)
    # PENDING live-hardware validation via the smoke-test before the full run; if the smoke fails
    # (a dead qubit / missing edge on the live map), re-derive from backend_coupling_map('emerald').
    "emerald": {"optimal": [10, 1, 9, 11, 19], "adverse": [0, 53, 6, 30, 45]},
    # ODRA (IQM Spark, 5q star): the 5-qubit logical circuit FILLS the device, so there is no
    # placement freedom at all — the layout is the identity and "adverse" does not exist. The
    # routing ladder on ODRA therefore comes entirely from the entanglement pattern
    # (star 12 CZ / linear 27 / circular 36 / all_to_all 54), not from placement.
    "odra": {"optimal": [0, 1, 2, 3, 4]},
    # code-block (4 data qubits) placements for the [[4,2,2]] arm:
    "garnet_qec": {"optimal": None, "adverse": None},
    "emerald_qec": {"optimal": None, "adverse": None},
}


def hardware_placement(device: str, strategy: str) -> list[int]:
    """Hand-picked physical qubits for a real device; raises if not yet filled.

    Validate against the backend's live coupling map at submit time (the ideal-grid
    ``placement`` is for the simulator only).
    """
    key = device.lower()
    if key not in HARDWARE_PLACEMENTS:
        raise ValueError(f"no hardware placement table for {device!r}; add one")
    if strategy not in HARDWARE_PLACEMENTS[key]:
        raise ValueError(f"unknown strategy {strategy!r} for {device!r}")
    layout = HARDWARE_PLACEMENTS[key][strategy]
    if layout is None:
        raise ValueError(
            f"HARDWARE_PLACEMENTS[{device!r}][{strategy!r}] is unset — fill it with "
            "real physical qubit indices from the live backend before submitting."
        )
    return list(layout)


def topological_distance(
    coupling_map: CouplingMap, num_qubits: int, a: int, b: int
) -> int:
    """Shortest-path (hop) distance between physical qubits ``a`` and ``b``.

    On a star an outer-outer pair is distance 2 (through the hub); on a grid it is
    the Manhattan distance. Used by W3 to relate layout choice to routing overhead.
    Returns ``-1`` if the qubits are on disconnected components.
    """
    if a == b:
        return 0
    # Treat the coupling map as UNDIRECTED: the live IQM map may list each edge only
    # once (one direction), so add both orientations or BFS spuriously can't traverse
    # back and reports -1. Our own star/grid maps are already bidirectional (harmless).
    adj: list[list[int]] = [[] for _ in range(num_qubits)]
    for u, v in coupling_map:
        adj[u].append(v)
        adj[v].append(u)
    seen = [False] * num_qubits
    seen[a] = True
    queue = deque([(a, 0)])
    while queue:
        node, dist = queue.popleft()
        for nb in adj[node]:
            if nb == b:
                return dist + 1
            if not seen[nb]:
                seen[nb] = True
                queue.append((nb, dist + 1))
    return -1


def _all_pairs_distance(coupling_map: CouplingMap, num_qubits: int) -> list[list[int]]:
    """All-pairs hop distance matrix (BFS from each node)."""
    return [[topological_distance(coupling_map, num_qubits, a, b)
             for b in range(num_qubits)] for a in range(num_qubits)]


def derive_placements(
    coupling_map: CouplingMap, num_qubits: int, n_logical: int = 5
) -> dict[str, list[int]]:
    """Pick optimal (compact) and adverse (dispersed) placements from a real map.

    Works on any coupling map (the live device is not a perfect grid). ``optimal``
    is the most compact connected cluster of ``n_logical`` qubits (min total pairwise
    hop-distance), with a high-degree hub placed at logical 0. ``adverse`` is a
    dispersed set from farthest-point sampling (max-min pairwise distance). Returns
    ``{"optimal": [...], "adverse": [...]}`` — hand-check, then lock into
    HARDWARE_PLACEMENTS.
    """
    D = _all_pairs_distance(coupling_map, num_qubits)
    reachable = lambda q, s: [c for c in s if D[q][c] >= 0]

    # --- optimal: most compact connected cluster of size n_logical ---
    best = None
    for hub in range(num_qubits):
        order = sorted((q for q in range(num_qubits) if D[hub][q] >= 0),
                       key=lambda q: D[hub][q])
        cluster = order[:n_logical]
        if len(cluster) < n_logical:
            continue
        spread = sum(D[a][b] for a in cluster for b in cluster)
        deg = sum(1 for q in range(num_qubits) if D[hub][q] == 1)
        # prefer small spread, tie-break on higher hub degree (better star native)
        score = (spread, -deg)
        if best is None or score < best[0]:
            ordered = [hub] + [q for q in cluster if q != hub]
            best = (score, ordered)
    optimal = best[1]

    # --- adverse: farthest-point sampling (dispersed) ---
    a0, b0 = max(
        ((a, b) for a in range(num_qubits) for b in range(num_qubits) if D[a][b] >= 0),
        key=lambda p: D[p[0]][p[1]],
    )
    chosen = [a0, b0]
    while len(chosen) < n_logical:
        rest = [q for q in range(num_qubits) if q not in chosen]
        nxt = max(rest, key=lambda q: min((D[q][c] for c in chosen if D[q][c] >= 0),
                                          default=-1))
        chosen.append(nxt)
    return {"optimal": list(optimal), "adverse": list(chosen)}


def _demo() -> None:
    for name in ("odra", "garnet", "emerald"):
        cm = device_coupling_map(name)
        n = device_num_qubits(name)
        deg = [0] * n
        for u, _ in cm:
            deg[u] += 1
        print(f"{name:>8}: {n:>2} qubits, {len(cm) // 2:>3} edges, "
              f"max degree {max(deg)}")


if __name__ == "__main__":
    _demo()
