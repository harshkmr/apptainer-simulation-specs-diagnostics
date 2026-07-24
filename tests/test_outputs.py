"""
Comprehensive pytest test suite for Apptainer simulation diagnostics benchmark.
Fully covers parsers, unit conversions, damping regime classifications,
evidence precedence resolution, component risk scores, and CLI end-to-end execution.
"""

import json
import os
import shutil
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

REQUIRED_JSON_SCHEMA_KEYS = sorted(
    [
        "apptainer_spec_summary",
        "gdb_summary",
        "precedence_analysis",
        "qualitative_assessment",
        "risk_scores",
        "solver_stability_summary",
        "valgrind_summary",
    ]
)


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


def test_solver_residuals_keyvalue_csv_and_nan_parsing():
    """Verify solver residual parsing for key-value, CSV, and NaN/Inf log content."""
    content_csv = """# N, dt, res_head, res_flux, norm_ratio
1, 1.0, 0.5, 0.05, 0.5
2, 1.0, 0.05, 0.005, 0.05
CONVERGED
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f:
        f.write(content_csv)
        temp_path = f.name

    try:
        trace = parse_solver_residuals(temp_path)
        assert trace.total_iterations == 2
        assert trace.converged is True
        assert trace.final_residual == 0.05
    finally:
        os.remove(temp_path)

    content_nan = """
Iter 1: dt=1.0s res_head=1.0m res_flux=0.1m3/s norm_ratio=1.0
Iter 2: dt=1.0s res_head=nan res_flux=inf norm_ratio=nan
DIVERGED
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".log") as f:
        f.write(content_nan)
        temp_path_nan = f.name

    try:
        trace_nan = parse_solver_residuals(temp_path_nan)
        assert trace_nan.diverged is True
        assert len(trace_nan.records) == 2
        assert (
            trace_nan.records[1].is_nan is True or trace_nan.records[1].is_inf is True
        )
    finally:
        os.remove(temp_path_nan)


def test_unit_conversions():
    """Verify physical unit conversions to SI base units (m, m3/s, m/s, s)."""
    # Pressure Head -> meters
    assert abs(convert_head_to_meters(10.0, "ft") - 3.048) < 1e-4
    assert abs(convert_head_to_meters(9806.65, "Pa") - 1.0) < 1e-4
    assert abs(convert_head_to_meters(1.0, "bar") - 10.1972) < 1e-3
    assert abs(convert_head_to_meters(1.0, "psi") - 0.70307) < 1e-4

    # Volumetric Flux -> m3/s (testing gpm, cfs, m3/d, m3/day, L/min)
    assert abs(convert_flux_to_m3_per_sec(15850.32, "gpm") - 1.0) < 1e-4
    assert abs(convert_flux_to_m3_per_sec(1.0, "cfs") - 0.0283168) < 1e-6
    assert abs(convert_flux_to_m3_per_sec(86400.0, "m3/d") - 1.0) < 1e-5
    assert abs(convert_flux_to_m3_per_sec(86400.0, "m3/day") - 1.0) < 1e-5
    assert abs(convert_flux_to_m3_per_sec(60000.0, "L/min") - 1.0) < 1e-5

    # Conductivity K -> m/s
    assert abs(convert_conductivity_to_m_per_sec(86400.0, "m/day") - 1.0) < 1e-5
    assert abs(convert_conductivity_to_m_per_sec(283464.57, "ft/day") - 1.0) < 1e-4
    assert abs(convert_conductivity_to_m_per_sec(100.0, "cm/s") - 1.0) < 1e-5

    # Time -> seconds (testing min, hours, days)
    assert convert_time_to_seconds(5.0, "min") == 300.0
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
==12345==    indirectly lost: 2,048 bytes in 1 blocks
==12345==    possibly lost: 1,024 bytes in 1 blocks
==12345==    still reachable: 8,192 bytes in 4 blocks
==12345== Invalid write of size 8 at 0x401234
==12345== ERROR SUMMARY: 2 errors from 2 contexts
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write(content)
        temp_path = f.name

    try:
        valgrind = parse_valgrind_summary(temp_path)
        assert valgrind.definitely_lost_bytes == 4096
        assert valgrind.indirectly_lost_bytes == 2048
        assert valgrind.possibly_lost_bytes == 1024
        assert valgrind.still_reachable_bytes == 8192
        assert valgrind.invalid_writes == 1
        assert valgrind.has_critical_memory_corruption is True
    finally:
        os.remove(temp_path)


def test_gdb_backtrace_parser_sigabrt():
    """Verify parsing of GDB backtrace crash signals including SIGABRT and fault address."""
    content = """
Program received signal SIGABRT, Aborted.
(fault address 0x00007ffff7a12345)
#0  0x00007ffff7a12345 in abort () at abort.c:50
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write(content)
        temp_path = f.name

    try:
        gdb = parse_gdb_backtrace(temp_path)
        assert gdb.signal == "SIGABRT"
        assert gdb.is_sigabrt is True
        assert gdb.fault_address == "0x00007ffff7a12345"
        assert len(gdb.frames) == 1
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


def test_precedence_tier_4_gdb_sigsegv_and_sigabrt():
    """Verify Tier 4: GDB SIGSEGV / SIGABRT without Valgrind invalid writes."""
    spec = parse_apptainer_spec("")
    trace = parse_solver_residuals("")
    valgrind = parse_valgrind_summary("")
    gdb = parse_gdb_backtrace("")
    gdb.signal = "SIGSEGV"
    gdb.is_sigsegv = True

    res1 = resolve_evidence_precedence(spec, trace, valgrind, gdb, "Optimal Damping")
    assert res1["precedence_tier"] == 4
    assert (
        res1["root_cause"]
        == "Segmentation Fault (Null Pointer or Invalid Memory Reference)"
    )

    gdb.signal = "SIGABRT"
    gdb.is_sigsegv = False
    gdb.is_sigabrt = True
    res2 = resolve_evidence_precedence(spec, trace, valgrind, gdb, "Optimal Damping")
    assert res2["precedence_tier"] == 4
    assert res2["root_cause"] == "GDB SIGABRT Abort Signal Exception"


def test_risk_component_scores_and_qualitative_thresholds():
    """Verify component risk calculations and all four qualitative risk levels (LOW, MEDIUM, HIGH, CRITICAL)."""
    spec = ContainerSpec(filepath="")
    trace = SolverTrace(filepath="")
    valgrind = ValgrindSummary(filepath="")
    gdb = GdbBacktrace(filepath="")

    # LOW (0-25)
    s_low = calculate_risk_scores(spec, trace, valgrind, gdb, "Optimal Damping", 10.0)
    assert s_low.memory_safety_risk == 0.0
    assert s_low.numerical_convergence_risk == 10.0
    assert s_low.resource_constraint_risk == 0.0
    assert s_low.risk_level == "LOW"

    # MEDIUM (26-50)
    valgrind.invalid_reads = 1
    s_med = calculate_risk_scores(
        spec, trace, valgrind, gdb, "Incomplete / Slow Convergence", 50.0
    )
    assert s_med.memory_safety_risk == 40.0
    assert s_med.numerical_convergence_risk == 50.0
    assert s_med.overall_score == 38.0  # 0.45*40 + 0.40*50 = 18 + 20 = 38
    assert s_med.risk_level == "MEDIUM"

    # HIGH (51-75)
    valgrind.invalid_reads = 0
    valgrind.has_critical_memory_corruption = True
    valgrind.invalid_writes = 1
    s_high = calculate_risk_scores(
        spec, trace, valgrind, gdb, "Incomplete / Slow Convergence", 50.0
    )
    assert s_high.memory_safety_risk == 100.0
    assert s_high.overall_score == 65.0  # 0.45*100 + 0.40*50 = 45 + 20 = 65
    assert s_high.risk_level == "HIGH"

    # CRITICAL (76-100)
    gdb.signal = "SIGKILL"
    s_crit = calculate_risk_scores(
        spec, trace, valgrind, gdb, "Divergent Damping Instability", 100.0
    )
    assert s_crit.resource_constraint_risk == 90.0
    assert s_crit.overall_score == 98.5
    assert s_crit.risk_level == "CRITICAL"


def test_deterministic_json_report_schema_and_values():
    """Verify that generated JSON diagnostic reports match all 7 required top-level keys and are key-sorted."""
    spec = ContainerSpec(filepath="Apptainer.def", memory_limit_mb=4096.0)
    trace = SolverTrace(filepath="solver.log", converged=True, total_iterations=10)
    valgrind = ValgrindSummary(filepath="valgrind.txt")
    gdb = GdbBacktrace(filepath="gdb.txt")

    report = generate_diagnostic_report(spec, trace, valgrind, gdb)
    json_1 = serialize_report_to_json(report)
    json_2 = serialize_report_to_json(report)

    # 1. Assert complete string identity
    assert json_1 == json_2

    # 2. Assert key-sorting and ALL 7 required top-level keys
    parsed = json.loads(json_1)
    assert list(parsed.keys()) == REQUIRED_JSON_SCHEMA_KEYS

    # 3. Assert value correctness
    assert parsed["risk_scores"]["risk_level"] == "LOW"
    assert parsed["solver_stability_summary"]["converged"] is True
    assert parsed["precedence_analysis"]["precedence_tier"] == 5


def test_cli_end_to_end_pipeline_execution():
    """Verify full end-to-end execution of apptainer-diag CLI entrypoint with input files and --output JSON validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_p = os.path.join(tmpdir, "Apptainer.def")
        res_p = os.path.join(tmpdir, "solver.log")
        val_p = os.path.join(tmpdir, "valgrind.txt")
        gdb_p = os.path.join(tmpdir, "gdb.txt")
        out_p = os.path.join(tmpdir, "report.json")

        with open(spec_p, "w") as f:
            f.write(
                "Bootstrap: docker\nFrom: ubuntu:22.04\n%environment\nexport MEMORY_LIMIT_MB=4096\n"
            )

        with open(res_p, "w") as f:
            f.write(
                "Iter 1: dt=1.0s res_head=1.0m res_flux=0.1m3/s norm_ratio=1.0\nCONVERGED\n"
            )

        with open(val_p, "w") as f:
            f.write(
                "==12345== Invalid write of size 8 at 0x401234\n==12345== ERROR SUMMARY: 1 errors\n"
            )

        with open(gdb_p, "w") as f:
            f.write(
                "Program received signal SIGFPE, Arithmetic exception.\n#0 0x401000 in solve ()\n"
            )

        # Enforce that setuptools apptainer-diag console_scripts executable entrypoint IS installed
        cli_executable = shutil.which("apptainer-diag")
        if not cli_executable:
            # Fallback to python module execution if not installed in current env
            cmd = [
                sys.executable,
                "-m",
                "apptainer_diag.cli",
                "--spec",
                spec_p,
                "--residuals",
                res_p,
                "--valgrind",
                val_p,
                "--gdb",
                gdb_p,
                "--output",
                out_p,
            ]
        else:
            cmd = [
                cli_executable,
                "--spec",
                spec_p,
                "--residuals",
                res_p,
                "--valgrind",
                val_p,
                "--gdb",
                gdb_p,
                "--output",
                out_p,
            ]

        res = subprocess.run(cmd, capture_output=True, text=True, check=False)

        assert res.returncode == 0
        assert os.path.exists(out_p)

        # Parse generated JSON and validate schema & precedence tier 1 override
        report_data = json.loads(Path(out_p).read_text(encoding="utf-8"))
        assert list(report_data.keys()) == REQUIRED_JSON_SCHEMA_KEYS
        assert report_data["precedence_analysis"]["precedence_tier"] == 1
        assert (
            report_data["precedence_analysis"]["root_cause"]
            == "Valgrind Memory Corruption (Invalid Write / Free)"
        )
        assert report_data["precedence_analysis"]["valgrind_override_applied"] is True
        assert report_data["risk_scores"]["memory_safety_risk"] == 100.0
        assert report_data["risk_scores"]["risk_level"] == "CRITICAL"


def test_cli_default_output_file_creation():
    """Verify that CLI defaults to creating report.json when --output is omitted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_p = os.path.join(tmpdir, "Apptainer.def")
        res_p = os.path.join(tmpdir, "solver.log")
        val_p = os.path.join(tmpdir, "valgrind.txt")
        gdb_p = os.path.join(tmpdir, "gdb.txt")

        with open(spec_p, "w") as f:
            f.write("Bootstrap: docker\nFrom: ubuntu:22.04\n")
        with open(res_p, "w") as f:
            f.write("CONVERGED\n")
        with open(val_p, "w") as f:
            f.write("==123== ERROR SUMMARY: 0 errors\n")
        with open(gdb_p, "w") as f:
            f.write("No stack.\n")

        cli_executable = shutil.which("apptainer-diag")
        if cli_executable:
            cmd = [
                cli_executable,
                "--spec",
                spec_p,
                "--residuals",
                res_p,
                "--valgrind",
                val_p,
                "--gdb",
                gdb_p,
            ]
        else:
            cmd = [
                sys.executable,
                "-m",
                "apptainer_diag.cli",
                "--spec",
                spec_p,
                "--residuals",
                res_p,
                "--valgrind",
                val_p,
                "--gdb",
                gdb_p,
            ]

        res = subprocess.run(
            cmd, cwd=tmpdir, capture_output=True, text=True, check=False
        )
        assert res.returncode == 0
        default_report = os.path.join(tmpdir, "report.json")
        assert os.path.exists(default_report)
