"""
Unit tests for parsers in apptainer_diag.
"""

import os
import tempfile

from apptainer_diag.parsers import (
    parse_apptainer_spec,
    parse_gdb_backtrace,
    parse_solver_residuals,
    parse_valgrind_summary,
)


def test_parse_apptainer_spec():
    content = """Bootstrap: docker
From: ubuntu:22.04

%environment
    export MEMORY_LIMIT_MB=8192
    export CPU_CORES=8
    export WALLTIME_SECONDS=7200

%labels
    Maintainer HydroLab
    Version 2.0
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".def") as f:
        f.write(content)
        temp_path = f.name

    try:
        spec = parse_apptainer_spec(temp_path)
        assert spec.base_image == "ubuntu:22.04"
        assert spec.memory_limit_mb == 8192.0
        assert spec.cpu_cores == 8.0
        assert spec.walltime_seconds == 7200.0
        assert spec.env_vars.get("MEMORY_LIMIT_MB") == "8192"
        assert spec.labels.get("Maintainer") == "HydroLab"
    finally:
        os.remove(temp_path)


def test_parse_solver_residuals():
    content = """
# Simulation log
Iter 1: dt=1.0s, res_head=10.0m, res_flux=1.0m3/s, norm_ratio=1.0
Iter 2: dt=1.0s, res_head=5.0m, res_flux=0.5m3/s, norm_ratio=0.5
Iter 3: dt=1.0s, res_head=0.0000001m, res_flux=0.00000001m3/s, norm_ratio=0.0000001
CONVERGED
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".log") as f:
        f.write(content)
        temp_path = f.name

    try:
        trace = parse_solver_residuals(temp_path)
        assert len(trace.records) == 3
        assert trace.converged is True
        assert trace.initial_residual == 1.0
        assert trace.final_residual == 0.0000001
    finally:
        os.remove(temp_path)


def test_parse_valgrind_summary():
    content = """
==12345== LEAK SUMMARY:
==12345==    definitely lost: 4,096 bytes in 1 blocks
==12345==    indirectly lost: 0 bytes in 0 blocks
==12345==    possibly lost: 1,024 bytes in 1 blocks
==12345==    still reachable: 8,192 bytes in 2 blocks
==12345== Invalid write of size 8 at 0x401234
==12345== ERROR SUMMARY: 2 errors from 2 contexts
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write(content)
        temp_path = f.name

    try:
        valgrind = parse_valgrind_summary(temp_path)
        assert valgrind.definitely_lost_bytes == 4096
        assert valgrind.invalid_writes == 1
        assert valgrind.has_critical_memory_corruption is True
        assert valgrind.total_errors == 2
    finally:
        os.remove(temp_path)


def test_parse_gdb_backtrace():
    content = """
Program received signal SIGSEGV, Segmentation fault.
0x00007ffff7a12345 in petsc_solve (matrix=0x0) at petsc_wrapper.c:120
120     matrix->values[0] = 1.0;
#0  0x00007ffff7a12345 in petsc_solve (matrix=0x0) at petsc_wrapper.c:120
#1  0x0000000000401122 in main (argc=1, argv=0x7fffffffe000) at main.c:45
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write(content)
        temp_path = f.name

    try:
        gdb = parse_gdb_backtrace(temp_path)
        assert gdb.signal == "SIGSEGV"
        assert gdb.is_sigsegv is True
        assert len(gdb.frames) == 2
        assert gdb.frames[0].function == "petsc_solve"
        assert gdb.frames[0].line == 120
    finally:
        os.remove(temp_path)
