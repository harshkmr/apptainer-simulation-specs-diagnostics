"""
Parser for finite-volume groundwater simulation solver residual traces.
"""

import re

from ..analyzer.unit_converter import (
    convert_flux_to_m3_per_sec,
    convert_head_to_meters,
    convert_time_to_seconds,
)
from ..models import ResidualRecord, SolverTrace


def parse_solver_residuals(filepath: str) -> SolverTrace:
    trace = SolverTrace(filepath=filepath)
    if not filepath:
        return trace

    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, ValueError, TypeError):
        return trace

    records = []
    initial_res = None
    last_res = None

    for line in lines:
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue

        # Look for iteration data
        # e.g., Iter 1: dt=1.0s res_head=1.0m res_flux=0.1m3/s norm_ratio=1.0
        # e.g., 1, 100.0, 1.5e-2, 3.2e-4, 0.85
        iter_match = re.search(
            r"(?:iter|iteration|step)\s*[:=]?\s*(\d+)", line_str, re.IGNORECASE
        )
        if iter_match:
            iter_num = int(iter_match.group(1))

            # Extract dt
            dt_match = re.search(
                r"dt\s*[:=]?\s*([\d\.eE\+-]+)\s*([a-zA-Z]+)?", line_str, re.IGNORECASE
            )
            dt_val = float(dt_match.group(1)) if dt_match else 1.0
            dt_unit = dt_match.group(2) if dt_match and dt_match.group(2) else "s"
            dt_sec = convert_time_to_seconds(dt_val, dt_unit)

            # Extract head residual
            head_match = re.search(
                r"(?:res_head|head_res|h_res|residual_head|head)\s*[:=]?\s*([\d\.eE\+-]+|nan|inf|-nan|-inf)\s*([a-zA-Z0-9_/]+)?",
                line_str,
                re.IGNORECASE,
            )
            if head_match:
                val_str = head_match.group(1).lower()
                is_nan = "nan" in val_str
                is_inf = "inf" in val_str
                val = 0.0 if (is_nan or is_inf) else float(val_str)
                unit = head_match.group(2) if head_match.group(2) else "m"
                head_m = convert_head_to_meters(val, unit)
            else:
                head_m = 0.0
                is_nan = False
                is_inf = False

            # Check for NaN / Inf anywhere in line
            if "nan" in line_str.lower():
                is_nan = True
            if "inf" in line_str.lower():
                is_inf = True

            # Extract flux residual
            flux_match = re.search(
                r"(?:res_flux|flux_res|q_res|residual_flux|flux)\s*[:=]?\s*([\d\.eE\+-]+)\s*([a-zA-Z0-9_/]+)?",
                line_str,
                re.IGNORECASE,
            )
            if flux_match:
                val = float(flux_match.group(1))
                unit = flux_match.group(2) if flux_match.group(2) else "m3/s"
                flux_m3_s = convert_flux_to_m3_per_sec(val, unit)
            else:
                flux_m3_s = 0.0

            # Extract norm ratio or norm
            norm_match = re.search(
                r"(?:norm_ratio|norm|ratio|res_norm)\s*[:=]?\s*([\d\.eE\+-]+)",
                line_str,
                re.IGNORECASE,
            )
            if norm_match:
                norm_ratio = float(norm_match.group(1))
            else:
                norm_ratio = head_m

            if initial_res is None and not (is_nan or is_inf):
                initial_res = norm_ratio if norm_ratio > 0 else 1.0

            last_res = norm_ratio

            rec = ResidualRecord(
                iteration=iter_num,
                time_step=1,
                dt_seconds=dt_sec,
                residual_head_m=head_m,
                residual_flux_m3_s=flux_m3_s,
                norm_ratio=norm_ratio,
                is_nan=is_nan,
                is_inf=is_inf,
            )
            records.append(rec)

        # Look for explicit convergence / divergence indicators in text
        if re.search(
            r"solver converged|convergence achieved|CONVERGED", line_str, re.IGNORECASE
        ):
            trace.converged = True
        if re.search(
            r"solver diverged|divergence detected|DIVERGED|nan encountered",
            line_str,
            re.IGNORECASE,
        ):
            trace.diverged = True

        # Damping factor detection
        damp_match = re.search(
            r"(?:damping|relax|alpha|omega)\s*[:=]?\s*([\d\.eE\+-]+)",
            line_str,
            re.IGNORECASE,
        )
        if damp_match:
            trace.damping_factor = float(damp_match.group(1))

    trace.records = records
    trace.total_iterations = len(records)
    if initial_res is not None:
        trace.initial_residual = initial_res
    if last_res is not None:
        trace.final_residual = last_res

    # Check overall divergence status
    if any(r.is_nan or r.is_inf for r in records):
        trace.diverged = True

    return trace
