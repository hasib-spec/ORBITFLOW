"""
OrbitFlow Module 12: ITU Filing Preparation Engine Models
=========================================================
Pydantic v2 Models for ITU Radio Regulations Appendix 4 (Annex 2B/2C),
Article 9 Advance Publication Information (API), Coordination Requests (CR/C),
and 47 CFR § 100.115 Statutory Tracking.
"""

from __future__ import annotations

import enum
import math
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class ITUNoticeType(str, enum.Enum):
    API_A = "API/A"       # Advance Publication (non-coordination under RR No. 9.1/9.2)
    CR_C = "CR/C"         # Coordination Request (RR Article 9 Section II)
    NOTIFICATION = "NOTIFICATION"  # Recording in MIFR (RR Article 11)


class ITUNetworkOrbitType(str, enum.Enum):
    GEO = "GEO"
    NON_GEO = "NON_GEO"


class StationClass(str, enum.Enum):
    EC = "EC"  # Space station in Fixed-Satellite Service (FSS)
    EI = "EI"  # Space station in Mobile-Satellite Service (MSS)
    EV = "EV"  # Space station in Broadcasting-Satellite Service (BSS)
    EH = "EH"  # Space research station
    ET = "ET"  # Space operation station (TT&C)
    EW = "EW"  # Earth exploration-satellite station (EESS)


class PolarizationType(str, enum.Enum):
    H = "H"  # Horizontal Linear
    V = "V"  # Vertical Linear
    L = "L"  # Left-hand circular (LHCP)
    R = "R"  # Right-hand circular (RHCP)
    D = "D"  # Dual / Cross-polar


class BeamDirection(str, enum.Enum):
    TRANSMIT = "E"  # Space-to-Earth / Emission
    RECEIVE = "R"   # Earth-to-Space / Reception


class NGSOOrbitCharacteristics(BaseModel):
    num_planes: int = Field(..., ge=1, description="Number of orbital planes (Item A.4.b.1)")
    sats_per_plane: int = Field(..., ge=1, description="Number of satellites per plane (Item A.4.b.2)")
    num_spares: int = Field(default=0, ge=0, description="Number of in-orbit spare satellites")
    inclination_deg: float = Field(..., ge=0.0, le=180.0, description="Orbital inclination in degrees")
    altitude_perigee_km: float = Field(..., ge=100.0, description="Altitude of perigee in km")
    altitude_apogee_km: float = Field(..., ge=100.0, description="Altitude of apogee in km")
    argument_of_perigee_deg: float = Field(default=0.0, ge=0.0, lt=360.0)
    raan_spread_deg: float = Field(default=360.0, ge=0.0, le=360.0)
    phasing_param_f: int = Field(default=1, ge=0, description="Walker Delta phasing parameter F")
    min_elevation_deg: float = Field(default=10.0, ge=0.0, le=90.0, description="Min operating elevation angle")
    orbital_period_minutes: Optional[float] = Field(None, description="Orbital period in minutes")

    @model_validator(mode="after")
    def compute_and_validate_orbit(self) -> NGSOOrbitCharacteristics:
        r_earth = 6378.137
        mu = 398600.4418
        a = r_earth + (self.altitude_perigee_km + self.altitude_apogee_km) / 2.0
        n = math.sqrt(mu / (a ** 3))
        period_calc = (2.0 * math.pi / n) / 60.0

        if self.orbital_period_minutes is None:
            self.orbital_period_minutes = round(period_calc, 3)
        return self

    @property
    def total_active_satellites(self) -> int:
        return self.num_planes * self.sats_per_plane


class GSOOrbitCharacteristics(BaseModel):
    nominal_longitude_deg: float = Field(..., ge=-180.0, le=180.0, description="Nominal orbital longitude")
    longitudinal_tolerance_deg: float = Field(default=0.05, ge=0.01, le=0.5, description="E-W station-keeping tolerance")
    inclination_excursion_deg: float = Field(default=0.05, ge=0.0, le=5.0, description="N-S station-keeping tolerance")


class ITUEmission(BaseModel):
    designator: str = Field(..., description="ITU standard emission code e.g. 500MD7W, 250MG7D")
    peak_eirp_dbw: float = Field(..., ge=-50.0, le=120.0, description="Peak aggregate EIRP in dBW")
    max_psd_dbw_hz: float = Field(..., ge=-200.0, le=50.0, description="Max power spectral density in dB(W/Hz)")
    min_psd_dbw_hz: Optional[float] = Field(default=None, description="Min power spectral density in dB(W/Hz)")
    bandwidth_khz: float = Field(..., gt=0.0, description="Assigned RF bandwidth in kHz")
    modulation_type: str = Field(default="DIGITAL", description="Modulation format e.g. QPSK, 16APSK")


class ITUCarrier(BaseModel):
    carrier_id: str
    beam_id: str
    direction: BeamDirection
    station_class: StationClass
    nature_of_service: str = Field(default="CO", description="CO=Common carrier, CP=Public, OT=Other")
    polarization: PolarizationType
    service_area_id: str = Field(default="GLOBAL", description="GIMS Diagram ID or ITU Country Code")
    center_frequency_mhz: float = Field(..., gt=0.0)
    bandwidth_mhz: float = Field(..., gt=0.0)
    emission: ITUEmission
    co_polar_pattern_id: str = Field(default="ITU-R S.672")
    cross_polar_pattern_id: str = Field(default="ITU-R S.672")


class ITUBeam(BaseModel):
    beam_id: str
    direction: BeamDirection
    peak_gain_dbi: float = Field(..., ge=0.0, le=80.0)
    beamwidth_3db_deg: float = Field(..., gt=0.0, le=180.0)
    pointing_type: str = Field(default="STEERABLE", description="STEERABLE, FIXED_GRID, GLOBAL")
    noise_temperature_k: Optional[float] = Field(default=None, description="Rx system noise temp for Rx beams")
    gt_ratio_db_k: Optional[float] = Field(default=None, description="Rx figure of merit G/T")


class CostRecoveryDeclaration(BaseModel):
    applicant_legal_name: str
    authorizing_officer_name: str
    authorizing_officer_title: str
    billing_address: str
    billing_email: str
    decision_482_acknowledgement: bool = Field(
        ...,
        description="Affirmative agreement to pay ITU BR cost recovery invoices pursuant to ITU Council Decision 482",
    )
    declaration_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("decision_482_acknowledgement")
    @classmethod
    def must_acknowledge_decision_482(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Part 100 § 100.115(d) mandates affirmative agreement to ITU Cost Recovery terms.")
        return v


class Part100ITUTracker(BaseModel):
    project_id: str
    applicant_id: str
    itu_filing_status: str = Field(
        default="DRAFT",
        description="DRAFT, READY_FOR_FCC, SUBMITTED_TO_ITU, APPLICATION_FILED, WITHDRAWN",
    )
    fcc_itu_submission_date: Optional[date] = None
    underlying_fcc_application_file_num: Optional[str] = None
    statutory_2yr_deadline: Optional[date] = None
    days_remaining_on_clock: Optional[int] = None

    def evaluate_2yr_clock(self, current_date: Optional[date] = None) -> Dict[str, Any]:
        curr = current_date or date.today()
        if not self.fcc_itu_submission_date:
            return {"status": "NOT_SUBMITTED", "clock_active": False}

        deadline = self.fcc_itu_submission_date.replace(year=self.fcc_itu_submission_date.year + 2)
        days_left = (deadline - curr).days

        if self.underlying_fcc_application_file_num:
            return {
                "status": "COMPLIANT_APPLICATION_SUBMITTED",
                "application_file_num": self.underlying_fcc_application_file_num,
                "clock_active": False,
                "days_remaining": days_left,
            }

        if days_left < 0:
            return {
                "status": "EXPIRED_SUBJECT_TO_MANDATORY_WITHDRAWAL",
                "days_expired": abs(days_left),
                "citation": "47 CFR § 100.115(c)",
                "clock_active": False,
            }
        else:
            return {
                "status": "CLOCK_RUNNING",
                "days_remaining": days_left,
                "deadline": deadline.isoformat(),
                "citation": "47 CFR § 100.115(c)",
                "clock_active": True,
            }


class ITUGroupData(BaseModel):
    grp_id: int
    beam_id: str
    direction: str
    station_class: str
    nature_of_service: str
    polarization: str
    service_area_id: str
    pattern_co_id: str
    pattern_cross_id: str
    eirp_max_dbw: float
    psd_max_dbw_hz: float
    psd_min_dbw_hz: float
    carrier_frequencies: List[tuple[float, float, float]] = Field(default_factory=list)
    emissions: List[str] = Field(default_factory=list)


class ITUAppendix4Notice(BaseModel):
    satellite_name: str = Field(..., max_length=20)
    notifying_administration: str = Field(default="USA", max_length=3)
    notice_type: ITUNoticeType
    orbit_type: ITUNetworkOrbitType
    planned_biu_date: date
    ngso_orbit: Optional[NGSOOrbitCharacteristics] = None
    gso_orbit: Optional[GSOOrbitCharacteristics] = None
    beams: List[ITUBeam] = Field(default_factory=list)
    carriers: List[ITUCarrier] = Field(default_factory=list)
    cost_recovery: CostRecoveryDeclaration
    tracker: Part100ITUTracker


class ITUFilingPackageResult(BaseModel):
    filing_id: str
    satellite_name: str
    notice_type: ITUNoticeType
    orbit_type: ITUNetworkOrbitType
    validation_status: str
    is_fully_compliant: bool
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    groups_formed: List[ITUGroupData] = Field(default_factory=list)
    spacecap_xml: str
    cost_recovery_valid: bool
    two_year_clock_status: Dict[str, Any]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
