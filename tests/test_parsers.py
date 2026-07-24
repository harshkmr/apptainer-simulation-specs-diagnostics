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
    content = """
Bootstrap: docker
From: debian:bookworm

%environment
    export MEMORY_LIMIT_MB=2048
    export WALLTIME_SECONDS=1800
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".def") as f:
        f.write(content)
        path = f.name

    try:
        spec = parse_apptainer_spec(path)
        assert spec.base_image == "debian:bookworm"
        assert spec.memory_limit_mb == 2048.0
        assert spec.walltime_seconds == 1800.0
    finally:
        os.remove(path)


def test_parse_solver_residuals_keyvalue_format():
    content = """
# Solver trace
Iter 1: dt=1.0s res_head=1.0m res_flux=0.1m3/s norm_ratio=1.0
Iter 2: dt=1.0s res_head=0.1m res_flux=0.01m3/s norm_ratio=0.1
CONVERGED
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".log") as f:
        f.write(content)
        path = f.name

    try:
        trace = parse_solver_residuals(path)
        assert trace.total_iterations == 2
        assert trace.converged is True
        assert len(trace.records) == 2
        assert trace.records[0].residual_head_m == 1.0
    finally:
        os.remove(path)


def test_parse_solver_residuals_csv_format():
    content = """# Iter, dt, res_head, res_flux, norm_ratio
1, 1.0, 0.5, 0.05, 0.5
2, 1.0, 0.05, 0.005, 0.05
CONVERGED
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f:
        f.write(content)
        path = f.name

    try:
        trace = parse_solver_residuals(path)
        assert trace.total_iterations == 2
        assert trace.converged is True
        assert len(trace.records) == 2
        assert trace.records[0].residual_head_m == 0.5
        assert trace.records[1].norm_ratio == 0.05
    finally:
        os.remove(path)


def test_parse_valgrind_summary():
    content = """
==999== LEAK SUMMARY:
==999==    definitely lost: 4,096 bytes in 1 blocks
==999==    indirectly lost: 2,048 bytes in 1 blocks
==999==    possibly lost: 1,024 bytes in 1 blocks
==999==    still reachable: 8,192 bytes in 4 blocks
==999== Invalid free() / delete / delete[] / realloc()
==999==    at 0x401234: free
==999== ERROR SUMMARY: 1 errors from 1 contexts
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write(content)
        path = f.name

    try:
        val = parse_valgrind_summary(path)
        assert val.definitely_lost_bytes == 4096
        assert val.indirectly_lost_bytes == 2048
        assert val.possibly_lost_bytes == 1024
        assert val.still_reachable_bytes == 8192
        assert val.invalid_frees == 1
        assert val.has_critical_memory_corruption is True
    finally:
        os.remove(path)


def test_parse_gdb_backtrace():
    content = """
Program received signal SIGSEGV, Segmentation fault.
(fault address 0x00007ffff7a12345)
#0  0x00007ffff7a12345 in solve_matrix (a=0x0) at solver.c:10
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write(content)
        path = f.name

    try:
        gdb = parse_gdb_backtrace(path)
        assert gdb.signal == "SIGSEGV"
        assert gdb.is_sigsegv is True
        assert gdb.fault_address == "0x00007ffff7a12345"
        assert len(gdb.frames) == 1
    finally:
        os.remove(path)


def test_parse_gdb_backtrace_sigabrt():
    content = """
Program received signal SIGABRT, Aborted.
#0  0x00007ffff7a99999 in __GI_raise () from /lib/x86_64-linux-gnu/libc.so.6
"""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write(content)
        path = f.name

    try:
        gdb = parse_gdb_backtrace(path)
        assert gdb.signal == "SIGABRT"
        assert gdb.is_sigabrt is True
    finally:
        os.remove(path)
