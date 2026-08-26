"""Tests for the device-topology layer (plan_month_2.md W1)."""

from __future__ import annotations

import pytest

from topology import (
    device_coupling_map,
    device_num_qubits,
    grid_coupling_map,
    placement,
    star_coupling_map,
    topological_distance,
)
from noisy_sim import DeviceCalibration


def _is_bidirectional(cm: list[list[int]]) -> bool:
    edges = {tuple(e) for e in cm}
    return all((b, a) in edges for a, b in edges)


# --- coupling map shape -----------------------------------------------------

def test_star_edges_and_hub_degree():
    cm = star_coupling_map(5, hub=0)
    assert len(cm) == 8  # 4 outer qubits, both orientations
    assert _is_bidirectional(cm)
    hub_out = sum(1 for a, _ in cm if a == 0)
    assert hub_out == 4


def test_grid_edge_count_matches_formula():
    # rows x cols lattice: rows*(cols-1) horizontal + (rows-1)*cols vertical
    cm = grid_coupling_map(4, 5)
    assert len(cm) // 2 == 4 * 4 + 3 * 5  # 31 undirected edges
    assert _is_bidirectional(cm)


@pytest.mark.parametrize(
    "name,n,edges",
    [("odra", 5, 4), ("garnet", 20, 31), ("emerald", 54, 93)],
)
def test_device_registry(name, n, edges):
    assert device_num_qubits(name) == n
    assert len(device_coupling_map(name)) // 2 == edges


def test_star_alias_is_odra():
    assert device_coupling_map("star") == device_coupling_map("odra")


def test_unknown_device_raises():
    with pytest.raises(ValueError):
        device_coupling_map("sycamore")


# --- topological distance ---------------------------------------------------

def test_star_outer_pair_distance_is_two():
    cm = star_coupling_map(5, hub=0)
    assert topological_distance(cm, 5, 1, 2) == 2  # through the hub
    assert topological_distance(cm, 5, 0, 3) == 1  # hub to outer
    assert topological_distance(cm, 5, 2, 2) == 0


def test_grid_distance_is_manhattan():
    cm = grid_coupling_map(4, 5)  # q = r*5 + c
    # (0,0)=0 to (3,4)=19 → Manhattan 3+4 = 7
    assert topological_distance(cm, 20, 0, 19) == 7
    # adjacent
    assert topological_distance(cm, 20, 0, 1) == 1


# --- fixed placements (W2) --------------------------------------------------

@pytest.mark.parametrize("device", ["garnet", "emerald"])
def test_optimal_placement_is_compact_plus(device):
    """Optimal layout = hub + its 4 lattice neighbours (all distance 1)."""
    cm = device_coupling_map(device)
    n = device_num_qubits(device)
    lay = placement(device, 5, "optimal")
    assert len(set(lay)) == 5  # distinct physical qubits
    dists = [topological_distance(cm, n, lay[0], lay[i]) for i in range(1, 5)]
    assert dists == [1, 1, 1, 1]


@pytest.mark.parametrize("device", ["garnet", "emerald"])
def test_adverse_placement_is_more_dispersed_than_optimal(device):
    cm = device_coupling_map(device)
    n = device_num_qubits(device)
    opt = placement(device, 5, "optimal")
    adv = placement(device, 5, "adverse")
    spread_opt = sum(topological_distance(cm, n, opt[0], opt[i]) for i in range(1, 5))
    spread_adv = sum(topological_distance(cm, n, adv[0], adv[i]) for i in range(1, 5))
    assert spread_adv > spread_opt


def test_star_has_no_placement_freedom():
    assert placement("odra", 5, "optimal") == placement("odra", 5, "adverse")


def test_placement_in_range():
    for device in ("odra", "garnet", "emerald"):
        n = device_num_qubits(device)
        for strat in ("optimal", "adverse"):
            assert max(placement(device, 5, strat)) < n


def test_placement_bad_size_and_strategy_raise():
    with pytest.raises(ValueError):
        placement("garnet", 4, "optimal")  # no hand-picked layout for n=4
    with pytest.raises(ValueError):
        placement("garnet", 5, "sideways")  # unknown strategy


# --- calibration integration ------------------------------------------------

def test_calibration_defaults_to_star():
    cal = DeviceCalibration()  # ODRA default
    assert cal.coupling_map == star_coupling_map(5, 0)


def test_calibration_accepts_lattice_coupling():
    cm = device_coupling_map("garnet")
    cal = DeviceCalibration(num_qubits=20, coupling_map=cm)
    assert cal.coupling_map == cm
    assert len(cal.t1) == 20 and len(cal.p_ro) == 20  # scalars broadcast
