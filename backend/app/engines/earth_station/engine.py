"""
OrbitFlow Module 19: Earth Station Nationwide Non-Site Master Engine
====================================================================
Synthesizes Earth Station specs into Nationwide Non-Site License packages,
evaluates clear-sky & rain link budgets (ITU-R P.618 / P.676), generates Form 312
Schedule B XML, and manages 365-day Bring-Into-Use site registries.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional

from backend.app.core.config import get_logger
from backend.app.engines.earth_station.models import (
    AntennaAssemblySpec,
    AntennaPolarization,
    BIUStatus,
    EarthStationFilingResult,
    FrequencyBandEnvelope,
    HorizonElevationPoint,
    LinkBudgetCalculation,
    PreGrantVerificationResult,
    SiteClassification,
    SiteRegistrationData,
)
from backend.app.engines.earth_station.physics import EarthStationRFPhysics
from backend.app.engines.earth_station.schedule_b import (
    PreGrantCertificationEngine,
    ScheduleBGenerator,
)
from backend.app.models.satellite import OrbitType, SatelliteSpec

log = get_logger(__name__)


class EarthStationEngine:
    """Master engine for FCC Part 100 Nationwide Non-Site Earth Station Licensing."""

    def generate_earth_station_package(
        self,
        spec: SatelliteSpec,
        lead_callsign: str = "E260100",
        applicant_name: str = "OrbitalFlow Communications Inc.",
        frn: str = "0034567891",
        custom_sites: Optional[List[SiteRegistrationData]] = None,
        custom_envelopes: Optional[List[FrequencyBandEnvelope]] = None,
    ) -> EarthStationFilingResult:
        """
        Generates a complete Nationwide Non-Site Lead License and Site Registration Package.
        """
        log.info("Generating Earth Station NNS Package for %s", spec.name)

        # 1. Derive Technical Envelopes
        envelopes = custom_envelopes or self._derive_default_envelopes(spec)

        # 2. Derive Registered Sites
        sites = custom_sites or self._derive_default_sites(spec)

        # 3. Calculate Downlink Link Budget for Primary Gateway
        primary_site = sites[0]
        primary_antenna = primary_site.antennas[0] if primary_site.antennas else AntennaAssemblySpec(antenna_id="ANT-01")

        link_budget = EarthStationRFPhysics.evaluate_downlink_budget(
            frequency_ghz=19.7,
            satellite_altitude_km=spec.altitude_km,
            elevation_deg=25.0,
            lat_deg=primary_site.latitude_deg,
            sat_eirp_dbw=23.0 if spec.orbit_type == OrbitType.LEO else 52.0,
            dish_diameter_m=primary_antenna.diameter_meters,
            feed_loss_db=primary_antenna.feed_loss_db,
            lna_temp_k=primary_antenna.lna_noise_temp_k,
            user_bit_rate_mbps=250.0,
            required_eb_n0_db=6.5,
        )

        # 4. Evaluate Pre-Grant Operations (§ 100.120(f))
        pre_grant = PreGrantCertificationEngine.evaluate(
            site=primary_site,
            has_approved_form312=True,
            days_on_public_notice=16,
            attestation_nib_signed=True,
            stop_buzzer_contact_ready=True,
        )

        # 5. Generate Schedule B XML
        schedule_b_xml = ScheduleBGenerator.generate_xml(
            lead_callsign=lead_callsign,
            applicant_name=applicant_name,
            frn=frn,
            envelope_bands=envelopes,
            sites=sites,
        )

        biu_deadline = primary_site.registration_date + timedelta(days=365)

        return EarthStationFilingResult(
            license_callsign=lead_callsign,
            applicant_name=applicant_name,
            frn=frn,
            envelope_bands=envelopes,
            registered_sites=sites,
            link_budget=link_budget,
            pre_grant_status=pre_grant,
            schedule_b_xml=schedule_b_xml,
            biu_deadline=biu_deadline,
        )

    def _derive_default_envelopes(self, spec: SatelliteSpec) -> List[FrequencyBandEnvelope]:
        return [
            FrequencyBandEnvelope(
                band_id="BAND-KA-UL",
                band_name="Ka-band Feeder Uplink",
                direction="TRANSMIT",
                lower_freq_mhz=27500.0,
                upper_freq_mhz=30000.0,
                center_freq_ghz=28.75,
                max_aggregate_eirp_dbw=82.5,
                max_eirp_density_dbw_4khz=42.0,
                max_eirp_density_dbw_1mhz=66.0,
                emission_designators=["500MD7W", "250MG7D", "1M00G1D"],
            ),
            FrequencyBandEnvelope(
                band_id="BAND-KA-DL",
                band_name="Ka-band Feeder Downlink",
                direction="RECEIVE",
                lower_freq_mhz=17800.0,
                upper_freq_mhz=20200.0,
                center_freq_ghz=19.0,
                max_aggregate_eirp_dbw=0.0,
                max_eirp_density_dbw_4khz=0.0,
                max_eirp_density_dbw_1mhz=0.0,
                emission_designators=["500MD7W"],
            ),
        ]

    def _derive_default_sites(self, spec: SatelliteSpec) -> List[SiteRegistrationData]:
        return [
            SiteRegistrationData(
                site_id="SITE-FL-01",
                site_name="Cape Canaveral Gateway Core Hub",
                classification=SiteClassification.GATEWAY_FEEDER,
                latitude_deg=28.4889,
                longitude_deg=-80.5778,
                site_elevation_amsl_m=3.2,
                antennas=[
                    AntennaAssemblySpec(
                        antenna_id="ANT-CC-01",
                        manufacturer="Viasat Commercial Terminals",
                        model_number="VA-9000-KA-GW",
                        diameter_meters=9.0,
                        center_of_radiation_agl_m=12.5,
                        polarization=AntennaPolarization.DUAL_CIRCULAR,
                        feed_loss_db=0.45,
                        lna_noise_temp_k=95.0,
                    )
                ],
                horizon_profile=[
                    HorizonElevationPoint(azimuth_deg=0.0, elevation_deg=1.2),
                    HorizonElevationPoint(azimuth_deg=90.0, elevation_deg=0.5),
                    HorizonElevationPoint(azimuth_deg=180.0, elevation_deg=1.0),
                    HorizonElevationPoint(azimuth_deg=270.0, elevation_deg=2.1),
                ],
                target_space_station_callsigns=[spec.name[:10]],
                coordination_agency="Comsearch Technical Services",
                coordination_case_id="CS-2026-KA-9941",
                pcn_completed_no_conflicts=True,
                ntia_concurrence_received=True,
                registration_date=date.today(),
                biu_status=BIUStatus.PENDING_365D,
                waiver_requested=False,
            ),
            SiteRegistrationData(
                site_id="SITE-TX-02",
                site_name="McGregor Teleport & Gateway Hub",
                classification=SiteClassification.TELEPORT_CORE,
                latitude_deg=31.3986,
                longitude_deg=-97.4089,
                site_elevation_amsl_m=215.0,
                antennas=[
                    AntennaAssemblySpec(
                        antenna_id="ANT-TX-01",
                        manufacturer="General Dynamics SATCOM",
                        model_number="GD-7300-KA",
                        diameter_meters=7.3,
                        center_of_radiation_agl_m=10.0,
                        polarization=AntennaPolarization.DUAL_CIRCULAR,
                        feed_loss_db=0.50,
                        lna_noise_temp_k=110.0,
                    )
                ],
                horizon_profile=[
                    HorizonElevationPoint(azimuth_deg=0.0, elevation_deg=0.8),
                    HorizonElevationPoint(azimuth_deg=180.0, elevation_deg=0.4),
                ],
                target_space_station_callsigns=[spec.name[:10]],
                coordination_agency="Comsearch Technical Services",
                coordination_case_id="CS-2026-KA-9942",
                pcn_completed_no_conflicts=True,
                ntia_concurrence_received=True,
                registration_date=date.today(),
                biu_status=BIUStatus.PENDING_365D,
                waiver_requested=False,
            ),
        ]


_earth_station_engine: Optional[EarthStationEngine] = None


def get_earth_station_engine() -> EarthStationEngine:
    global _earth_station_engine
    if _earth_station_engine is None:
        _earth_station_engine = EarthStationEngine()
    return _earth_station_engine
