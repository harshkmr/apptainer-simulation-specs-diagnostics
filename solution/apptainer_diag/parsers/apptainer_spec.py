"""
Parser for Apptainer container definition files (.def / .spec).
"""

import json
import re

from ..models import ContainerSpec


def parse_apptainer_spec(filepath: str) -> ContainerSpec:
    spec = ContainerSpec(filepath=filepath)
    if not filepath:
        return spec

    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except (OSError, ValueError, TypeError):
        return spec

    # JSON formatted spec check
    if content.strip().startswith("{") and content.strip().endswith("}"):
        try:
            data = json.loads(content)
            spec.base_image = data.get("base_image", spec.base_image)
            spec.memory_limit_mb = data.get("memory_limit_mb")
            spec.cpu_cores = data.get("cpu_cores")
            spec.walltime_seconds = data.get("walltime_seconds")
            spec.env_vars = data.get("env_vars", {})
            spec.labels = data.get("labels", {})
            return spec
        except json.JSONDecodeError:
            pass

    # Standard Apptainer .def / text parsing
    from_match = re.search(r"(?:From|from):\s*(\S+)", content)
    if from_match:
        spec.base_image = from_match.group(1).strip()
    else:
        boot_match = re.search(r"(?:Bootstrap|bootstrap):\s*(\S+)", content)
        if boot_match:
            spec.base_image = boot_match.group(1).strip()

    # Search for resource limits in comments, environment, or labels
    # e.g., MEMORY_LIMIT_MB=4096, CPU_CORES=4, WALLTIME_SECONDS=3600
    mem_match = re.search(
        r"(?:MEMORY_LIMIT_MB|MEMORY_MB|memory_mb|mem_limit)\s*[:=]\s*(\d+(?:\.\d+)?)",
        content,
        re.IGNORECASE,
    )
    if mem_match:
        spec.memory_limit_mb = float(mem_match.group(1))

    cpu_match = re.search(
        r"(?:CPU_CORES|CPUS|cpus|cpu_cores)\s*[:=]\s*(\d+(?:\.\d+)?)",
        content,
        re.IGNORECASE,
    )
    if cpu_match:
        spec.cpu_cores = float(cpu_match.group(1))

    wall_match = re.search(
        r"(?:WALLTIME_SECONDS|WALLTIME_SEC|walltime)\s*[:=]\s*(\d+(?:\.\d+)?)",
        content,
        re.IGNORECASE,
    )
    if wall_match:
        spec.walltime_seconds = float(wall_match.group(1))

    # Parse %environment section
    env_section = re.search(r"%environment\s*\n(.*?)(?=\n%|\Z)", content, re.DOTALL)
    if env_section:
        for line in env_section.group(1).splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" in line:
                key, val = line.split("=", 1)
                spec.env_vars[key.strip()] = val.strip().strip("\"'")

    # Parse %labels section
    labels_section = re.search(r"%labels\s*\n(.*?)(?=\n%|\Z)", content, re.DOTALL)
    if labels_section:
        for line in labels_section.group(1).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    spec.labels[parts[0].strip()] = parts[1].strip()

    return spec
