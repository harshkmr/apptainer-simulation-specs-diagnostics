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

from apptainer_diag.analyzer import calculate_risk_scores
from apptainer_diag.models import (
    ContainerSpec,
    GdbBacktrace,
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

REQUIRED_SUBKEYS = {
    "apptainer_spec_summary": [
        "base_image",
        "cpu_cores",
        "environment_vars",
        "filepath",
        "labels",
        "memory_limit_mb",
        "walltime_seconds",
    ],
    "solver_stability_summary": [
        "converged",
        "damping_factor",
        "damping_regime",
        "diverged",
        "filepath",
        "final_residual_norm",
        "initial_residual_norm",
        "regime_explanation",
        "total_iterations",
    ],
    "valgrind_summary": [
        "definitely_lost_bytes",
        "filepath",
        "has_critical_memory_corruption",
        "indirectly_lost_bytes",
        "invalid_frees",
        "invalid_reads",
        "invalid_writes",
        "possibly_lost_bytes",
        "still_reachable_bytes",
        "total_errors",
        "uninitialized_reads",
    ],
    "gdb_summary": [
        "crash_thread",
        "fault_address",
        "filepath",
        "frames",
        "is_sigabrt",
        "is_sigfpe",
        "is_sigsegv",
        "signal",
    ],
    "precedence_analysis": [
        "contradictions_resolved",
        "precedence_tier",
        "rationale",
        "root_cause",
        "valgrind_override_applied",
    ],
    "risk_scores": [
        "memory_safety_risk",
        "numerical_convergence_risk",
        "overall_score",
        "resource_constraint_risk",
        "risk_level",
    ],
}


def test_apptainer_spec_parsing_def_and_json():
    """Verify parsing of Apptainer spec in both .def text format and JSON format."""
    content_def = """Bootstrap: docker
From: ubuntu:22.04

%environment
    export MEMORY_LIMIT_MB=4096
    export CPU_CORES=4
    export WALLTIME_SECONDS=3600

%labels
    Maintainer HydroLab
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".def") as f:
        f.write(content_def)
        temp_path_def = f.name

    try:
        spec = parse_apptainer_spec(temp_path_def)
        assert spec.base_image == "ubuntu:22.04"
        assert spec.memory_limit_mb == 4096.0
        assert spec.cpu_cores == 4.0
        assert spec.walltime_seconds == 3600.0
        assert spec.env_vars.get("MEMORY_LIMIT_MB") == "4096"
        assert spec.labels.get("Maintainer") == "HydroLab"
    finally:
        os.remove(temp_path_def)

    content_json = json.dumps(
        {
            "base_image": "ubuntu:22.04",
            "memory_limit_mb": 4096.0,
            "cpu_cores": 4.0,
            "walltime_seconds": 3600.0,
            "environment_vars": {"MEMORY_LIMIT_MB": "4096"},
            "labels": {"Maintainer": "HydroLab"},
        }
    )
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
        f.write(content_json)
        temp_path_json = f.name

    try:
        spec_json = parse_apptainer_spec(temp_path_json)
        assert spec_json.base_image == "ubuntu:22.04"
        assert spec_json.memory_limit_mb == 4096.0
        assert spec_json.cpu_cores == 4.0
        assert spec_json.walltime_seconds == 3600.0
        assert spec_json.env_vars.get("MEMORY_LIMIT_MB") == "4096"
    finally:
        os.remove(temp_path_json)


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





def test_deterministic_json_report_schema_and_subkeys():
    """Verify that generated JSON diagnostic reports match all 7 required top-level keys AND all nested sub-keys."""
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

    # 3. Assert all nested sub-keys for all sections
    for section, expected_keys in REQUIRED_SUBKEYS.items():
        assert sorted(parsed[section].keys()) == sorted(expected_keys)

    # 4. Assert value correctness
    assert parsed["risk_scores"]["risk_level"] == "LOW"
    assert parsed["solver_stability_summary"]["converged"] is True
    assert parsed["solver_stability_summary"]["damping_factor"] == trace.damping_factor
    assert parsed["precedence_analysis"]["precedence_tier"] == 5

    # 5. Assert qualitative_assessment is a non-empty list of meaningful strings
    qa = parsed["qualitative_assessment"]
    assert isinstance(qa, list)
    assert len(qa) > 0
    assert all(isinstance(s, str) and len(s) > 10 for s in qa)


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

        extra_paths = [
            os.path.expanduser("~/.local/bin"),
            sys.prefix + "/bin",
            "/usr/local/bin",
        ]
        search_path = os.path.pathsep.join(extra_paths + [os.environ.get("PATH", "")])
        cli_executable = shutil.which("apptainer-diag", path=search_path)
        assert cli_executable is not None, "apptainer-diag CLI entrypoint binary not found on PATH"
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

        # 1. Verify stdout contains valid JSON and matches the report written to file
        stdout_parsed = json.loads(res.stdout)

        raw_text = Path(out_p).read_text(encoding="utf-8")
        report_data = json.loads(raw_text)
        assert stdout_parsed == report_data

        # 2. Verify raw file formatting follows sort_keys=True, indent=2
        expected_text = json.dumps(report_data, sort_keys=True, indent=2)
        assert raw_text.strip() == expected_text.strip()

        assert list(report_data.keys()) == REQUIRED_JSON_SCHEMA_KEYS

        for section, expected_keys in REQUIRED_SUBKEYS.items():
            assert sorted(report_data[section].keys()) == sorted(expected_keys)

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

        extra_paths = [
            os.path.expanduser("~/.local/bin"),
            sys.prefix + "/bin",
            "/usr/local/bin",
        ]
        search_path = os.path.pathsep.join(extra_paths + [os.environ.get("PATH", "")])
        cli_executable = shutil.which("apptainer-diag", path=search_path)
        assert cli_executable is not None, "apptainer-diag CLI entrypoint binary not found on PATH"
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

        res = subprocess.run(
            cmd, cwd=tmpdir, capture_output=True, text=True, check=False
        )
        assert res.returncode == 0
        default_report = os.path.join(tmpdir, "report.json")
        assert os.path.exists(default_report)


def test_cli_stdout_output_mode():
    """Verify stdout mode when running CLI module."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_p = os.path.join(tmpdir, "Apptainer.def")
        res_p = os.path.join(tmpdir, "solver.log")

        with open(spec_p, "w") as f:
            f.write("Bootstrap: docker\nFrom: ubuntu:22.04\n")
        with open(res_p, "w") as f:
            f.write("CONVERGED\n")

        cmd = [
            sys.executable,
            "-m",
            "apptainer_diag.cli",
            "--spec",
            spec_p,
            "--residuals",
            res_p,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert res.returncode == 0
        parsed = json.loads(res.stdout)
        assert list(parsed.keys()) == REQUIRED_JSON_SCHEMA_KEYS
        expected_fmt = json.dumps(parsed, sort_keys=True, indent=2)
        assert res.stdout.strip() == expected_fmt.strip()


def test_cli_empty_output_skips_file():
    """Verify --output '' (empty string) skips file writing and prints exclusively to stdout."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_p = os.path.join(tmpdir, "Apptainer.def")
        res_p = os.path.join(tmpdir, "solver.log")

        with open(spec_p, "w") as f:
            f.write("Bootstrap: docker\nFrom: ubuntu:22.04\n")
        with open(res_p, "w") as f:
            f.write("CONVERGED\n")

        cmd = [
            sys.executable,
            "-m",
            "apptainer_diag.cli",
            "--spec",
            spec_p,
            "--residuals",
            res_p,
            "--output",
            "",
        ]
        res = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True, check=False)
        assert res.returncode == 0
        # No report.json should be created when --output "" is passed
        assert not os.path.exists(os.path.join(tmpdir, "report.json"))
        # Stdout should contain valid JSON matching complete required schema & sub-keys
        parsed = json.loads(res.stdout)
        assert list(parsed.keys()) == REQUIRED_JSON_SCHEMA_KEYS
        for section, expected_keys in REQUIRED_SUBKEYS.items():
            assert sorted(parsed[section].keys()) == sorted(expected_keys)


def test_parse_apptainer_spec_dot_spec_format():
    """Verify parsing of Apptainer container spec from a .spec file (same format as .def)."""
    content = """Bootstrap: docker
From: centos:8

%environment
    export MEMORY_LIMIT_MB=8192
    export CPU_CORES=8
    export WALLTIME_SECONDS=7200

%labels
    Author SimTeam
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".spec") as f:
        f.write(content)
        temp_path = f.name

    try:
        spec = parse_apptainer_spec(temp_path)
        assert spec.base_image == "centos:8"
        assert spec.memory_limit_mb == 8192.0
        assert spec.cpu_cores == 8.0
        assert spec.walltime_seconds == 7200.0
        assert spec.labels.get("Author") == "SimTeam"
    finally:
        os.remove(temp_path)


def test_qualitative_assessment_content():
    """Verify qualitative_assessment contains exhaustive human-readable summary findings matching exact computed state."""
    spec = ContainerSpec(filepath="Apptainer.def", memory_limit_mb=4096.0)
    trace = SolverTrace(filepath="solver.log", converged=True, total_iterations=10)
    valgrind = ValgrindSummary(filepath="valgrind.txt", invalid_writes=1, has_critical_memory_corruption=True)
    gdb = GdbBacktrace(filepath="gdb.txt", signal="SIGFPE", is_sigfpe=True)

    report = generate_diagnostic_report(spec, trace, valgrind, gdb)
    json_str = serialize_report_to_json(report)
    parsed = json.loads(json_str)

    qa = parsed["qualitative_assessment"]
    assert isinstance(qa, list)
    assert len(qa) >= 4

    # Exhaustively validate exact string elements in qualitative_assessment
    exact_risk_str = f"Overall Simulation Stability Risk Level: {report['risk_scores']['risk_level']} ({report['risk_scores']['overall_score']}/100)"
    exact_root_cause_str = f"Identified Primary Root Cause: {report['precedence_analysis']['root_cause']}"
    exact_regime_str = f"Damping Regime Classification: {report['solver_stability_summary']['damping_regime']} - {report['solver_stability_summary']['regime_explanation']}"

    assert exact_risk_str in qa
    assert exact_root_cause_str in qa
    assert exact_regime_str in qa
    assert any(s.startswith("Precedence Resolution:") for s in qa)


def test_resource_constraint_risk_percentage_thresholds():
    """Verify resource_constraint_risk adds +80.0 for leak > 50% container limit, and +50.0 for leak > 20% limit."""
    trace = SolverTrace(filepath="")
    gdb = GdbBacktrace(filepath="")

    # >50% of container memory (60 MB leak with 100 MB limit) -> +80.0
    spec1 = ContainerSpec(filepath="", memory_limit_mb=100.0)
    val1 = ValgrindSummary(filepath="", definitely_lost_bytes=60 * 1024 * 1024)
    scores1 = calculate_risk_scores(spec1, trace, val1, gdb, "Optimal Damping", 10.0)
    assert scores1.resource_constraint_risk == 80.0

    # >20% of container memory (25 MB leak with 100 MB limit) -> +50.0
    spec2 = ContainerSpec(filepath="", memory_limit_mb=100.0)
    val2 = ValgrindSummary(filepath="", definitely_lost_bytes=25 * 1024 * 1024)
    scores2 = calculate_risk_scores(spec2, trace, val2, gdb, "Optimal Damping", 10.0)
    assert scores2.resource_constraint_risk == 50.0


def test_signal_minimum_risk_scores_enforcement():
    """Verify SIGSEGV enforces memory_safety_risk >= 85.0 and SIGFPE enforces numerical_convergence_risk >= 95.0."""
    spec = ContainerSpec(filepath="")
    trace = SolverTrace(filepath="")
    valgrind = ValgrindSummary(filepath="")

    # SIGSEGV min-85 for memory_safety_risk without critical corruption
    gdb_segv = GdbBacktrace(filepath="", signal="SIGSEGV", is_sigsegv=True)
    scores_segv = calculate_risk_scores(spec, trace, valgrind, gdb_segv, "Optimal Damping", 10.0)
    assert scores_segv.memory_safety_risk >= 85.0

    # SIGFPE min-95 for numerical_convergence_risk
    gdb_fpe = GdbBacktrace(filepath="", signal="SIGFPE", is_sigfpe=True)
    scores_fpe = calculate_risk_scores(spec, trace, valgrind, gdb_fpe, "Optimal Damping", 10.0)
    assert scores_fpe.numerical_convergence_risk >= 95.0

