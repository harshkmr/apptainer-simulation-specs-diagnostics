Configure a build and packaging environment for an offline Python diagnostic tool (`apptainer_diag`) that validates Apptainer container specs, dependency environment configurations, and simulation execution logs.

### Functional Requirements

#### 1. Input Log Parsers
The package must parse four distinct diagnostic file inputs:
- **Apptainer Container Specs (.def / .spec or JSON)**: Extract base_image, memory_limit_mb, cpu_cores, walltime_seconds, %environment variables, and %labels.
- **Solver Residual Logs**: Parse lines formatted as Iter <N>: dt=<X>s res_head=<Y>m res_flux=<Z>m3/s norm_ratio=<R> or CSV lines N, dt, res_head, res_flux, norm_ratio. Detect NaN / Inf values and keywords CONVERGED / DIVERGED.
- **Valgrind Memcheck Summaries**: Parse definitely lost, indirectly lost, possibly lost, and still reachable bytes, ERROR SUMMARY counts, and error patterns (Invalid write, Invalid read, Invalid free, uninitialised value). Flag has_critical_memory_corruption = True if invalid writes or invalid frees > 0.
- **GDB Backtrace Dumps**: Detect crash signals (SIGSEGV, SIGFPE, SIGABRT), fault address (fault address 0x...), and frame call stacks #N [0x...] in <function> at <file>:<line>.

#### 2. Physical Unit Conversions
Normalize all input quantities to SI units:
- **Pressure Head (h)**: ft to m (x 0.3048), Pa to m (/ 9806.65), bar to m (x 10.1972), psi to m (x 0.70307).
- **Volumetric Flux (Q)**: gpm to m3/s (/ 15850.32), cfs to m3/s (x 0.0283168), m3/d to m3/s (/ 86400).
- **Time Step (dt)**: min to s (x 60), hours to s (x 3600), days to s (x 86400).

#### 3. Damping Regime Classifier
Classify the solver residual convergence behavior across iteration histories into one of five regimes:
- **Divergent Damping Instability** (Risk = 100.0): Any NaN / Inf residual, explicit DIVERGED status, or norm ratio > 2.0.
- **Optimal Damping** (Risk = 10.0): Final residual norm ratio < 1e-6 and no oscillations.
- **Under-Damped Oscillation** (Risk = 75.0): Residual norm ratios oscillate (> 1.15 and < 0.85 on alternating steps >= 2 times).
- **Over-Damped Stagnation** (Risk = 60.0): Residual norm ratio remains > 0.98 for >= 5 consecutive steps without reaching target tolerance.
- **Incomplete / Slow Convergence** (Risk = 50.0): Non-divergent solver that terminates before reaching 1e-6 tolerance.

#### 4. Precedence Hierarchy Resolver
Disentangle contradictory diagnostic signals by applying a strict 5-tier root-cause precedence hierarchy:
- **Tier 1 - Valgrind Memory Corruption**: If has_critical_memory_corruption is true, override downstream GDB SIGFPE crashes or solver divergence. Set precedence_tier = 1, valgrind_override_applied = True, and root_cause = "Valgrind Memory Corruption (Invalid Write / Free)".
- **Tier 2 - Container Resource Limit Exhaustion**: If execution exceeded memory_limit_mb or walltime_seconds, set precedence_tier = 2 and root_cause = "Apptainer Container Resource Limit Exhaustion (OOM)".
- **Tier 3 - GDB SIGFPE Exception**: If GDB caught SIGFPE and Valgrind memory check is clean, set precedence_tier = 3 and root_cause = "GDB SIGFPE Arithmetic Exception".
- **Tier 4 - Segmentation Fault**: If GDB caught SIGSEGV without Valgrind invalid writes, set precedence_tier = 4 and root_cause = "Segmentation Fault (Null Pointer or Invalid Memory Reference)".
- **Tier 5 - Algorithmic Damping Instability**: If no fatal memory or signal crashes occurred, set precedence_tier = 5 and root_cause = "Algorithmic Damping Instability: <Regime Name>".

#### 5. Risk Scoring and Qualitative Levels
Compute component risk scores (0.0 to 100.0) weighted as:
Overall Score = 0.45 x Memory Safety Risk + 0.40 x Solver Stability Risk + 0.15 x Resource Limits Risk.
Qualitative risk levels: LOW (0-25), MEDIUM (26-50), HIGH (51-75), CRITICAL (76-100).

#### 6. Deterministic JSON Report Schema
Serialize the analysis into a key-sorted JSON report (sort_keys=True) with the following top-level keys:
- apptainer_spec_summary: { "base_image", "memory_limit_mb", "cpu_cores", "walltime_seconds", "env_vars", "labels" }
- solver_stability_summary: { "total_iterations", "initial_residual", "final_residual", "converged", "diverged", "damping_regime", "damping_factor" }
- valgrind_summary: { "definitely_lost_bytes", "indirectly_lost_bytes", "possibly_lost_bytes", "still_reachable_bytes", "total_errors", "invalid_writes", "invalid_reads", "invalid_frees", "uninitialized_reads", "has_critical_memory_corruption" }
- gdb_summary: { "signal", "is_sigsegv", "is_sigfpe", "is_sigabrt", "fault_address", "top_frame_function" }
- precedence_analysis: { "precedence_tier", "root_cause", "rationale", "valgrind_override_applied" }
- risk_scores: { "memory_safety_score", "solver_stability_score", "resource_limit_score", "overall_score", "risk_level" }
- assessment: List of human-readable assessment strings.

#### 7. Packaging and CLI Interface
Package the project using setuptools in solution/setup.py exposing a CLI entrypoint apptainer-diag.
The CLI must accept arguments --spec, --residuals, --valgrind, --gdb, and --output <json_path> (or print to stdout if omitted).
