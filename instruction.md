Build a Python command-line diagnostic tool (`apptainer_diag`) for analyzing finite-volume groundwater simulation execution logs, Apptainer container specifications, Valgrind memory profiles, and GDB crash dumps. Package the project using `setuptools` with CLI entrypoint `apptainer-diag`.

### Key Requirements

1. **Packaging & CLI Interface**:
   - Package the project using `setuptools` in `solution/setup.py` exposing console script entrypoint `apptainer-diag` mapping to `apptainer_diag.cli:main`.
   - The CLI must accept `--spec`, `--residuals`, `--valgrind`, `--gdb`, and `--output <json_path>`.
   - **Output File**: If `--output` is omitted, default to writing the report to `report.json` in the current working directory.
   - **Stdout Behavior**: The CLI must always print the formatted JSON report (`sort_keys=True`, `indent=2`) to standard output (`stdout`), in addition to writing it to the specified output file (or `report.json`). If `--output ""` is explicitly passed as an empty string, writing to file is skipped and the report is printed exclusively to `stdout`.

2. **Diagnostic Log Data Parsers**:
   - **Apptainer Container Spec**: Parse base image, resource limits (`MEMORY_LIMIT_MB`, `CPU_CORES`, `WALLTIME_SECONDS`), environment variables, and labels from `.def`, `.spec`, or `.json` files.
   - **Solver Residual Logs**: Parse iteration history from key-value or CSV logs, extracting initial and final residual norms, detecting NaN/Inf values, and identifying explicit `CONVERGED` or `DIVERGED` status lines.
   - **Valgrind Memcheck Summaries**: Parse heap memory leak byte counts (`definitely_lost_bytes`, `indirectly_lost_bytes`, `possibly_lost_bytes`, `still_reachable_bytes`), error counts (`invalid_reads`, `invalid_writes`, `invalid_frees`, `uninitialized_reads`), and total errors. Flag `has_critical_memory_corruption = true` if `invalid_writes > 0` or `invalid_frees > 0`.
   - **GDB Backtrace Summaries**: Parse crash signal strings (`SIGSEGV`, `SIGFPE`, `SIGABRT`, `SIGKILL`), fault addresses, thread ID, and stack frame lists.

3. **Physical Unit Normalization**:
   - Convert pressure head ($ft$, $Pa$, $bar$, $psi$) into meters ($m$). Factors: $1\text{ ft} = 0.3048\text{ m}$, $1\text{ Pa} = 1/9806.65\text{ m}$, $1\text{ bar} = 10.1972\text{ m}$, $1\text{ psi} = 0.70307\text{ m}$.
   - Convert volumetric flux ($gpm$, $cfs$, $m^3/d$, $m^3/day$, $L/min$) into $m^3/s$. Factors: $1\text{ gpm} = 6.30902\times 10^{-5}\text{ m}^3/\text{s}$, $1\text{ cfs} = 0.0283168\text{ m}^3/\text{s}$, $1\text{ m}^3/\text{d} = 1/86400\text{ m}^3/\text{s}$, $1\text{ L/min} = 1/60000\text{ m}^3/\text{s}$.
   - Convert hydraulic conductivity ($m/day$, $ft/day$, $cm/s$) into $m/s$. Factors: $1\text{ m/day} = 1/86400\text{ m/s}$, $1\text{ ft/day} = 0.3048/86400\text{ m/s}$, $1\text{ cm/s} = 0.01\text{ m/s}$.
   - Convert time ($min$, $hours$, $days$) into seconds ($s$). Factors: $1\text{ min} = 60\text{ s}$, $1\text{ hours} = 3600\text{ s}$, $1\text{ days} = 86400\text{ s}$.

4. **Damping Regime Classification**:
   Classify solver convergence behavior across iteration histories into five mutually exclusive regimes:
   - **Divergent Damping Instability** (Risk Impact: 100.0): Triggered if solver marked diverged with no records, or NaN/Inf residual values present, or any iteration norm ratio > 2.0.
   - **Optimal Damping** (Risk Impact: 10.0): Triggered if solver marked converged or final residual norm ratio < 1e-6 within $\le 100$ iterations without divergence or NaN/Inf values.
   - **Under-Damped Oscillation** (Risk Impact: 75.0): Triggered if step ratios alternate direction (step ratio $> 1.15$ followed by $< 0.85$, or $< 0.85$ followed by $> 1.15$) for $\ge 2$ boundary transitions.
   - **Over-Damped Stagnation** (Risk Impact: 60.0): Triggered if consecutive step ratios remain between $0.98$ and $1.02$ inclusive for $\ge 5$ iterations.
   - **Incomplete / Slow Convergence** (Risk Impact: 50.0): Default regime for non-converged solver runs not matching above criteria.

5. **5-Tier Root-Cause Precedence Hierarchy**:
   Resolve evidence conflicts between container limits, memory traces, signals, and solver logs using a 5-tier root-cause hierarchy:
   - **Tier 1**: Valgrind Memory Corruption (`has_critical_memory_corruption = true`). Overrides downstream GDB signals or solver divergence. Root cause: `"Valgrind Memory Corruption (Invalid Write / Free)"`. `valgrind_override_applied = true`.
   - **Tier 2**: Container OOM Limit Exhaustion (`signal == "SIGKILL"` or `OOM` in container env vars). Root cause: `"Apptainer Container Resource Limit Exhaustion (OOM)"`.
   - **Tier 3**: GDB SIGFPE Arithmetic Exception (`is_sigfpe = true`). Root cause: `"GDB SIGFPE Arithmetic Exception"`.
   - **Tier 4**: GDB SIGSEGV (`is_sigsegv = true`, root cause: `"Segmentation Fault (Null Pointer or Invalid Memory Reference)"`) or GDB SIGABRT (`is_sigabrt = true`, root cause: `"GDB SIGABRT Abort Signal Exception"`).
   - **Tier 5**: Algorithmic Damping Instability or Solver Non-Convergence. Root cause derived directly from solver damping regime explanation.

6. **Component Risk Scoring**:
   Calculate component risk scores ($0.0$ to $100.0$) using the formula:
   $$\text{Overall Score} = (0.45 \times \text{Memory Safety Risk}) + (0.40 \times \text{Numerical Convergence Risk}) + (0.15 \times \text{Resource Constraint Risk})$$
   - **Memory Safety Risk**: Base $100.0$ if `has_critical_memory_corruption` is true. Otherwise accumulate increments: $+40.0$ for `invalid_reads > 0`, $+30.0$ for `uninitialized_reads > 0`, $+25.0$ if `definitely_lost_bytes` > 1 MB ($1,048,576$ bytes) or $+10.0$ if `definitely_lost_bytes` > 0. If `is_sigsegv = true` without critical corruption, enforce minimum score of $85.0$. Capped at $100.0$.
   - **Numerical Convergence Risk**: Base score equals classified solver damping regime risk impact score ($10.0$ to $100.0$). If `is_sigfpe = true`, enforce minimum score of $95.0$. Capped at $100.0$.
   - **Resource Constraint Risk**: If container memory limit is defined (`memory_limit_mb`) and `definitely_lost_bytes` > 0: $+80.0$ if leak > 50% of container limit, or $+50.0$ if leak > 20% of container limit. If `signal == "SIGKILL"` or `OOM` in env vars, enforce minimum score of $90.0$. Capped at $100.0$.
   - **Qualitative Risk Levels**:
     - `CRITICAL`: Overall Score $\ge 76.0$
     - `HIGH`: Overall Score $\ge 51.0$ and $< 76.0$
     - `MEDIUM`: Overall Score $\ge 26.0$ and $< 51.0$
     - `LOW`: Overall Score $< 26.0$

7. **Structured Data Schema (Exact Top-Level Keys & Sub-Keys)**:
   Serialize the analysis into a key-sorted JSON report (`sort_keys=True`, `indent=2`). The JSON report must contain all 7 exact top-level section keys and their exact required sub-keys:
   - `apptainer_spec_summary` (dict): `base_image`, `cpu_cores`, `environment_vars`, `filepath`, `labels`, `memory_limit_mb`, `walltime_seconds`
   - `solver_stability_summary` (dict): `converged`, `damping_factor`, `damping_regime`, `diverged`, `filepath`, `final_residual_norm`, `initial_residual_norm`, `regime_explanation`, `total_iterations`
   - `valgrind_summary` (dict): `definitely_lost_bytes`, `filepath`, `has_critical_memory_corruption`, `indirectly_lost_bytes`, `invalid_frees`, `invalid_reads`, `invalid_writes`, `possibly_lost_bytes`, `still_reachable_bytes`, `total_errors`, `uninitialized_reads`
   - `gdb_summary` (dict): `crash_thread`, `fault_address`, `filepath`, `frames`, `is_sigabrt`, `is_sigfpe`, `is_sigsegv`, `signal`
   - `precedence_analysis` (dict): `contradictions_resolved`, `precedence_tier`, `rationale`, `root_cause`, `valgrind_override_applied`
   - `risk_scores` (dict): `memory_safety_risk`, `numerical_convergence_risk`, `overall_score`, `resource_constraint_risk`, `risk_level`
   - `qualitative_assessment` (list of strings): List of human-readable summary findings.
