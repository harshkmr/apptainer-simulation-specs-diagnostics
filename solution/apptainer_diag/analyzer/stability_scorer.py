"""
Scoring engine for numerical stability risks and solver damping regimes.
"""

from ..models import (
    ContainerSpec,
    GdbBacktrace,
    RiskScore,
    SolverTrace,
    ValgrindSummary,
)


def classify_damping_regime(trace: SolverTrace) -> tuple[str, float, str]:
    """
    Classifies solver convergence damping regime and returns:
    (regime_name, risk_impact_score, explanation)
    """
    if not trace.records:
        if trace.diverged:
            return (
                "Divergent Damping Instability",
                95.0,
                "Solver marked as diverged with no valid residual records.",
            )
        return (
            "Unknown / No Residual Data",
            50.0,
            "No residual records available to evaluate damping regime.",
        )

    records = trace.records
    has_nan_inf = any(r.is_nan or r.is_inf for r in records)
    if has_nan_inf or trace.diverged:
        return (
            "Divergent Damping Instability",
            100.0,
            "Solver encounter NaN/Inf residual values or catastrophic mathematical divergence.",
        )

    norm_ratios = [r.norm_ratio for r in records]
    n = len(norm_ratios)

    # Check for explosive growth (norm ratio > 2.0 anywhere)
    for r in norm_ratios:
        if r > 2.0:
            return (
                "Divergent Damping Instability",
                90.0,
                f"Residual norm ratio exceeded explosive limit (found {r:.2e}).",
            )

    # Check for monotonic optimal convergence
    final_ratio = norm_ratios[-1]
    if trace.converged or (final_ratio < 1e-6 and n <= 100):
        return (
            "Optimal Damping",
            5.0,
            "Solver achieved monotonic residual reduction below tolerance limit.",
        )

    # Check for under-damped oscillation (alternating ratio > 1.15 and < 0.85)
    oscillations = 0
    for i in range(1, n - 1):
        r1 = norm_ratios[i] / max(norm_ratios[i - 1], 1e-15)
        r2 = norm_ratios[i + 1] / max(norm_ratios[i], 1e-15)
        if (r1 > 1.15 and r2 < 0.85) or (r1 < 0.85 and r2 > 1.15):
            oscillations += 1

    if oscillations >= 3 or (n > 10 and oscillations / n > 0.2):
        return (
            "Under-Damped Oscillation",
            75.0,
            f"Residual norm displayed periodic oscillations across {oscillations} iteration boundaries.",
        )

    # Check for over-damped stagnation (slope nearly flat, norm ratio stays > 0.98 for many steps)
    stagnant_steps = 0
    for i in range(1, n):
        step_ratio = norm_ratios[i] / max(norm_ratios[i - 1], 1e-15)
        if 0.98 <= step_ratio <= 1.02 and norm_ratios[i] > 1e-3:
            stagnant_steps += 1

    if stagnant_steps >= 15 or (n > 20 and stagnant_steps / n > 0.6):
        return (
            "Over-Damped Stagnation",
            60.0,
            f"Residual norm stagnated for {stagnant_steps} iterations due to over-conservative damping.",
        )

    if final_ratio > 1e-3:
        return (
            "Incomplete / Slow Convergence",
            50.0,
            f"Solver terminated with unreduced residual norm ratio ({final_ratio:.2e}).",
        )

    return (
        "Sub-Optimal Damping",
        30.0,
        f"Solver converged slowly over {n} iterations.",
    )


def calculate_risk_scores(
    spec: ContainerSpec,
    trace: SolverTrace,
    valgrind: ValgrindSummary,
    gdb: GdbBacktrace,
    regime_name: str,
    regime_risk: float,
) -> RiskScore:
    """
    Computes numerical stability, memory safety, and resource constraint risk scores (0-100).
    """
    # 1. Memory Safety Risk
    mem_risk = 0.0
    if valgrind.has_critical_memory_corruption:
        mem_risk = 100.0
    else:
        if valgrind.invalid_reads > 0:
            mem_risk += 40.0
        if valgrind.uninitialized_reads > 0:
            mem_risk += 30.0
        if valgrind.definitely_lost_bytes > 1024 * 1024:  # > 1 MB leak
            mem_risk += 25.0
        elif valgrind.definitely_lost_bytes > 0:
            mem_risk += 10.0

    if gdb.is_sigsegv and not valgrind.has_critical_memory_corruption:
        mem_risk = max(mem_risk, 85.0)

    mem_risk = min(mem_risk, 100.0)

    # 2. Numerical Convergence Risk
    num_risk = regime_risk
    if gdb.is_sigfpe:
        num_risk = max(num_risk, 95.0)

    num_risk = min(num_risk, 100.0)

    # 3. Resource Constraint Risk
    res_risk = 0.0
    if spec.memory_limit_mb is not None and valgrind.definitely_lost_bytes > 0:
        leak_mb = valgrind.definitely_lost_bytes / (1024.0 * 1024.0)
        if leak_mb > spec.memory_limit_mb * 0.5:
            res_risk += 80.0
        elif leak_mb > spec.memory_limit_mb * 0.2:
            res_risk += 50.0

    if gdb.signal == "SIGKILL" or "OOM" in str(spec.env_vars):
        res_risk = max(res_risk, 90.0)

    res_risk = min(res_risk, 100.0)

    # 4. Overall Score calculation (Weighted combination)
    overall = (num_risk * 0.45) + (mem_risk * 0.40) + (res_risk * 0.15)
    overall = min(max(overall, 0.0), 100.0)

    if overall >= 75.0:
        level = "CRITICAL"
    elif overall >= 50.0:
        level = "HIGH"
    elif overall >= 25.0:
        level = "MEDIUM"
    else:
        level = "LOW"

    return RiskScore(
        overall_score=round(overall, 2),
        risk_level=level,
        memory_safety_risk=round(mem_risk, 2),
        numerical_convergence_risk=round(num_risk, 2),
        resource_constraint_risk=round(res_risk, 2),
    )
