"""
OrbitFlow Module 10: Spectrum & EPFD Engine
===========================================
Exports public models, propagation routines, and master SpectrumEngine.
"""

from backend.app.engines.epfd.models import (
    EmissionDesignator,
    EPFDAggregateResult,
    EPFDEntryResult,
    FrequencyBand,
    FrequencyChannelConfig,
    LinkDirection,
    OffAxisEIRPCheckResult,
    PFDAnalysisResult,
    PFDMaskType,
    PFDPointResult,
    Polarization,
    SlantRangeResult,
    SpectrumSharingReport,
)
from backend.app.engines.epfd.propagation import (
    calculate_atmospheric_loss,
    calculate_free_space_loss,
    calculate_slant_range,
)
from backend.app.engines.epfd.antenna import (
    calculate_itu_s1428_gain,
    evaluate_off_axis_eirp_density,
)
from backend.app.engines.epfd.engine import (
    SpectrumEngine,
    get_spectrum_engine,
)

__all__ = [
    "FrequencyBand",
    "LinkDirection",
    "Polarization",
    "PFDMaskType",
    "EmissionDesignator",
    "FrequencyChannelConfig",
    "SlantRangeResult",
    "PFDPointResult",
    "PFDAnalysisResult",
    "EPFDEntryResult",
    "EPFDAggregateResult",
    "OffAxisEIRPCheckResult",
    "SpectrumSharingReport",
    "calculate_slant_range",
    "calculate_free_space_loss",
    "calculate_atmospheric_loss",
    "calculate_itu_s1428_gain",
    "evaluate_off_axis_eirp_density",
    "SpectrumEngine",
    "get_spectrum_engine",
]
