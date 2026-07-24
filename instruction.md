Process and analyze diagnostic log data from groundwater simulation execution runs, Apptainer container specifications, Valgrind memory profiles, and GDB crash dumps. Build an offline data processing pipeline (`apptainer_diag`) packaged via `setuptools` with CLI entrypoint `apptainer-diag`.

### Key Requirements

1. **Packaging & CLI Interface**:
   - Package the project using `setuptools` in `solution/setup.py` exposing console script entrypoint `apptainer-diag` mapping to `apptainer_diag.cli:main`.
   - The CLI must accept `--spec`, `--residuals`, `--valgrind`, `--gdb`, and `--output <json_path>` (defaulting to `report.json` if omitted, or printing to stdout if explicitly configured).

2. **Diagnostic Log Data Parsers**:
   - Parse container spec resource limits, environment variables, and labels from `.def`, `.spec`, or `.json` files.
   - Parse solver residual iterations from key-value or CSV logs, detecting NaN/Inf values and convergence/divergence statuses.
   - Parse Valgrind heap memory leak byte counts, invalid reads/writes, invalid frees, and error summaries. Flag critical memory corruption if invalid writes or invalid frees occur.
   - Parse GDB crash signals (SIGSEGV, SIGFPE, SIGABRT), fault addresses, and stack frames.

3. **Physical Unit Normalization**:
   - Convert pressure head ($ft$, $Pa$, $bar$, $psi$), volumetric flux ($gpm$, $cfs$, $m^3/d$, $m^3/day$, $L/min$), hydraulic conductivity ($m/day$, $ft/day$, $cm/s$), and time steps ($min$, $hours$, $days$) into SI base units ($m$, $m^3/s$, $m/s$, $s$).

4. **Damping Regime Classification & Precedence Resolution**:
   - Classify solver convergence behavior across iteration histories into five regimes: *Divergent Damping Instability*, *Optimal Damping*, *Under-Damped Oscillation*, *Over-Damped Stagnation*, and *Incomplete / Slow Convergence*.
   - Apply a 5-tier root-cause precedence hierarchy to resolve evidence conflicts: Tier 1 (Valgrind memory corruption override), Tier 2 (Container OOM limit), Tier 3 (GDB SIGFPE), Tier 4 (GDB SIGSEGV / SIGABRT), and Tier 5 (Algorithmic damping instability).

5. **Risk Scoring & Deterministic JSON Report**:
   - Calculate component risk scores ($0.0$ to $100.0$) for Memory Safety, Solver Stability, and Resource Constraints, combining them into an overall weighted score and qualitative risk level (LOW, MEDIUM, HIGH, CRITICAL).
   - Serialize the analysis into a key-sorted JSON report (`sort_keys=True`) with required top-level sections (`apptainer_spec_summary`, `solver_stability_summary`, `valgrind_summary`, `gdb_summary`, `precedence_analysis`, `risk_scores`, `qualitative_assessment`) and their associated sub-keys.
