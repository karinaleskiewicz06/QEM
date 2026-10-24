"""An Aer model of ODRA built from one calibration snapshot, with coherent error on top.

The question it exists to answer is *how much of the hardware's CDR failure is coherent*.
That needs a model whose total error budget is pinned to what the device reports, so
that turning up the coherent part changes the *kind* of error and not its *amount*.

Layers, per gate and qubit, all mapped through ``ODRA_PHYS`` (logical 0 = hub QB3):

* **thermal relaxation** from T1, T2 and the gate duration, on every ``r`` and ``cz``.
  Inside a gate the dephasing time is the Hahn-echo T2 by default, not Ramsey T2*:
  T2* is dominated by quasi-static frequency noise, whose decay over a 20-60 ns pulse
  is quadratic in time and negligible, while the exponential channel would charge it
  linearly. With T2* the thermal part alone exceeds the RB error of two PRX gates on
  2026-08-03; with echo T2 no gate is over budget at theta = 0 (``gate_t2="ramsey"``
  restores the other choice);
* **idle relaxation**: the native circuit is scheduled (ALAP by default, ASAP
  selectable) with the calibrated gate durations and every gap becomes a ``delay``
  carrying T1 and Ramsey T2* -- or echo T2 when the run uses dynamical decoupling
  (``dd=True``). The archived ODRA windows ran with DD off (``odra_backend.run_circuits``
  defaults to ``dd=False``). On the star the leaves wait while the hub works, so this is
  not a small term. How IQM's server actually places gates in time is not documented to
  us; the ALAP/ASAP difference is reported as a sensitivity, not assumed away;
* **coherent CZ error** ``RZZ(theta) . (RZ(phi) x RZ(phi))`` after every CZ;
* **depolarizing** on ``r`` and ``cz``, chosen so that the *total* average gate fidelity
  -- thermal + coherent + depolarizing -- equals the device's own per-gate number:
  randomized benchmarking of PRX (``metrics.rb.prx``) and interleaved RB of each CZ pair
  (``metrics.irb.cz``). RB sees coherent error too, so a model with ``theta > 0`` must
  not be *worse* than the device, only differently composed;
* **PRX over-rotation** ``r(a, phi) -> r(a (1 + eps), phi)``: an amplitude
  miscalibration, which scales with the angle. Aer cannot attach an angle-dependent
  error to a gate, so this is a rewrite of the circuit before simulation. It is left out
  of the fidelity budget: at ``eps = 0.01`` it costs ~1e-4 against an RB infidelity of
  ~1e-3;
* **asymmetric readout** ``e01``, ``e10`` per qubit from SSRO.

Why per-gate fidelities: ``collect_odra_calibration.py`` maps ``p_2q`` from the
*Clifford* RB of the pair (``metrics.rb.clifford.uz_cz``, F ~ 0.982), and a two-qubit
Clifford is ~1.5 CZ plus single-qubit gates. The CZ itself (IRB) is F ~ 0.992, so the
mapped ``p_2q`` overstates CZ error about 2.5x; ``p_1q`` is likewise a per-Clifford
number. The raw dump (``calibrations/odra_raw_*.json``) has the per-gate values; this
module reads them. A mapped file is accepted with a warning and treated as per-gate.

    from sim.device_model import build_noise_model
    dev = build_noise_model("calibrations/odra_raw_20260803.json", theta_zz=0.03)
    counts = dev.run([native_with_measure], shots=8192)

Reference point for the coherent term: ``spec/sim_cdr_variants_bench2.py`` (ODRA
23.07 constants; no RB matching, no idle, fixed CZ depolarizing 0.003).
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import re
import warnings
from typing import Any, Sequence

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Delay
from qiskit.circuit.library import RGate, RZGate, RZZGate
from qiskit.quantum_info import Operator, average_gate_fidelity
from qiskit.transpiler import InstructionDurations, PassManager
from qiskit.transpiler.passes import ALAPScheduleAnalysis, ASAPScheduleAnalysis, PadDelay
from qiskit_aer import AerSimulator
from qiskit_aer.noise import (NoiseModel, ReadoutError, RelaxationNoisePass,
                              coherent_unitary_error, depolarizing_error,
                              thermal_relaxation_error)

#: logical -> physical on ODRA; must equal ``run_hardware.PHYS``.
ODRA_PHYS: tuple[str, ...] = ("QB3", "QB1", "QB2", "QB4", "QB5")
HUB = 0
#: star edges in logical indices
STAR_EDGES: tuple[tuple[int, int], ...] = tuple((HUB, q) for q in range(1, 5))

#: scheduling resolution; IQM gate durations are whole nanoseconds
DT = 1e-9
#: only used to place the final measurements; idle *before* them is what matters
T_MEASURE = 1.5e-6

_IRB_CZ = re.compile(r"^metrics\.irb\.cz\.[^.]+\.(QB\d+)__(QB\d+)\.fidelity")
_RB_PRX = re.compile(r"^metrics\.rb\.prx\.[^.]+\.(QB\d+)\.fidelity")


# --------------------------------------------------------------------------- #
# Calibration                                                                    #
# --------------------------------------------------------------------------- #

@dataclasses.dataclass(frozen=True)
class OdraCalibration:
    """Per-gate numbers for the five logical qubits, already mapped through PHYS."""

    t1: np.ndarray            #: s
    t2: np.ndarray            #: s, Ramsey T2*
    t2_echo: np.ndarray       #: s, Hahn-echo T2
    t_prx: float              #: s
    t_cz: float               #: s
    f_prx: np.ndarray         #: RB average fidelity of one PRX, per qubit
    f_cz: dict                #: (hub, leaf) -> IRB average fidelity of the CZ
    e01: np.ndarray           #: P(read 1 | prepared 0)
    e10: np.ndarray           #: P(read 0 | prepared 1)
    source: str
    per_gate: bool            #: False when read from a mapped (per-Clifford) file

    @property
    def n_qubits(self) -> int:
        return len(self.t1)


def _physical(d: dict, phys: Sequence[str]) -> np.ndarray:
    return np.array([float(d[q]) for q in phys])


def load_calibration(path_or_dict: str | pathlib.Path | dict,
                     phys: Sequence[str] = ODRA_PHYS) -> OdraCalibration:
    """Read a ``collect_odra_calibration.py`` file -- raw dump preferred.

    The raw dump (``{"source", "url", "raw": {...}}``) carries per-qubit dicts keyed by
    physical name and the full observation set, from which the per-gate PRX RB and CZ
    IRB fidelities are taken. The mapped file (``num_qubits``, ``p_1q``, ``p_2q`` ...)
    has only per-Clifford numbers and symmetric readout; it is accepted with a warning.

    Raises:
        ValueError: if a required per-gate fidelity is missing or ambiguous.
    """
    if isinstance(path_or_dict, dict):
        d, src = path_or_dict, "<dict>"
    else:
        src = str(path_or_dict)
        d = json.loads(pathlib.Path(path_or_dict).read_text())
    if "raw" in d:
        return _from_raw(d["raw"], phys, src)
    return _from_mapped(d, src)


def _from_raw(raw: dict, phys: Sequence[str], src: str) -> OdraCalibration:
    obs = raw.get("observations", {})
    prx: dict[str, float] = {}
    cz: dict[frozenset, float] = {}
    for key, rec in obs.items():
        m = _RB_PRX.match(key)
        if m:
            if m.group(1) in prx:
                raise ValueError(f"two PRX RB fidelities for {m.group(1)} in {src}")
            prx[m.group(1)] = float(rec["value"])
        m = _IRB_CZ.match(key)
        if m:
            pair = frozenset(m.groups())
            if pair in cz:
                raise ValueError(f"two CZ IRB fidelities for {sorted(pair)} in {src}")
            cz[pair] = float(rec["value"])
    missing = [q for q in phys if q not in prx]
    if missing:
        raise ValueError(f"no metrics.rb.prx fidelity for {missing} in {src}")
    f_cz = {}
    for a, b in STAR_EDGES:
        pair = frozenset((phys[a], phys[b]))
        if pair not in cz:
            raise ValueError(f"no metrics.irb.cz fidelity for {sorted(pair)} in {src}")
        f_cz[(a, b)] = cz[pair]
    ro = raw["readout"]
    return OdraCalibration(
        t1=_physical(raw["t1"], phys), t2=_physical(raw["t2"], phys),
        t2_echo=_physical(raw.get("t2_echo") or raw["t2"], phys),
        t_prx=float(raw["t_1q"]), t_cz=float(raw["t_2q"]),
        f_prx=np.array([prx[q] for q in phys]), f_cz=f_cz,
        e01=np.array([float(ro[q]["error_0_to_1"]) for q in phys]),
        e10=np.array([float(ro[q]["error_1_to_0"]) for q in phys]),
        source=src, per_gate=True)


def _from_mapped(d: dict, src: str) -> OdraCalibration:
    warnings.warn(
        f"{src} is a mapped calibration: p_1q/p_2q are per-Clifford RB numbers and "
        "readout is symmetric. Using them as per-gate overstates gate error; prefer the "
        "raw dump (calibrations/odra_raw_*.json).", stacklevel=3)
    n = int(d["num_qubits"])
    p_ro = np.broadcast_to(np.asarray(d["p_ro"], float), (n,))
    return OdraCalibration(
        t1=np.asarray(d["t1"], float), t2=np.asarray(d["t2"], float),
        t2_echo=np.asarray(d.get("t2_echo", d["t2"]), float),
        t_prx=float(d["t_1q"]), t_cz=float(d["t_2q"]),
        f_prx=1.0 - np.broadcast_to(np.asarray(d["p_1q"], float), (n,)),
        f_cz={e: 1.0 - float(d["p_2q"]) for e in STAR_EDGES},
        e01=p_ro.copy(), e10=p_ro.copy(), source=src, per_gate=False)


# --------------------------------------------------------------------------- #
# Error budget                                                                   #
# --------------------------------------------------------------------------- #

def cz_coherent_unitary(theta_zz: float, phi_z: float) -> np.ndarray:
    """``exp(-i theta/2 Z x Z) . (RZ(phi) x RZ(phi))``."""
    u = Operator(RZZGate(theta_zz)).compose(
        Operator(RZGate(phi_z)).tensor(Operator(RZGate(phi_z))))
    return u.data


def match_depolarizing(base_error, target_fidelity: float, n_qubits: int):
    """Depolarizing parameter that brings ``base_error`` down to ``target_fidelity``.

    ``depol(p) o C = (1 - p) C + p R`` with ``R`` the replacement channel ``rho -> I/d``,
    whose average fidelity is ``1/d``, so the fidelity is linear in ``p``:
    ``F(p) = (1 - p) F_0 + p / d``.

    Returns:
        ``(p, f_without_depolarizing, exceeded)``. ``exceeded`` means thermal and
        coherent error alone are already below the target, so ``p = 0`` and the model
        is *worse* than the device at that gate.
    """
    d = 2 ** n_qubits
    f0 = float(average_gate_fidelity(base_error.to_quantumchannel()))
    if f0 <= target_fidelity:
        return 0.0, f0, bool(f0 < target_fidelity - 1e-12)
    p = (f0 - target_fidelity) / (f0 - 1.0 / d)
    return float(p), f0, False


@dataclasses.dataclass
class DeviceModel:
    """Noise model plus the two effects a NoiseModel cannot carry (idle, over-rotation)."""

    calibration: OdraCalibration
    theta_zz: float
    phi_z: float
    eps_prx: float
    with_idle: bool
    noise_model: NoiseModel
    budget: list[dict]          #: per gate: target and achieved fidelity, depolarizing p
    gate_t2: str = "echo"       #: dephasing time inside gates: "echo" or "ramsey"
    dd: bool = False            #: idle qubits dephase at echo T2 instead of T2*
    schedule: str = "alap"      #: "alap" or "asap"

    @property
    def tag(self) -> str:
        """Short identifier of every setting that changes the simulated counts."""
        stem = pathlib.Path(self.calibration.source).stem
        return (f"{stem}_th{self.theta_zz}_ph{self.phi_z}_eps{self.eps_prx}_g{self.gate_t2}"
                f"_{'idle-' + self.schedule if self.with_idle else 'noidle'}"
                f"{'_dd' if self.dd else ''}")

    # -- circuit preparation ---------------------------------------------- #

    def durations(self) -> InstructionDurations:
        cal = self.calibration
        return InstructionDurations(
            [("r", None, int(round(cal.t_prx / DT))),
             ("cz", None, int(round(cal.t_cz / DT))),
             ("measure", None, int(round(T_MEASURE / DT))),
             ("barrier", None, 0)], dt=DT)

    def over_rotate(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """``r(a, phi) -> r(a (1 + eps), phi)`` on every PRX; explicit ``id`` dropped.

        ``id`` is in the IQM basis list but is not a timed operation on the device, and
        idle time is modelled by the schedule, so it is removed rather than given noise.
        """
        out = circuit.copy_empty_like()
        for inst in circuit.data:
            op = inst.operation
            if op.name == "id":
                continue
            if op.name == "r" and self.eps_prx:
                a, phi = (float(x) for x in op.params)
                op = RGate(a * (1.0 + self.eps_prx), phi)
            out.append(op, inst.qubits, inst.clbits)
        return out

    def prepare(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """What actually goes to Aer: over-rotated, then scheduled with idle relaxation.

        The input must already be native (``r``, ``cz``, ``barrier``, ``measure``) on
        the five logical qubits; nothing is transpiled here, so the circuit that is
        simulated is gate for gate the circuit that would be submitted.
        """
        bad = sorted({i.operation.name for i in circuit.data}
                     - {"r", "cz", "barrier", "measure", "delay", "id"})
        if bad:
            raise ValueError(f"DeviceModel expects a native circuit; found {bad}")
        if circuit.num_qubits != self.calibration.n_qubits:
            raise ValueError(f"circuit has {circuit.num_qubits} qubits, model has "
                             f"{self.calibration.n_qubits}")
        out = self.over_rotate(circuit)
        out = _delays_in_dt(out)
        if self.with_idle:
            dur = self.durations()
            sched = ALAPScheduleAnalysis if self.schedule == "alap" else ASAPScheduleAnalysis
            out = PassManager([sched(dur), PadDelay(durations=dur)]).run(out)
            cal = self.calibration
            t2_idle = cal.t2_echo if self.dd else cal.t2
            out = RelaxationNoisePass(list(cal.t1), list(t2_idle), dt=DT,
                                      op_types=[Delay])(out)
        return out

    # -- execution ---------------------------------------------------------- #

    def simulator(self) -> AerSimulator:
        # experiments are independent, so let Aer spread a batch over the cores
        return AerSimulator(method="density_matrix", noise_model=self.noise_model,
                            max_parallel_experiments=0)

    def run(self, circuits: Sequence[QuantumCircuit], shots: int,
            seed: int | None = None) -> list[dict[str, int]]:
        """Counts for each circuit, in submission order, Qiskit bit order."""
        if not circuits:
            return []
        prepared = [self.prepare(c) for c in circuits]
        res = self.simulator().run(prepared, shots=int(shots), seed_simulator=seed).result()
        return [res.get_counts(i) for i in range(len(prepared))]

    def describe(self) -> str:
        lines = [f"device model: {self.calibration.source} | theta_zz={self.theta_zz} "
                 f"phi_z={self.phi_z} eps_prx={self.eps_prx} gate_t2={self.gate_t2} "
                 f"idle={self.schedule if self.with_idle else 'off'} dd={self.dd}"]
        for b in self.budget:
            lines.append(f"  {b['gate']:<3} {str(b['qubits']):<8} target F={b['f_target']:.5f} "
                         f"no-depol F={b['f_no_depol']:.5f} p_depol={b['p_depol']:.5f}"
                         + (f"  BUDGET EXCEEDED ({b['cause']})" if b["exceeded"] else ""))
        return "\n".join(lines)


def _delays_in_dt(circuit: QuantumCircuit) -> QuantumCircuit:
    """Rewrite delays given in seconds (P5 idle insertion) in units of :data:`DT`.

    The scheduler and the relaxation pass work in ``dt``; a delay already there is kept.
    """
    if not any(i.operation.name == "delay" and getattr(i.operation, "unit", "dt") != "dt"
               for i in circuit.data):
        return circuit
    from qem.identity_insertion import delay_seconds
    out = circuit.copy_empty_like()
    for inst in circuit.data:
        op = inst.operation
        if op.name == "delay" and getattr(op, "unit", "dt") != "dt":
            op = Delay(int(round(delay_seconds(op) / DT)), unit="dt")
        out.append(op, inst.qubits, inst.clbits)
    return out


def build_noise_model(calibration: str | pathlib.Path | dict | OdraCalibration,
                      theta_zz: float = 0.0, phi_z: float = 0.0, eps_prx: float = 0.0,
                      *, with_idle: bool = True, gate_t2: str = "echo", dd: bool = False,
                      schedule: str = "alap") -> DeviceModel:
    """Build the device model for one calibration and one coherent-error setting.

    Args:
        calibration: path to a ``collect_odra_calibration.py`` JSON (raw dump
            preferred), its parsed dict, or an :class:`OdraCalibration`.
        theta_zz: ZZ angle of the coherent CZ error, rad.
        phi_z: single-qubit Z angle of the coherent CZ error, rad, on both qubits.
        eps_prx: relative PRX over-rotation.
        with_idle: schedule circuits and relax idle qubits.
        gate_t2: dephasing time inside gates, ``"echo"`` (default) or ``"ramsey"``.
        dd: idle qubits dephase at echo T2 (dynamical decoupling on).
        schedule: ``"alap"`` or ``"asap"``.

    Returns:
        A :class:`DeviceModel`. Its ``budget`` lists, for every gate, the target
        fidelity, the fidelity without depolarizing and the depolarizing parameter;
        ``exceeded`` marks gates where thermal (and, for CZ, coherent) error alone
        already exceeds the device's error, and ``cause`` says which.
    """
    if gate_t2 not in ("echo", "ramsey"):
        raise ValueError(f"gate_t2 must be 'echo' or 'ramsey'; got {gate_t2!r}")
    if schedule not in ("alap", "asap"):
        raise ValueError(f"schedule must be 'alap' or 'asap'; got {schedule!r}")
    cal = (calibration if isinstance(calibration, OdraCalibration)
           else load_calibration(calibration))
    t2g = cal.t2_echo if gate_t2 == "echo" else cal.t2
    nm = NoiseModel(basis_gates=["r", "cz"])
    budget = []

    thermal_prx = [thermal_relaxation_error(cal.t1[q], t2g[q], cal.t_prx)
                   for q in range(cal.n_qubits)]
    for q in range(cal.n_qubits):
        p, f0, ex = match_depolarizing(thermal_prx[q], cal.f_prx[q], 1)
        nm.add_quantum_error(thermal_prx[q].compose(depolarizing_error(p, 1)), "r", [q])
        nm.add_readout_error(ReadoutError([[1 - cal.e01[q], cal.e01[q]],
                                           [cal.e10[q], 1 - cal.e10[q]]]), [q])
        budget.append({"gate": "r", "qubits": (q,), "f_target": float(cal.f_prx[q]),
                       "f_no_depol": f0, "p_depol": p, "exceeded": bool(ex),
                       "cause": "thermal" if ex else ""})

    coherent = (coherent_unitary_error(cz_coherent_unitary(theta_zz, phi_z))
                if (theta_zz or phi_z) else None)
    for (a, b) in STAR_EDGES:
        for qa, qb in ((a, b), (b, a)):
            # tensor order: the second operand acts on the first listed qubit
            thermal = thermal_relaxation_error(cal.t1[qb], t2g[qb], cal.t_cz).tensor(
                thermal_relaxation_error(cal.t1[qa], t2g[qa], cal.t_cz))
            base = thermal if coherent is None else thermal.compose(coherent)
            p, f0, ex = match_depolarizing(base, cal.f_cz[(a, b)], 2)
            nm.add_quantum_error(base.compose(depolarizing_error(p, 2)), "cz", [qa, qb])
            if qa == a:
                thermal_only = match_depolarizing(thermal, cal.f_cz[(a, b)], 2)[2]
                budget.append({"gate": "cz", "qubits": (a, b),
                               "f_target": float(cal.f_cz[(a, b)]), "f_no_depol": f0,
                               "p_depol": p, "exceeded": bool(ex),
                               "cause": ("thermal" if thermal_only else "coherent") if ex else ""})
    over = [b for b in budget if b["exceeded"]]
    if over:
        gates = ", ".join(f"{b['gate']}{list(b['qubits'])} ({b['cause']}, "
                          f"{b['f_target'] - b['f_no_depol']:.1e})" for b in over)
        warnings.warn(f"the model is worse than the calibration on {gates}: the listed "
                      f"error alone exceeds the measured infidelity "
                      f"(theta_zz={theta_zz}, phi_z={phi_z}, gate_t2={gate_t2})",
                      stacklevel=2)
    return DeviceModel(calibration=cal, theta_zz=float(theta_zz), phi_z=float(phi_z),
                       eps_prx=float(eps_prx), with_idle=bool(with_idle), noise_model=nm,
                       budget=budget, gate_t2=gate_t2, dd=bool(dd), schedule=schedule)


# --------------------------------------------------------------------------- #
# CLI plumbing shared by the runners                                             #
# --------------------------------------------------------------------------- #

def add_arguments(ap) -> None:
    """``--sim-device CAL`` and the coherent-error knobs, identical in every runner."""
    g = ap.add_argument_group("device-calibrated simulator (P7)")
    g.add_argument("--sim-device", default=None, metavar="CALIBRATION_JSON",
                   help="run on sim.device_model built from this calibration (raw dump "
                        "preferred) instead of hardware; implies a simulated run")
    g.add_argument("--sim-theta", type=float, default=0.0,
                   help="coherent ZZ angle on every CZ, rad (inside the IRB budget)")
    g.add_argument("--sim-phi", type=float, default=0.0,
                   help="coherent single-qubit Z angle on every CZ, rad")
    g.add_argument("--sim-eps", type=float, default=0.0,
                   help="relative PRX over-rotation")
    g.add_argument("--sim-no-idle", action="store_true",
                   help="omit idle relaxation (ablation)")
    g.add_argument("--sim-schedule", choices=["alap", "asap"], default="alap",
                   help="how gates are placed in time for idle relaxation")
    g.add_argument("--sim-gate-t2", choices=["echo", "ramsey"], default="echo",
                   help="dephasing time used inside gates")


def from_args(args, device: str = "odra", *, dd: bool = False) -> DeviceModel | None:
    """The model requested on the command line, or None.

    Raises:
        SystemExit: with ``--submit`` (a simulated run must not reach hardware), or for
            a device other than ODRA (the model is the five-qubit star).
    """
    if not getattr(args, "sim_device", None):
        return None
    if getattr(args, "submit", False):
        raise SystemExit("--sim-device and --submit are mutually exclusive")
    if device != "odra":
        raise SystemExit(f"--sim-device models ODRA's star only; got --device {device}")
    return build_noise_model(args.sim_device, args.sim_theta, args.sim_phi, args.sim_eps,
                             with_idle=not args.sim_no_idle,
                             gate_t2=getattr(args, "sim_gate_t2", "echo"),
                             schedule=getattr(args, "sim_schedule", "alap"), dd=dd)


def manifest_entry(dev: DeviceModel) -> dict[str, Any]:
    """What a run's manifest should record about the model."""
    return {"calibration": dev.calibration.source, "per_gate": dev.calibration.per_gate,
            "theta_zz": dev.theta_zz, "phi_z": dev.phi_z, "eps_prx": dev.eps_prx,
            "with_idle": dev.with_idle, "schedule": dev.schedule, "gate_t2": dev.gate_t2,
            "dd": dev.dd, "tag": dev.tag,
            "budget": [{**b, "qubits": list(b["qubits"])} for b in dev.budget]}
