Configure a build and packaging pipeline for an offline Python diagnostic tool (`apptainer_diag`) that validates Apptainer container specs, dependency environment configurations, and simulation execution logs.

The tool must manage dependency package installation, parse container definition files, check runtime environment variables, and verify numerical stability metrics across simulation iterations.

Package the solution into a standard Python setuptools distribution and generate a key-sorted, deterministic JSON report summarizing container spec parameters, dependency health, component risk scores, and overall risk levels.
