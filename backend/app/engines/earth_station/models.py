"""
OrbitFlow Module 19: Earth Station Nationwide Non-Site Engine Models
====================================================================
Pydantic v2 Models for 47 CFR § 100.120 (Nationwide Non-Site License),
§ 100.121 (Site Registration), Antenna G/T, and Schedule B XML.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SiteClassification(str, enum.Enum):
    GATEWAY_FEEDER = "GATEWAY_FEEDER_LINK"
    TTC_GROUND_STATION = "TTC_GROUND_STATION"
    ENTERPRISE_HUB = "ENTERPRISE_TERMINAL_HUB"
    TELEPORT_CORE = "TELEPORT_CORE_FACILITY"


class AntennaPolarization(str, enum.Enum):
    LHCP = "LHCP"
    RHCP = "RHCP"
    DUAL_CIRCULAR = "DUAL_CIRCULAR"
    LINEAR_HORIZONTAL = "LINEAR_HORIZONTAL"
    LINEAR_VERTICAL = "LINEAR_VERTICAL"
    DUAL_LINEAR = "DUAL_LINEAR"


class BIUStatus(str, enum.Enum):
    PENDING_365D = "PENDING_365D_VERIFICATION"
    COMMISSIONED_ACTIVE = "COMMISSIONED_ACTIVE"
    EXPIRED_REVOKED = "EXPIRED_REVOKED"


class HorizonElevationPoint(BaseModel):
    azimuth_deg: float = Field(..., ge=0.0, le=360.0)
    elevation_deg: float = Field(..., ge=-5.0, le=90.0)


class AntennaAssemblySpec(BaseModel):
    antenna_id: str
    manufacturer: str = "Viasat Commercial Terminals"
    model_number: str = "VA-9000-KA-GW"
    diameter_meters: float = Field(default=9.0, gt=0.0)
    aperture_efficiency: float = Field(default=0.65, gt=0.0, le=1.0)
    center_of_radiation_agl_m: float = Field(default=12.5, ge=0.0)
    polarization: AntennaPolarization = AntennaPolarization.DUAL_CIRCULAR
    feed_loss_db: float = Field(default=0.45, ge=0.0)
    lna_noise_temp_k: float = Field(default=95.0, gt=0.0)


class FrequencyBandEnvelope(BaseModel):
    band_id: str
    band_name: str
    direction: str  # TRANSMIT or RECEIVE
    lower_freq_mhz: float
    upper_freq_mhz: float
    center_freq_ghz: float
    max_aggregate_eirp_dbw: float
    max_eirp_density_dbw_4khz: float
    max_eirp_density_dbw_1mhz: float
    emission_designators: List[str] = Field(default_factory=list)


class SiteRegistrationData(BaseModel):
    site_id: str
    site_name: str
    classification: SiteClassification = SiteClassification.GATEWAY_FEEDER
    latitude_deg: float = Field(..., ge=-90.0, le=90.0)
    longitude_deg: float = Field(..., ge=-180.0, le=180.0)
    site_elevation_amsl_m: float = 3.2
    antennas: List[AntennaAssemblySpec] = Field(default_factory=list)
    horizon_profile: List[HorizonElevationPoint] = Field(default_factory=list)
    target_space_station_callsigns: List[str] = Field(default_factory=lambda: ["S3099"])

    # Coordination & BIU Record
    coordination_agency: str = "Comsearch Technical Services"
    coordination_case_id: str = "CS-2026-KA-9941"
    pcn_date: date = Field(default_factory=lambda: date.today() - timedelta(days=30))
    pcn_completed_no_conflicts: bool = True
    ntia_concurrence_received: bool = True
    registration_date: date = Field(default_factory=date.today)
    biu_status: BIUStatus = BIUStatus.PENDING_365D
    waiver_requested: bool = False


class PreGrantVerificationResult(BaseModel):
    is_authorized_pre_grant: bool
    public_notice_cleared: bool
    zero_waiver_verified: bool
    coordination_cleared: bool
    nib_attestation_bound: bool
    stop_buzzer_poc_ready: bool
    status_summary: str


class LinkBudgetCalculation(BaseModel):
    frequency_ghz: float
    elevation_deg: float
    slant_range_km: float
    free_space_loss_db: float
    atmospheric_loss_db: float
    rain_attenuation_db: float
    clear_sky_g_t_db_k: float
    rain_faded_g_t_db_k: float
    eirp_dbw: float
    c_n0_clear_sky_db_hz: float
    c_n0_rain_faded_db_hz: float
    user_bit_rate_mbps: float
    eb_n0_received_rain_db: float
    eb_n0_required_db: float
    link_margin_rain_db: float
    is_link_closed: bool


class EarthStationFilingResult(BaseModel):
    license_callsign: str
    applicant_name: str
    frn: str
    envelope_bands: List[FrequencyBandEnvelope]
    registered_sites: List[SiteRegistrationData]
    link_budget: LinkBudgetCalculation
    pre_grant_status: PreGrantVerificationResult
    schedule_b_xml: str
    biu_deadline: date
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
