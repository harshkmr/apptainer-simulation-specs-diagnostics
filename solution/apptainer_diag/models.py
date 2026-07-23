"""
Data models for simulation specs, logs, diagnostics, and risk reports.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContainerSpec:
    filepath: str
    base_image: str = "ubuntu:22.04"
    memory_limit_mb: float | None = None
    cpu_cores: float | None = None
    walltime_seconds: float | None = None
    env_vars: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class ResidualRecord:
    iteration: int
    time_step: int
    dt_seconds: float
    residual_head_m: float
    residual_flux_m3_s: float
    norm_ratio: float
    is_nan: bool = False
    is_inf: bool = False


@dataclass
class SolverTrace:
    filepath: str
    records: list[ResidualRecord] = field(default_factory=list)
    initial_residual: float = 1.0
    final_residual: float = 1.0
    converged: bool = False
    diverged: bool = False
    damping_factor: float | None = None
    total_iterations: int = 0


@dataclass
class ValgrindSummary:
    filepath: str
    definitely_lost_bytes: int = 0
    indirectly_lost_bytes: int = 0
    possibly_lost_bytes: int = 0
    still_reachable_bytes: int = 0
    uninitialized_reads: int = 0
    invalid_reads: int = 0
    invalid_writes: int = 0
    invalid_frees: int = 0
    total_errors: int = 0
    has_critical_memory_corruption: bool = False


@dataclass
class GdbFrame:
    frame_number: int
    function: str
    file: str | None = None
    line: int | None = None
    address: str | None = None


@dataclass
class GdbBacktrace:
    filepath: str
    signal: str | None = None
    fault_address: str | None = None
    crash_thread: str | None = None
    frames: list[GdbFrame] = field(default_factory=list)
    is_sigfpe: bool = False
    is_sigsegv: bool = False
    is_sigabrt: bool = False


@dataclass
class RiskScore:
    overall_score: float
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    memory_safety_risk: float
    numerical_convergence_risk: float
    resource_constraint_risk: float


@dataclass
class DiagnosticReport:
    apptainer_spec_summary: dict[str, Any]
    solver_stability_summary: dict[str, Any]
    valgrind_summary: dict[str, Any]
    gdb_summary: dict[str, Any]
    precedence_analysis: dict[str, Any]
    risk_scores: dict[str, Any]
    qualitative_assessment: list[str]
