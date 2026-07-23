"""
Reporter module to build and serialize deterministic JSON diagnostic reports.
"""

import json
from typing import Any

from .analyzer import (
    calculate_risk_scores,
    classify_damping_regime,
    resolve_evidence_precedence,
)
from .models import (
    ContainerSpec,
    GdbBacktrace,
    SolverTrace,
    ValgrindSummary,
)


def generate_diagnostic_report(
    spec: ContainerSpec,
    trace: SolverTrace,
    valgrind: ValgrindSummary,
    gdb: GdbBacktrace,
) -> dict[str, Any]:
    """
    Generates a deterministic diagnostic dictionary.
    """
    # 1. Analyze solver damping regime
    regime_name, regime_risk, regime_explanation = classify_damping_regime(trace)

    # 2. Resolve precedence rules between GDB and Valgrind
    precedence = resolve_evidence_precedence(spec, trace, valgrind, gdb, regime_name)

    # 3. Calculate risk scores
    risk_score = calculate_risk_scores(
        spec, trace, valgrind, gdb, regime_name, regime_risk
    )

    # 4. Generate qualitative assessment statements
    assessment: list[str] = [
        f"Overall Simulation Stability Risk Level: {risk_score.risk_level} ({risk_score.overall_score}/100)",
        f"Identified Primary Root Cause: {precedence['root_cause']}",
        f"Damping Regime Classification: {regime_name} - {regime_explanation}",
    ]
    for c in precedence["contradictions_resolved"]:
        assessment.append(f"Precedence Resolution: {c}")

    # 5. Build structured report dictionary
    report = {
        "apptainer_spec_summary": {
            "base_image": spec.base_image,
            "cpu_cores": spec.cpu_cores,
            "environment_vars": dict(sorted(spec.env_vars.items())),
            "filepath": spec.filepath,
            "labels": dict(sorted(spec.labels.items())),
            "memory_limit_mb": spec.memory_limit_mb,
            "walltime_seconds": spec.walltime_seconds,
        },
        "gdb_summary": {
            "crash_thread": gdb.crash_thread,
            "fault_address": gdb.fault_address,
            "filepath": gdb.filepath,
            "frames": [
                {
                    "address": f.address,
                    "file": f.file,
                    "frame_number": f.frame_number,
                    "function": f.function,
                    "line": f.line,
                }
                for f in gdb.frames
            ],
            "is_sigabrt": gdb.is_sigabrt,
            "is_sigfpe": gdb.is_sigfpe,
            "is_sigsegv": gdb.is_sigsegv,
            "signal": gdb.signal,
        },
        "precedence_analysis": {
            "contradictions_resolved": precedence["contradictions_resolved"],
            "precedence_tier": precedence["precedence_tier"],
            "rationale": precedence["rationale"],
            "root_cause": precedence["root_cause"],
            "valgrind_override_applied": precedence["valgrind_override_applied"],
        },
        "qualitative_assessment": sorted(assessment),
        "risk_scores": {
            "memory_safety_risk": risk_score.memory_safety_risk,
            "numerical_convergence_risk": risk_score.numerical_convergence_risk,
            "overall_score": risk_score.overall_score,
            "resource_constraint_risk": risk_score.resource_constraint_risk,
            "risk_level": risk_score.risk_level,
        },
        "solver_stability_summary": {
            "converged": trace.converged,
            "damping_factor": trace.damping_factor,
            "damping_regime": regime_name,
            "diverged": trace.diverged,
            "filepath": trace.filepath,
            "final_residual_norm": round(trace.final_residual, 6),
            "initial_residual_norm": round(trace.initial_residual, 6),
            "regime_explanation": regime_explanation,
            "total_iterations": trace.total_iterations,
        },
        "valgrind_summary": {
            "definitely_lost_bytes": valgrind.definitely_lost_bytes,
            "filepath": valgrind.filepath,
            "has_critical_memory_corruption": valgrind.has_critical_memory_corruption,
            "indirectly_lost_bytes": valgrind.indirectly_lost_bytes,
            "invalid_frees": valgrind.invalid_frees,
            "invalid_reads": valgrind.invalid_reads,
            "invalid_writes": valgrind.invalid_writes,
            "possibly_lost_bytes": valgrind.possibly_lost_bytes,
            "still_reachable_bytes": valgrind.still_reachable_bytes,
            "total_errors": valgrind.total_errors,
            "uninitialized_reads": valgrind.uninitialized_reads,
        },
    }

    return report


def serialize_report_to_json(
    report: dict[str, Any], output_path: str | None = None
) -> str:
    """
    Serializes diagnostic report dictionary to a deterministic JSON string.
    If output_path is provided, writes to file.
    """
    json_str = json.dumps(report, indent=2, sort_keys=True)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str + "\n")
    return json_str
