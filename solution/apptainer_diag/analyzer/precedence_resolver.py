"""
Precedence resolver for resolving contradictory GDB and Valgrind evidence
according to the laboratory qualification manual precedence hierarchy.
"""

from typing import Any

from ..models import ContainerSpec, GdbBacktrace, SolverTrace, ValgrindSummary


def resolve_evidence_precedence(
    spec: ContainerSpec,
    trace: SolverTrace,
    valgrind: ValgrindSummary,
    gdb: GdbBacktrace,
    regime_name: str,
) -> dict[str, Any]:
    """
    Applies laboratory qualification manual precedence rules to determine root cause
    and resolve contradictory evidence.
    """
    precedence_tier = None
    root_cause = ""
    rationale = ""
    contradictions_resolved: list[str] = []

    # Check Tier 1: Critical Memory Corruption (Valgrind Invalid Writes/Frees)
    if valgrind.has_critical_memory_corruption:
        precedence_tier = 1
        root_cause = "Heap Memory Corruption (Valgrind Memory Safety Failure)"
        rationale = (
            f"Valgrind reported {valgrind.invalid_writes} invalid write(s) and {valgrind.invalid_frees} invalid free(s). "
            "According to Qualification Manual Tier 1 rules, memory corruption supercedes downstream solver crashes or residuals."
        )

        if gdb.is_sigfpe:
            contradictions_resolved.append(
                "GDB reported SIGFPE (floating point exception), but Valgrind memory corruption takes precedence as the primary trigger."
            )
        elif gdb.is_sigsegv:
            contradictions_resolved.append(
                "GDB reported SIGSEGV in solver stack, which is classified as a secondary manifestation of heap corruption."
            )
        if trace.diverged:
            contradictions_resolved.append(
                "Solver residual divergence was caused by corrupted matrix array contents in heap memory."
            )

    # Check Tier 2: Container Resource Limits / Out-Of-Memory (OOM)
    elif gdb.signal == "SIGKILL" or (
        spec.memory_limit_mb
        and valgrind.definitely_lost_bytes / (1024 * 1024) > spec.memory_limit_mb
    ):
        precedence_tier = 2
        root_cause = "Apptainer Container Resource Limit Exhaustion (OOM)"
        rationale = (
            "Container memory or walltime limits were exceeded during simulation execution. "
            "According to Qualification Manual Tier 2 rules, resource limit exhaustion supercedes solver non-convergence."
        )
        if trace.diverged:
            contradictions_resolved.append(
                "Solver non-convergence was cut short by container memory exhaustion."
            )

    # Check Tier 3: Floating Point Arithmetic Crash (GDB SIGFPE)
    elif gdb.is_sigfpe:
        precedence_tier = 3
        root_cause = (
            "Numerical Floating Point Exception (Division by Zero / NaN Invalidation)"
        )
        fault_fn = gdb.frames[0].function if gdb.frames else "unknown solver routine"
        rationale = (
            f"GDB caught SIGFPE arithmetic exception in '{fault_fn}'. "
            "Valgrind memory check is clean. Manual Tier 3 rules classify this as pure numerical solver divergence."
        )

    # Check Tier 4: Segmentation Fault without Valgrind Memory Violation (Unmapped Access)
    elif gdb.is_sigsegv:
        precedence_tier = 4
        root_cause = "Segmentation Fault (Null Pointer or Invalid Memory Reference)"
        fault_fn = gdb.frames[0].function if gdb.frames else "unknown routine"
        rationale = f"GDB caught SIGSEGV at fault address {gdb.fault_address or '0x0'} in '{fault_fn}'."

    # Check Tier 5: Algorithmic Solver Instability / Damping Failure
    else:
        precedence_tier = 5
        root_cause = f"Solver Damping Regime Instability: {regime_name}"
        rationale = f"Execution completed without fatal crash signals. Stability risk is governed by solver residual damping regime ({regime_name})."

    return {
        "precedence_tier": precedence_tier,
        "root_cause": root_cause,
        "rationale": rationale,
        "contradictions_resolved": contradictions_resolved,
        "valgrind_override_applied": precedence_tier == 1
        and bool(gdb.signal or trace.diverged),
    }
