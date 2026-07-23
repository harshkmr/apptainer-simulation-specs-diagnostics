"""
Unit tests for analyzer modules in apptainer_diag.
"""

from apptainer_diag.analyzer import (
    classify_damping_regime,
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
from apptainer_diag.reporter import generate_diagnostic_report, serialize_report_to_json


def test_unit_conversions():
    # Head conversions
    assert abs(convert_head_to_meters(10.0, "ft") - 3.048) < 1e-5
    assert abs(convert_head_to_meters(9806.65, "Pa") - 1.0) < 1e-4

    # Flux conversions
    assert abs(convert_flux_to_m3_per_sec(86400.0, "m3/day") - 1.0) < 1e-5
    assert abs(convert_flux_to_m3_per_sec(60000.0, "L/min") - 1.0) < 1e-5

    # Time conversions
    assert convert_time_to_seconds(2.0, "hours") == 7200.0
    assert convert_time_to_seconds(1.0, "days") == 86400.0


def test_damping_regime_classification():
    # Optimal
    trace_optimal = SolverTrace(
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
    regime, risk, _ = classify_damping_regime(trace_optimal)
    assert regime == "Optimal Damping"
    assert risk < 20.0

    # Divergent
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


def test_precedence_tier_1_valgrind_override():
    spec = ContainerSpec(filepath="")
    trace = SolverTrace(filepath="", diverged=True)
    valgrind = ValgrindSummary(
        filepath="", invalid_writes=2, has_critical_memory_corruption=True
    )
    gdb = GdbBacktrace(filepath="", signal="SIGFPE", is_sigfpe=True)

    regime, _risk, _ = classify_damping_regime(trace)
    res = resolve_evidence_precedence(spec, trace, valgrind, gdb, regime)

    assert res["precedence_tier"] == 1
    assert "Heap Memory Corruption" in res["root_cause"]
    assert res["valgrind_override_applied"] is True
    assert len(res["contradictions_resolved"]) > 0


def test_deterministic_report_generation():
    spec = ContainerSpec(filepath="Apptainer.def", memory_limit_mb=4096.0)
    trace = SolverTrace(filepath="solver.log", converged=True, total_iterations=25)
    valgrind = ValgrindSummary(filepath="valgrind.txt")
    gdb = GdbBacktrace(filepath="gdb.txt")

    report = generate_diagnostic_report(spec, trace, valgrind, gdb)
    json_str_1 = serialize_report_to_json(report)
    json_str_2 = serialize_report_to_json(report)

    assert json_str_1 == json_str_2
    assert "risk_scores" in report
    assert "precedence_analysis" in report
