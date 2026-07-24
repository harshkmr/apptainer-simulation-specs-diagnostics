"""
Unit tests for analyzer modules in apptainer_diag.
"""

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
from apptainer_diag.reporter import generate_diagnostic_report, serialize_report_to_json


def test_unit_conversions():
    # Head conversions
    assert abs(convert_head_to_meters(10.0, "ft") - 3.048) < 1e-4
    assert abs(convert_head_to_meters(9806.65, "Pa") - 1.0) < 1e-4
    assert abs(convert_head_to_meters(1.0, "bar") - 10.1972) < 1e-3
    assert abs(convert_head_to_meters(1.0, "psi") - 0.70307) < 1e-4

    # Flux conversions
    assert abs(convert_flux_to_m3_per_sec(15850.32, "gpm") - 1.0) < 1e-4
    assert abs(convert_flux_to_m3_per_sec(1.0, "cfs") - 0.0283168) < 1e-6
    assert abs(convert_flux_to_m3_per_sec(86400.0, "m3/day") - 1.0) < 1e-5
    assert abs(convert_flux_to_m3_per_sec(60000.0, "L/min") - 1.0) < 1e-5

    # Conductivity conversions
    assert abs(convert_conductivity_to_m_per_sec(86400.0, "m/day") - 1.0) < 1e-5
    assert abs(convert_conductivity_to_m_per_sec(283464.57, "ft/day") - 1.0) < 1e-4
    assert abs(convert_conductivity_to_m_per_sec(100.0, "cm/s") - 1.0) < 1e-5

    # Time conversions
    assert convert_time_to_seconds(2.0, "hours") == 7200.0
    assert convert_time_to_seconds(1.0, "days") == 86400.0


def test_all_five_damping_regimes():
    # 1. Optimal Damping
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


def test_precedence_hierarchy_all_tiers():
    spec = ContainerSpec(filepath="", memory_limit_mb=4096.0)
    trace = SolverTrace(filepath="", diverged=True)
    valgrind = ValgrindSummary(
        filepath="", invalid_writes=2, has_critical_memory_corruption=True
    )
    gdb = GdbBacktrace(filepath="", signal="SIGFPE", is_sigfpe=True)

    # Tier 1: Valgrind Memory Corruption
    res1 = resolve_evidence_precedence(spec, trace, valgrind, gdb, "Optimal Damping")
    assert res1["precedence_tier"] == 1
    assert res1["root_cause"] == "Valgrind Memory Corruption (Invalid Write / Free)"
    assert res1["valgrind_override_applied"] is True

    # Tier 2: Container OOM
    valgrind.has_critical_memory_corruption = False
    valgrind.invalid_writes = 0
    gdb.signal = "SIGKILL"
    gdb.is_sigfpe = False
    res2 = resolve_evidence_precedence(spec, trace, valgrind, gdb, "Optimal Damping")
    assert res2["precedence_tier"] == 2
    assert res2["root_cause"] == "Apptainer Container Resource Limit Exhaustion (OOM)"

    # Tier 3: GDB SIGFPE
    gdb.signal = "SIGFPE"
    gdb.is_sigfpe = True
    res3 = resolve_evidence_precedence(spec, trace, valgrind, gdb, "Optimal Damping")
    assert res3["precedence_tier"] == 3
    assert res3["root_cause"] == "GDB SIGFPE Arithmetic Exception"

    # Tier 4: GDB SIGSEGV / SIGABRT
    gdb.signal = "SIGABRT"
    gdb.is_sigfpe = False
    gdb.is_sigabrt = True
    res4 = resolve_evidence_precedence(spec, trace, valgrind, gdb, "Optimal Damping")
    assert res4["precedence_tier"] == 4
    assert res4["root_cause"] == "GDB SIGABRT Abort Signal Exception"

    # Tier 5: Algorithmic Damping Instability
    gdb.signal = None
    gdb.is_sigabrt = False
    res5 = resolve_evidence_precedence(
        spec, trace, valgrind, gdb, "Under-Damped Oscillation"
    )
    assert res5["precedence_tier"] == 5
    assert (
        res5["root_cause"]
        == "Algorithmic Damping Instability: Under-Damped Oscillation"
    )


def test_risk_score_component_validation_and_thresholds():
    spec = ContainerSpec(filepath="")
    trace = SolverTrace(filepath="")
    valgrind = ValgrindSummary(filepath="")
    gdb = GdbBacktrace(filepath="")

    # 1. LOW Risk Level (0-25)
    scores_low = calculate_risk_scores(
        spec, trace, valgrind, gdb, "Optimal Damping", 10.0
    )
    assert scores_low.memory_safety_risk == 0.0
    assert scores_low.numerical_convergence_risk == 10.0
    assert scores_low.resource_constraint_risk == 0.0
    assert scores_low.overall_score == 4.0
    assert scores_low.risk_level == "LOW"

    # 2. MEDIUM Risk Level (26-50)
    scores_med = calculate_risk_scores(
        spec, trace, valgrind, gdb, "Incomplete / Slow Convergence", 50.0
    )
    assert scores_med.memory_safety_risk == 0.0
    assert scores_med.numerical_convergence_risk == 50.0
    assert scores_med.resource_constraint_risk == 0.0
    assert scores_med.overall_score == 20.0  # 0.4*50 = 20
    assert scores_med.risk_level == "LOW"

    valgrind.invalid_reads = 1
    scores_med2 = calculate_risk_scores(
        spec, trace, valgrind, gdb, "Incomplete / Slow Convergence", 50.0
    )
    # mem_risk = 40.0, num_risk = 50.0 -> 0.45*40 + 0.40*50 = 18 + 20 = 38.0
    assert scores_med2.memory_safety_risk == 40.0
    assert scores_med2.overall_score == 38.0
    assert scores_med2.risk_level == "MEDIUM"

    # 3. HIGH Risk Level (51-75)
    valgrind.invalid_reads = 0
    valgrind.has_critical_memory_corruption = True
    valgrind.invalid_writes = 1
    scores_high = calculate_risk_scores(
        spec, trace, valgrind, gdb, "Incomplete / Slow Convergence", 50.0
    )
    # mem_risk = 100.0, num_risk = 50.0 -> 0.45*100 + 0.40*50 = 45 + 20 = 65.0
    assert scores_high.memory_safety_risk == 100.0
    assert scores_high.overall_score == 65.0
    assert scores_high.risk_level == "HIGH"

    # 4. CRITICAL Risk Level (76-100)
    gdb.signal = "SIGKILL"
    scores_critical = calculate_risk_scores(
        spec, trace, valgrind, gdb, "Divergent Damping Instability", 100.0
    )
    # mem_risk = 100.0, num_risk = 100.0, res_risk = 90.0 -> 0.45*100 + 0.40*100 + 0.15*90 = 45 + 40 + 13.5 = 98.5
    assert scores_critical.resource_constraint_risk == 90.0
    assert scores_critical.overall_score == 98.5
    assert scores_critical.risk_level == "CRITICAL"


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
