"""
OrbitFlow Module 10: Spectrum & EPFD Engine — Data Models
=========================================================
Pydantic schemas for Power Flux Density (PFD), Equivalent Power Flux Density (EPFD),
Off-Axis EIRP Density, and atmospheric link propagation under FCC Part 100 & ITU Radio Regulations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class FrequencyBand(str, Enum):
    UHF_VHF = "UHF/VHF (100 - 450 MHz)"
    S_BAND = "S-band (2.0 - 4.0 GHz)"
    C_BAND = "C-band (3.7 - 6.5 GHz)"
    X_BAND = "X-band (7.0 - 8.5 GHz)"
    KU_BAND = "Ku-band (10.7 - 14.5 GHz)"
    KA_BAND = "Ka-band (17.7 - 30.0 GHz)"
    Q_BAND = "Q-band (37.5 - 42.5 GHz)"
    V_BAND = "V-band (47.2 - 51.4 GHz)"
    OPTICAL = "Optical / Laser (ISL)"


class LinkDirection(str, Enum):
    TRANSMIT = "TRANSMIT"  # Space-to-Earth (Downlink)
    RECEIVE = "RECEIVE"    # Earth-to-Space (Uplink)
    INTER_SATELLITE = "INTER_SATELLITE"  # Space-to-Space (ISL)


class Polarization(str, Enum):
    CIRCULAR_RHCP = "RHCP"
    CIRCULAR_LHCP = "LHCP"
    DUAL_CIRCULAR = "Dual Circular (RHCP/LHCP)"
    LINEAR_HORIZONTAL = "Linear Horizontal"
    LINEAR_VERTICAL = "Linear Vertical"
    DUAL_LINEAR = "Dual Linear (H/V)"


class PFDMaskType(str, Enum):
    ITU_SF_1006_KU = "ITU-R SF.1006 (Ku-band)"
    ITU_SF_1602_KA = "ITU-R SF.1602 (Ka-band)"
    FCC_100_212_GENERIC = "FCC § 100.212 Generic Stepped Mask"
    FCC_100_212_QV_BAND = "FCC § 100.212 (Q/V-band)"


class EmissionDesignator(BaseModel):
    """
    Standard ITU Emission Designator (47 CFR § 2.201 / ITU Appendix 1).
    Example: '500MD7W', '1M00G1D', '50M0G7D'.
    """
    designator: str = Field(..., description="Full 7-character ITU emission designator")
    necessary_bandwidth_mhz: float = Field(..., gt=0.0)
    modulation_type: str = Field(..., description="e.g. Digital Phase Modulation, Multi-channel")
    description: str = Field(default="")


class FrequencyChannelConfig(BaseModel):
    channel_id: str
    direction: LinkDirection
    band: FrequencyBand
    center_frequency_mhz: float = Field(..., gt=0.0)
    bandwidth_mhz: float = Field(..., gt=0.0)
    emission_designator: str = Field(default="500MD7W")
    polarization: Polarization = Field(default=Polarization.DUAL_CIRCULAR)
    max_eirp_dbw: float = Field(default=52.0, description="Max total EIRP in dBW")
    max_eirp_density_dbw_mhz: float = Field(default=0.0, description="Max power spectral density in dBW/MHz")
    peak_antenna_gain_dbi: float = Field(default=36.0, description="Peak antenna gain in dBi")
    is_shared_federal_band: bool = Field(default=False, description="Shared NTIA/Federal coordination band")


class SlantRangeResult(BaseModel):
    elevation_deg: float = Field(..., ge=0.0, le=90.0)
    altitude_km: float = Field(..., gt=0.0)
    slant_range_km: float
    earth_central_angle_deg: float
    satellite_off_nadir_deg: float


class PFDPointResult(BaseModel):
    elevation_deg: float
    slant_range_km: float
    free_space_loss_db: float
    atmospheric_loss_db: float
    eirp_density_dbw_mhz: float
    pfd_calculated_dbw_m2_mhz: float
    pfd_limit_dbw_m2_mhz: float
    margin_db: float
    compliant: bool


class PFDAnalysisResult(BaseModel):
    mask_type: PFDMaskType
    band: FrequencyBand
    center_frequency_ghz: float
    min_margin_db: float
    critical_elevation_deg: float
    is_fully_compliant: bool
    data_points: List[PFDPointResult]


class EPFDEntryResult(BaseModel):
    satellite_id: str
    sub_satellite_lat: float
    sub_satellite_lon: float
    slant_range_km: float
    pfd_dbw_m2_bw: float
    off_axis_angle_deg: float
    victim_antenna_gain_dbi: float
    normalized_gain_ratio: float
    weighted_pfd_w_m2_bw: float


class EPFDAggregateResult(BaseModel):
    calculation_type: str = Field(default="EPFD_Downlink")
    frequency_ghz: float
    reference_bandwidth_khz: float
    gso_earth_station_dish_diameter_m: float
    gso_es_peak_gain_dbi: float
    visible_satellites_count: int
    aggregate_epfd_dbw_m2_bw: float
    itu_art22_limit_dbw_m2_bw: float
    margin_db: float
    compliant: bool
    details: str = Field(default="")
    satellite_breakdown: List[EPFDEntryResult] = Field(default_factory=list)


class OffAxisEIRPCheckResult(BaseModel):
    frequency_band: FrequencyBand
    reference_bandwidth_khz: float
    theta_deg: float
    actual_eirp_density_dbw: float
    copolar_limit_dbw: float
    cross_polar_limit_dbw: Optional[float] = None
    copolar_compliant: bool
    cross_polar_compliant: Optional[bool] = None
    two_degree_spacing_compliant: bool
    details: str = Field(default="")


class SpectrumSharingReport(BaseModel):
    """
    Comprehensive Master Spectrum & EPFD Engineering Report.
    """
    report_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    system_name: str
    operator_name: str
    channels_analyzed: List[FrequencyChannelConfig]
    pfd_analysis: List[PFDAnalysisResult]
    epfd_downlink_analysis: Optional[EPFDAggregateResult] = None
    off_axis_eirp_analysis: Optional[OffAxisEIRPCheckResult] = None
    shared_federal_bands_detected: bool = False
    all_spectrum_requirements_met: bool = True
    summary_verdict: str
    disclaimer: str = Field(
        default="CONFIDENTIAL - TECHNICAL SPECTRUM ASSESSMENT. Evaluated in accordance with FCC Part 100 (§§ 100.212, 100.222, 100.280) and ITU Radio Regulations Article 22 & ITU-R S.1432."
    )
