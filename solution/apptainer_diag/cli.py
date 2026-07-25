"""
CLI entry point for Apptainer simulation diagnostics analyzer.
"""

import argparse

from .parsers import (
    parse_apptainer_spec,
    parse_gdb_backtrace,
    parse_solver_residuals,
    parse_valgrind_summary,
)
from .reporter import generate_diagnostic_report, serialize_report_to_json


def main():
    parser = argparse.ArgumentParser(
        description="Offline analysis tool to score numerical stability risks for finite-volume groundwater simulations."
    )
    parser.add_argument(
        "--spec", type=str, help="Path to Apptainer spec / definition file", default=""
    )
    parser.add_argument(
        "--residuals", type=str, help="Path to solver residual trace log", default=""
    )
    parser.add_argument(
        "--valgrind", type=str, help="Path to Valgrind memcheck summary", default=""
    )
    parser.add_argument(
        "--gdb", type=str, help="Path to GDB backtrace dump file", default=""
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Path to output JSON report file",
        default="report.json",
    )

    args = parser.parse_args()

    spec = parse_apptainer_spec(args.spec)
    trace = parse_solver_residuals(args.residuals)
    valgrind = parse_valgrind_summary(args.valgrind)
    gdb = parse_gdb_backtrace(args.gdb)

    report = generate_diagnostic_report(spec, trace, valgrind, gdb)

    # Determine output target: None means --output was not provided (use default),
    # empty string means stdout-only (skip file writing).
    if args.output == "":
        # --output "" explicitly passed: stdout only, no file
        json_out = serialize_report_to_json(report, None)
    else:
        # --output <path> or default "report.json"
        json_out = serialize_report_to_json(report, args.output)
    print(json_out)


if __name__ == "__main__":
    main()
