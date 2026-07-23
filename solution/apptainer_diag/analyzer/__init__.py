"""
Analyzer module for unit conversions, stability scoring, and evidence precedence resolution.
"""

from .precedence_resolver import resolve_evidence_precedence
from .stability_scorer import calculate_risk_scores, classify_damping_regime
from .unit_converter import (
    convert_conductivity_to_m_per_sec,
    convert_flux_to_m3_per_sec,
    convert_head_to_meters,
    convert_time_to_seconds,
)

__all__ = [
    "calculate_risk_scores",
    "classify_damping_regime",
    "convert_conductivity_to_m_per_sec",
    "convert_flux_to_m3_per_sec",
    "convert_head_to_meters",
    "convert_time_to_seconds",
    "resolve_evidence_precedence",
]
