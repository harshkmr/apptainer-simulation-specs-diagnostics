"""
Comprehensive pytest test suite for Apptainer simulation diagnostics benchmark.
Fully covers parsers, unit conversions, damping regime classifications,
evidence precedence resolution, and deterministic report generation.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path



from apptainer_diag.analyzer import (
    calculate_risk_scores,
    classify_damping_regime,
    convert_conductivity_to_m_per_sec,
    convert_flux_to_m3_per_sec,
    convert_head_to_meters,
    convert_time_to_seconds,
    resolve_evidence_precedence,
)
from apptainer_diag.models import (
    ContainerSpec,
    GdbBacktrace,
    ResidualRecord,
    SolverTrace,
    ValgrindSummary,
)
from apptainer_diag.parsers import (
    parse_apptainer_spec,
    parse_gdb_backtrace,
    parse_solver_residuals,
    parse_valgrind_summary,
)
from apptainer_diag.reporter import generate_diagnostic_report, serialize_report_to_json


def test_apptainer_spec_parsing():
    """Verify parsing of Apptainer spec resource limits, env vars, and base image."""
    content = """Bootstrap: docker
From: ubuntu:22.04

%environment
    export MEMORY_LIMIT_MB=4096
    export CPU_CORES=4
    export WALLTIME_SECONDS=3600

%labels
    Maintainer HydroLab
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".def") as f:
        f.write(content)
        temp_path = f.name

    try:
        spec = parse_apptainer_spec(temp_path)
        assert spec.base_image == "ubuntu:22.04"
        assert spec.memory_limit_mb == 4096.0
        assert spec.cpu_cores == 4.0
        assert spec.walltime_seconds == 3600.0
        assert spec.env_vars.get("MEMORY_LIMIT_MB") == "4096"
        assert spec.labels.get("Maintainer") == "HydroLab"
    finally:
        os.remove(temp_path)


def test_unit_conversions():
    """Verify physical unit conversions to SI base units (m, m3/s, m/s, s)."""
    # Pressure Head -> meters
    assert abs(convert_head_to_meters(10.0, "ft") - 3.048) < 1e-4
    assert abs(convert_head_to_meters(9806.65, "Pa") - 1.0) < 1e-4
    assert abs(convert_head_to_meters(1.0, "bar") - 10.1972) < 1e-3
    assert abs(convert_head_to_meters(1.0, "psi") - 0.70307) < 1e-4

    # Volumetric Flux -> m3/s
    assert abs(convert_flux_to_m3_per_sec(15850.32, "gpm") - 1.0) < 1e-4
    assert abs(convert_flux_to_m3_per_sec(1.0, "cfs") - 0.0283168) < 1e-6
    assert abs(convert_flux_to_m3_per_sec(86400.0, "m3/day") - 1.0) < 1e-5
    assert abs(convert_flux_to_m3_per_sec(60000.0, "L/min") - 1.0) < 1e-5

    # Conductivity K -> m/s
    assert abs(convert_conductivity_to_m_per_sec(86400.0, "m/day") - 1.0) < 1e-5
    assert abs(convert_conductivity_to_m_per_sec(283464.57, "ft/day") - 1.0) < 1e-4

    # Time -> seconds
    assert convert_time_to_seconds(1.0, "hours") == 3600.0
    assert convert_time_to_seconds(2.0, "days") == 172800.0


def test_all_five_solver_damping_regimes():
    """Verify classification of all five solver damping regimes."""
    # 1. Optimal Damping
    trace_opt = SolverTrace(
        filepath="",
        records=[
            ResidualRecord(
                iteration=i,
                time_step=1,
                dt_seconds=1.0,
                residual_head_m=1.0 / (10**i),
                residual_flux_m3_s=0.0,
                norm_ratio=1.0 / (10**i),
            )
            for i in range(1, 8)
        ],
        converged=True,
    )
    regime, risk, _ = classify_damping_regime(trace_opt)
    assert regime == "Optimal Damping"
    assert risk == 10.0

    # 2. Over-Damped Stagnation
    trace_stagnant = SolverTrace(
        filepath="",
        records=[
            ResidualRecord(
                iteration=i,
                time_step=1,
                dt_seconds=1.0,
                residual_head_m=0.5,
                residual_flux_m3_s=0.0,
                norm_ratio=0.99,
            )
            for i in range(1, 8)
        ],
        converged=False,
    )
    regime, risk, _ = classify_damping_regime(trace_stagnant)
    assert regime == "Over-Damped Stagnation"
    assert risk == 60.0

    # 3. Under-Damped Oscillation
    oscillating_ratios = [1.0, 1.25, 0.70, 1.30, 0.65, 1.20]
    trace_oscillating = SolverTrace(
        filepath="",
        records=[
            ResidualRecord(
                iteration=i + 1,
                time_step=1,
                dt_seconds=1.0,
                residual_head_m=r,
                residual_flux_m3_s=0.0,
                norm_ratio=r,
            )
            for i, r in enumerate(oscillating_ratios)
        ],
        converged=False,
    )
    regime, risk, _ = classify_damping_regime(trace_oscillating)
    assert regime == "Under-Damped Oscillation"
    assert risk == 75.0

    # 4. Incomplete / Slow Convergence
    trace_slow = SolverTrace(
        filepath="",
        records=[
            ResidualRecord(
                iteration=i,
                time_step=1,
                dt_seconds=1.0,
                residual_head_m=0.1,
                residual_flux_m3_s=0.0,
                norm_ratio=0.1,
            )
            for i in range(1, 4)
        ],
        converged=False,
    )
    regime, risk, _ = classify_damping_regime(trace_slow)
    assert regime == "Incomplete / Slow Convergence"
    assert risk == 50.0

    # 5. Divergent Damping Instability
    trace_div = SolverTrace(
        filepath="",
        records=[
            ResidualRecord(
                iteration=1,
                time_step=1,
                dt_seconds=1.0,
                residual_head_m=0.0,
                residual_flux_m3_s=0.0,
                norm_ratio=0.0,
                is_nan=True,
            )
        ],
        diverged=True,
    )
    regime, risk, _ = classify_damping_regime(trace_div)
    assert regime == "Divergent Damping Instability"
    assert risk == 100.0


def test_valgrind_memcheck_parser():
    """Verify parsing of Valgrind heap memory leak and error summaries."""
    content = """
==12345== LEAK SUMMARY:
==12345==    definitely lost: 4,096 bytes in 1 blocks
==12345==    possibly lost: 1,024 bytes in 1 blocks
==12345== Invalid write of size 8 at 0x401234
==12345== ERROR SUMMARY: 2 errors from 2 contexts
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write(content)
        temp_path = f.name

    try:
        valgrind = parse_valgrind_summary(temp_path)
        assert valgrind.definitely_lost_bytes == 4096
        assert valgrind.invalid_writes == 1
        assert valgrind.has_critical_memory_corruption is True
    finally:
        os.remove(temp_path)


def test_gdb_backtrace_parser():
    """Verify parsing of GDB backtrace crash signals and call stack frames."""
    content = """
Program received signal SIGSEGV, Segmentation fault.
#0  0x00007ffff7a12345 in petsc_solve (matrix=0x0) at petsc_wrapper.c:120
#1  0x0000000000401122 in main (argc=1, argv=0x7fffffffe000) at main.c:45
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write(content)
        temp_path = f.name

    try:
        gdb = parse_gdb_backtrace(temp_path)
        assert gdb.signal == "SIGSEGV"
        assert gdb.is_sigsegv is True
        assert len(gdb.frames) == 2
        assert gdb.frames[0].function == "petsc_solve"
    finally:
        os.remove(temp_path)


def test_precedence_tier_1_memory_safety_override():
    """Verify Tier 1: Valgrind memory corruption overrides downstream GDB SIGFPE / divergence."""
    spec = parse_apptainer_spec("")
    trace = parse_solver_residuals("")
    valgrind = parse_valgrind_summary("")
    gdb = parse_gdb_backtrace("")

    valgrind.invalid_writes = 2
    valgrind.has_critical_memory_corruption = True
    gdb.signal = "SIGFPE"
    gdb.is_sigfpe = True
    trace.diverged = True

    regime, _risk, _ = classify_damping_regime(trace)
    res = resolve_evidence_precedence(spec, trace, valgrind, gdb, regime)

    assert res["precedence_tier"] == 1
    assert res["root_cause"] == "Valgrind Memory Corruption (Invalid Write / Free)"
    assert res["valgrind_override_applied"] is True
    assert len(res["contradictions_resolved"]) > 0


def test_precedence_tier_2_container_oom():
    """Verify Tier 2: Container OOM / SIGKILL supercedes solver non-convergence."""
    spec = parse_apptainer_spec("")
    spec.memory_limit_mb = 4096.0
    trace = parse_solver_residuals("")
    trace.diverged = True
    valgrind = parse_valgrind_summary("")
    gdb = parse_gdb_backtrace("")
    gdb.signal = "SIGKILL"

    res = resolve_evidence_precedence(spec, trace, valgrind, gdb, "Sub-Optimal Damping")
    assert res["precedence_tier"] == 2
    assert res["root_cause"] == "Apptainer Container Resource Limit Exhaustion (OOM)"


def test_precedence_tier_3_gdb_sigfpe():
    """Verify Tier 3: GDB SIGFPE arithmetic exception when Valgrind is clean."""
    spec = parse_apptainer_spec("")
    trace = parse_solver_residuals("")
    valgrind = parse_valgrind_summary("")
    gdb = parse_gdb_backtrace("")
    gdb.signal = "SIGFPE"
    gdb.is_sigfpe = True

    res = resolve_evidence_precedence(spec, trace, valgrind, gdb, "Optimal Damping")
    assert res["precedence_tier"] == 3
    assert res["root_cause"] == "GDB SIGFPE Arithmetic Exception"


def test_precedence_tier_4_gdb_sigsegv():
    """Verify Tier 4: GDB SIGSEGV segmentation fault without Valgrind invalid writes."""
    spec = parse_apptainer_spec("")
    trace = parse_solver_residuals("")
    valgrind = parse_valgrind_summary("")
    gdb = parse_gdb_backtrace("")
    gdb.signal = "SIGSEGV"
    gdb.is_sigsegv = True

    res = resolve_evidence_precedence(spec, trace, valgrind, gdb, "Optimal Damping")
    assert res["precedence_tier"] == 4
    assert (
        res["root_cause"]
        == "Segmentation Fault (Null Pointer or Invalid Memory Reference)"
    )


def test_risk_scoring_formula():
    """Verify 45% / 40% / 15% weighted risk score calculation."""
    spec = ContainerSpec(filepath="")
    trace = SolverTrace(filepath="")
    valgrind = ValgrindSummary(
        filepath="", invalid_writes=1, has_critical_memory_corruption=True
    )
    gdb = GdbBacktrace(filepath="")

    scores = calculate_risk_scores(
        spec, trace, valgrind, gdb, "Incomplete / Slow Convergence", 50.0
    )
    expected_overall = (
        0.45 * scores.memory_safety_risk
        + 0.40 * scores.numerical_convergence_risk
        + 0.15 * scores.resource_constraint_risk
    )
    assert abs(scores.overall_score - round(expected_overall, 2)) < 0.01


def test_deterministic_json_report_and_values():
    """Verify that generated JSON diagnostic reports are key-sorted and value-accurate."""
    spec = ContainerSpec(filepath="Apptainer.def", memory_limit_mb=4096.0)
    trace = SolverTrace(filepath="solver.log", converged=True, total_iterations=10)
    valgrind = ValgrindSummary(filepath="valgrind.txt")
    gdb = GdbBacktrace(filepath="gdb.txt")

    report = generate_diagnostic_report(spec, trace, valgrind, gdb)
    json_1 = serialize_report_to_json(report)
    json_2 = serialize_report_to_json(report)

    # 1. Assert complete string identity
    assert json_1 == json_2

    # 2. Assert key-sorting at top level
    parsed = json.loads(json_1)
    assert list(parsed.keys()) == sorted(parsed.keys())

    # 3. Assert value correctness and key names
    assert parsed["risk_scores"]["risk_level"] == "LOW"
    assert parsed["solver_stability_summary"]["converged"] is True
    assert parsed["precedence_analysis"]["precedence_tier"] == 5
    assert "qualitative_assessment" in parsed
    assert "contradictions_resolved" in parsed["precedence_analysis"]


def test_setuptools_packaging_and_cli_entrypoint():
    """Verify setuptools package installation and apptainer-diag CLI entrypoint execution."""
    solution_dir = str(Path(__file__).parent.parent / "solution")
    assert os.path.exists(os.path.join(solution_dir, "setup.py"))

    # Test CLI invocation module fallback or installed script
    res = subprocess.run(
        [sys.executable, "-m", "apptainer_diag.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "apptainer" in res.stdout.lower() or "groundwater" in res.stdout.lower()
