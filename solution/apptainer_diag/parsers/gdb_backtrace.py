"""
Parser for GDB backtrace dumps and crash reports.
"""

import re

from ..models import GdbBacktrace, GdbFrame


def parse_gdb_backtrace(filepath: str) -> GdbBacktrace:
    bt = GdbBacktrace(filepath=filepath)
    if not filepath:
        return bt

    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, ValueError, TypeError):
        return bt

    content = "".join(lines)

    # Detect signal
    sig_match = re.search(
        r"Program received signal\s+(SIG[A-Z0-9]+|\d+)", content, re.IGNORECASE
    )
    if sig_match:
        bt.signal = sig_match.group(1).upper()
    else:
        # Check for alternative signal mentions
        if "SIGSEGV" in content:
            bt.signal = "SIGSEGV"
        elif "SIGFPE" in content:
            bt.signal = "SIGFPE"
        elif "SIGABRT" in content:
            bt.signal = "SIGABRT"
        elif "SIGKILL" in content:
            bt.signal = "SIGKILL"

    if bt.signal == "SIGSEGV":
        bt.is_sigsegv = True
    elif bt.signal == "SIGFPE":
        bt.is_sigfpe = True
    elif bt.signal == "SIGABRT":
        bt.is_sigabrt = True

    # Detect fault address
    addr_match = re.search(r"fault address\s+(0x[0-9a-fA-F]+)", content, re.IGNORECASE)
    if addr_match:
        bt.fault_address = addr_match.group(1)

    # Parse backtrace frames: e.g. #0  0x00007f... in solve_matrix (a=0x0, b=0x1) at solver.c:45
    frame_pattern = re.compile(
        r"#(\d+)\s+(?:(0x[0-9a-fA-F]+)\s+in\s+)?([^\(\n\r]+)(?:\([^\)]*\))?(?:\s+at\s+([^:\n\r]+):(\d+))?",
        re.IGNORECASE,
    )

    frames = []
    for line in lines:
        match = frame_pattern.search(line)
        if match:
            frame_num = int(match.group(1))
            address = match.group(2)
            function = match.group(3).strip()
            filename = match.group(4).strip() if match.group(4) else None
            line_num = int(match.group(5)) if match.group(5) else None

            frames.append(
                GdbFrame(
                    frame_number=frame_num,
                    function=function,
                    file=filename,
                    line=line_num,
                    address=address,
                )
            )

    bt.frames = frames
    return bt
