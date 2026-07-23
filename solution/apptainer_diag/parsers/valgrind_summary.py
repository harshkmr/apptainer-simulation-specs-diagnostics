"""
Parser for Valgrind memcheck summary reports.
"""

import re

from ..models import ValgrindSummary


def parse_valgrind_summary(filepath: str) -> ValgrindSummary:
    summary = ValgrindSummary(filepath=filepath)
    if not filepath:
        return summary

    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except (OSError, ValueError, TypeError):
        return summary

    # Parse LEAK SUMMARY block
    def_match = re.search(
        r"definitely lost:\s*([\d,]+)\s*bytes", content, re.IGNORECASE
    )
    if def_match:
        summary.definitely_lost_bytes = int(def_match.group(1).replace(",", ""))

    ind_match = re.search(
        r"indirectly lost:\s*([\d,]+)\s*bytes", content, re.IGNORECASE
    )
    if ind_match:
        summary.indirectly_lost_bytes = int(ind_match.group(1).replace(",", ""))

    pos_match = re.search(r"possibly lost:\s*([\d,]+)\s*bytes", content, re.IGNORECASE)
    if pos_match:
        summary.possibly_lost_bytes = int(pos_match.group(1).replace(",", ""))

    reach_match = re.search(
        r"still reachable:\s*([\d,]+)\s*bytes", content, re.IGNORECASE
    )
    if reach_match:
        summary.still_reachable_bytes = int(reach_match.group(1).replace(",", ""))

    # Parse ERROR SUMMARY block
    err_match = re.search(r"ERROR SUMMARY:\s*(\d+)\s*errors", content, re.IGNORECASE)
    if err_match:
        summary.total_errors = int(err_match.group(1))

    # Parse specific memory access violation patterns
    summary.invalid_writes = len(
        re.findall(r"Invalid write of size", content, re.IGNORECASE)
    )
    summary.invalid_reads = len(
        re.findall(r"Invalid read of size", content, re.IGNORECASE)
    )
    summary.invalid_frees = len(
        re.findall(r"Invalid free\(\) / delete", content, re.IGNORECASE)
    )
    summary.uninitialized_reads = len(
        re.findall(
            r"Use of uninitialised value|Conditional jump or move depends on uninitialised",
            content,
            re.IGNORECASE,
        )
    )

    # Check for critical memory corruption
    if summary.invalid_writes > 0 or summary.invalid_frees > 0:
        summary.has_critical_memory_corruption = True

    return summary
