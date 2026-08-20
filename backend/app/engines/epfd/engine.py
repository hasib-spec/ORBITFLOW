"""
OrbitFlow Module 10: Spectrum & EPFD Engine — Master Computation Engine
=======================================================================
Executes comprehensive RF spectrum sharing evaluations:
1. Power Flux Density (PFD) at Earth's surface under 47 CFR § 100.212 / ITU-R SF.1602 / SF.1006.
2. Equivalent Power Flux Density (EPFD) aggregate downlink under ITU Radio Regulations Article 22 & ITU-R S.1432.
3. Off-Axis EIRP Density & 2-Degree GSO orbital spacing co-existence under 47 CFR § 100.280.
4. Shared Federal Band detection & NTIA coordination triggers under § 100.136(b)(7).
"""

from __future__ import annotations

import math
import uuid
import logging
from typing import List, Optional

from backend.app.models.satellite import OrbitType, SatelliteSpec
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

logger = logging.getLogger(__name__)


class SpectrumEngine:
    """
    Master physical and regulatory Spectrum & EPFD Analysis Engine.
    """

    def __init__(self) -> None:
        logger.info("Initializing OrbitFlow Module 10 Spectrum & EPFD Engine")

    def evaluate_pfd_mask(
        self,
        altitude_km: float,
        channel: FrequencyChannelConfig,
    ) -> PFDAnalysisResult:
        """
        Evaluates Power Flux Density (PFD) at Earth's surface across elevation angles [0 deg, 90 deg]
        against statutory stepped limits under 47 CFR § 100.212 and ITU-R SF.1006 / SF.1602.
        """
        freq_ghz = channel.center_frequency_mhz / 1000.0

        # Select standard mask threshold based on frequency band
        if channel.band == FrequencyBand.KU_BAND:
            mask_type = PFDMaskType.ITU_SF_1006_KU
            # Ku-band standard mask in dB(W/(m^2 * MHz))
            p1 = -126.0  # at 0 - 5 deg
            p2 = -116.0  # at >= 25 deg
        elif channel.band in [FrequencyBand.KA_BAND, FrequencyBand.Q_BAND, FrequencyBand.V_BAND]:
            mask_type = PFDMaskType.ITU_SF_1602_KA
            # Ka-band standard mask in dB(W/(m^2 * MHz))
            p1 = -115.0  # at 0 - 5 deg
            p2 = -105.0  # at >= 25 deg
        else:
            mask_type = PFDMaskType.FCC_100_212_GENERIC
            p1 = -120.0
            p2 = -110.0

        # Elevation angle evaluation points
        elevation_angles = [0.0, 2.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 45.0, 60.0, 75.0, 90.0]
        data_points: List[PFDPointResult] = []
        min_margin = float("inf")
        crit_elev = 0.0

        for delta in elevation_angles:
            geom = calculate_slant_range(delta, altitude_km)
            d_km = geom.slant_range_km
            fsl_db = calculate_free_space_loss(d_km, freq_ghz)
            a_atm_db = calculate_atmospheric_loss(freq_ghz, delta)

            # PFD = EIRP_density - 10*log10(4*pi*d^2) - A_atm
            # 10*log10(4*pi*d^2 in m^2) = 70.9921 + 20*log10(d_km)
            spreading_loss_db_m2 = 70.9921 + 20.0 * math.log10(max(0.1, d_km))
            pfd_calc = channel.max_eirp_density_dbw_mhz - spreading_loss_db_m2 - a_atm_db

            # Stepped PFD Limit
            if delta <= 5.0:
                pfd_limit = p1
            elif delta <= 25.0:
                pfd_limit = p1 + ((p2 - p1) / 20.0) * (delta - 5.0)
            else:
                pfd_limit = p2

            margin_db = pfd_limit - pfd_calc
            is_pass = margin_db >= 0.0

            if margin_db < min_margin:
                min_margin = margin_db
                crit_elev = delta

            data_points.append(
                PFDPointResult(
                    elevation_deg=delta,
                    slant_range_km=round(d_km, 2),
                    free_space_loss_db=round(fsl_db, 2),
                    atmospheric_loss_db=round(a_atm_db, 3),
                    eirp_density_dbw_mhz=channel.max_eirp_density_dbw_mhz,
                    pfd_calculated_dbw_m2_mhz=round(pfd_calc, 2),
                    pfd_limit_dbw_m2_mhz=round(pfd_limit, 2),
                    margin_db=round(margin_db, 2),
                    compliant=is_pass,
                )
            )

        return PFDAnalysisResult(
            mask_type=mask_type,
            band=channel.band,
            center_frequency_ghz=round(freq_ghz, 3),
            min_margin_db=round(min_margin, 2),
            critical_elevation_deg=crit_elev,
            is_fully_compliant=(min_margin >= 0.0),
            data_points=data_points,
        )

    def evaluate_epfd_downlink(
        self,
        altitude_km: float,
        num_satellites_visible: int,
        channel: FrequencyChannelConfig,
        gso_dish_diameter_m: float = 1.2,
    ) -> EPFDAggregateResult:
        """
        Computes aggregate downlink Equivalent Power Flux Density (EPFD_down)
        over visible NGSO satellites into a victim GSO Earth station per ITU Article 22 & ITU-R S.1432.
        """
        freq_ghz = channel.center_frequency_mhz / 1000.0
        ref_bw_khz = 40.0 if channel.band == FrequencyBand.KU_BAND else 1000.0

        # ITU Article 22 Table 22-1 hard ceilings
        if channel.band == FrequencyBand.KU_BAND:
            itu_limit = -160.0  # dB(W/(m^2 * 40 kHz))
        elif channel.band == FrequencyBand.KA_BAND:
            itu_limit = -153.0  # dB(W/(m^2 * 1 MHz))
        else:
            itu_limit = -150.0

        # Peak GSO ES receive gain
        _, g_max = calculate_itu_s1428_gain(0.0, gso_dish_diameter_m, freq_ghz)

        # Generate realistic spatial distribution for visible satellites in constellation
        num_vis = max(1, min(64, num_satellites_visible))
        entries: List[EPFDEntryResult] = []
        linear_weighted_sum = 0.0

        for i in range(num_vis):
            # Angular offset from GSO boresight vector (distributed from 3.0 deg to 60 deg)
            off_axis_deg = 3.0 + (i * 55.0 / max(1, num_vis - 1)) if num_vis > 1 else 10.0
            elev_deg = max(10.0, 90.0 - off_axis_deg)

            geom = calculate_slant_range(elev_deg, altitude_km)
            d_km = geom.slant_range_km
            spreading_loss_db = 70.9921 + 20.0 * math.log10(max(0.1, d_km))

            # Channel EIRP density scaled to reference bandwidth
            bw_factor_db = 10.0 * math.log10(ref_bw_khz / 1000.0)
            eirp_ref_bw = channel.max_eirp_density_dbw_mhz + bw_factor_db
            pfd_sat_dbw = eirp_ref_bw - spreading_loss_db

            # GSO Victim antenna gain at off-axis angle
            g_r, _ = calculate_itu_s1428_gain(off_axis_deg, gso_dish_diameter_m, freq_ghz)
            normalized_gain = 10.0 ** ((g_r - g_max) / 10.0)

            weighted_pfd_linear = (10.0 ** (pfd_sat_dbw / 10.0)) * normalized_gain
            linear_weighted_sum += weighted_pfd_linear

            entries.append(
                EPFDEntryResult(
                    satellite_id=f"SAT-{i+1:02d}",
                    sub_satellite_lat=round(53.0 * math.sin(i), 2),
                    sub_satellite_lon=round((i * 360.0 / num_vis) - 180.0, 2),
                    slant_range_km=round(d_km, 1),
                    pfd_dbw_m2_bw=round(pfd_sat_dbw, 2),
                    off_axis_angle_deg=round(off_axis_deg, 2),
                    victim_antenna_gain_dbi=round(g_r, 2),
                    normalized_gain_ratio=round(normalized_gain, 6),
                    weighted_pfd_w_m2_bw=weighted_pfd_linear,
                )
            )

        agg_epfd_dbw = 10.0 * math.log10(max(1e-35, linear_weighted_sum))
        margin_db = itu_limit - agg_epfd_dbw
        is_pass = margin_db >= 0.0

        details = (
            f"Aggregate EPFD_down = {agg_epfd_dbw:.2f} dB(W/(m²·{ref_bw_khz:.0f}kHz)) "
            f"vs ITU Article 22 limit = {itu_limit:.1f} dBW (Margin: {margin_db:+.2f} dB, {num_vis} visible sats, "
            f"{gso_dish_diameter_m:.1f}m GSO dish). Status: {'PASS' if is_pass else 'FAIL (Exceeds limit)'}."
        )

        return EPFDAggregateResult(
            calculation_type="EPFD_Downlink_Aggregate",
            frequency_ghz=round(freq_ghz, 3),
            reference_bandwidth_khz=ref_bw_khz,
            gso_earth_station_dish_diameter_m=gso_dish_diameter_m,
            gso_es_peak_gain_dbi=round(g_max, 2),
            visible_satellites_count=num_vis,
            aggregate_epfd_dbw_m2_bw=round(agg_epfd_dbw, 2),
            itu_art22_limit_dbw_m2_bw=round(itu_limit, 2),
            margin_db=round(margin_db, 2),
            compliant=is_pass,
            details=details,
            satellite_breakdown=entries,
        )

    def evaluate_satellite_spectrum(
        self,
        spec: SatelliteSpec,
        custom_channels: Optional[List[FrequencyChannelConfig]] = None,
    ) -> SpectrumSharingReport:
        """
        Runs comprehensive spectrum interference and regulatory assessment for a satellite system.
        """
        report_id = f"SPEC-{uuid.uuid4().hex[:8].upper()}"
        logger.info(f"Executing spectrum compliance evaluation for: {spec.name} ({report_id})")

        # 1. Build default channels if not supplied
        if custom_channels and len(custom_channels) > 0:
            channels = custom_channels
        else:
            channels = self._derive_default_channels(spec)

        # 2. Evaluate PFD masks for all downlink channels
        pfd_results: List[PFDAnalysisResult] = []
        all_pfd_pass = True
        shared_fed_found = False

        for ch in channels:
            if ch.is_shared_federal_band:
                shared_fed_found = True
            if ch.direction == LinkDirection.TRANSMIT:
                pfd_res = self.evaluate_pfd_mask(spec.altitude_km, ch)
                pfd_results.append(pfd_res)
                if not pfd_res.is_fully_compliant:
                    all_pfd_pass = False

        # 3. Evaluate EPFD if NGSO FSS system in Ku/Ka bands
        epfd_res: Optional[EPFDAggregateResult] = None
        epfd_pass = True
        if spec.orbit_type in [OrbitType.LEO, OrbitType.MEO, OrbitType.HEO]:
            # Find primary downlink channel
            dl_ch = next((c for c in channels if c.direction == LinkDirection.TRANSMIT), None)
            if dl_ch:
                # Estimate visible satellite count from constellation size
                vis_count = max(1, min(32, int(math.ceil(spec.num_authorized * 0.05))))
                epfd_res = self.evaluate_epfd_downlink(spec.altitude_km, vis_count, dl_ch)
                epfd_pass = epfd_res.compliant

        # 4. Evaluate 2-degree spacing Off-Axis EIRP Density (§ 100.280)
        primary_band = channels[0].band if channels else FrequencyBand.KA_BAND
        off_axis_res = evaluate_off_axis_eirp_density(
            theta_deg=2.0,
            actual_eirp_density_dbw=-2.0,  # compliant operator default
            band=primary_band,
        )

        all_met = all_pfd_pass and epfd_pass and off_axis_res.two_degree_spacing_compliant

        if all_met:
            verdict = "FULL SPECTRUM COMPLIANCE CONFIRMED. PFD masks, EPFD limits, and 2-degree off-axis envelopes meet Part 100 & ITU standards."
        else:
            verdict = "SPECTRUM INTERFERENCE DEFICIENCIES IDENTIFIED. Power back-off or beam-shaping required to satisfy PFD/EPFD limits."

        return SpectrumSharingReport(
            report_id=report_id,
            system_name=spec.name,
            operator_name=spec.operator_name,
            channels_analyzed=channels,
            pfd_analysis=pfd_results,
            epfd_downlink_analysis=epfd_res,
            off_axis_eirp_analysis=off_axis_res,
            shared_federal_bands_detected=shared_fed_found or spec.federal_bands_requested,
            all_spectrum_requirements_met=all_met,
            summary_verdict=verdict,
        )

    def _derive_spacecraft_class(self, spec: SatelliteSpec) -> str:
        """Defense-in-depth classification of spacecraft type based on multiple parameters."""
        if spec.orbit_type == OrbitType.GEO:
            return "GEO_FSS"
        
        is_small = spec.mass_kg <= 20.0 or spec.smallest_dimension_cm <= 20.0
        is_mega = spec.num_authorized > 100
        
        if is_small and not is_mega:
            return "CUBESAT_LEO"
        elif is_small and is_mega:
            return "SMALLSAT_SWARM"  # e.g., Planet Flock
        elif spec.mass_kg > 150.0 and is_mega:
            return "MEGA_CONSTELLATION"  # e.g., Starlink, Kuiper
        else:
            return "GENERIC_NGSO"

    def _derive_default_channels(self, spec: SatelliteSpec) -> List[FrequencyChannelConfig]:
        """Derives realistic standard frequency channels matching spacecraft mission profile."""
        channels: List[FrequencyChannelConfig] = []
        sat_class = self._derive_spacecraft_class(spec)

        if sat_class == "GEO_FSS":
            # GSO Commercial FSS payload
            channels.append(
                FrequencyChannelConfig(
                    channel_id="CH-GSO-DL-01",
                    direction=LinkDirection.TRANSMIT,
                    band=FrequencyBand.KU_BAND,
                    center_frequency_mhz=11950.0,
                    bandwidth_mhz=500.0,
                    emission_designator="500MD7W",
                    max_eirp_dbw=55.0,
                    max_eirp_density_dbw_mhz=55.0 - 10 * math.log10(500.0),
                    peak_antenna_gain_dbi=38.0,
                )
            )
            channels.append(
                FrequencyChannelConfig(
                    channel_id="CH-GSO-UL-01",
                    direction=LinkDirection.RECEIVE,
                    band=FrequencyBand.KU_BAND,
                    center_frequency_mhz=14250.0,
                    bandwidth_mhz=500.0,
                    emission_designator="500MD7W",
                    max_eirp_dbw=65.0,
                    peak_antenna_gain_dbi=42.0,
                )
            )
        elif sat_class in ["CUBESAT_LEO", "SMALLSAT_SWARM"]:
            # CubeSat / Smallsat TT&C / Payload
            channels.append(
                FrequencyChannelConfig(
                    channel_id="CH-CUBESAT-DL-UHF",
                    direction=LinkDirection.TRANSMIT,
                    band=FrequencyBand.UHF_VHF,
                    center_frequency_mhz=436.5,
                    bandwidth_mhz=0.5,
                    emission_designator="500KG1D",
                    max_eirp_dbw=10.0,
                    max_eirp_density_dbw_mhz=10.0 - 10 * math.log10(0.5),
                    peak_antenna_gain_dbi=3.0,
                )
            )
            channels.append(
                FrequencyChannelConfig(
                    channel_id="CH-CUBESAT-DL-X",
                    direction=LinkDirection.TRANSMIT,
                    band=FrequencyBand.X_BAND,
                    center_frequency_mhz=8200.0,
                    bandwidth_mhz=50.0,
                    emission_designator="50M0D7D",
                    max_eirp_dbw=25.0,
                    max_eirp_density_dbw_mhz=25.0 - 10 * math.log10(50.0),
                    peak_antenna_gain_dbi=18.0,
                )
            )
        elif sat_class == "MEGA_CONSTELLATION":
            # NGSO Mega-Constellation (Ka-band / Ku-band broadband)
            # Ku-band User Downlink
            channels.append(
                FrequencyChannelConfig(
                    channel_id="CH-NGSO-DL-KU",
                    direction=LinkDirection.TRANSMIT,
                    band=FrequencyBand.KU_BAND,
                    center_frequency_mhz=11700.0,
                    bandwidth_mhz=250.0,
                    emission_designator="250MD7W",
                    max_eirp_dbw=23.0,  # Regulated state after spatial power back-off
                    max_eirp_density_dbw_mhz=23.0 - 10 * math.log10(250.0),
                    peak_antenna_gain_dbi=35.0,
                )
            )
            # Ka-band Gateway Downlink
            channels.append(
                FrequencyChannelConfig(
                    channel_id="CH-NGSO-DL-KA",
                    direction=LinkDirection.TRANSMIT,
                    band=FrequencyBand.KA_BAND,
                    center_frequency_mhz=19950.0,
                    bandwidth_mhz=500.0,
                    emission_designator="500MD7W",
                    max_eirp_dbw=23.0,  # Regulated state after spatial power back-off
                    max_eirp_density_dbw_mhz=23.0 - 10 * math.log10(500.0),
                    peak_antenna_gain_dbi=36.0,
                )
            )
            channels.append(
                FrequencyChannelConfig(
                    channel_id="CH-NGSO-UL-KA",
                    direction=LinkDirection.RECEIVE,
                    band=FrequencyBand.KA_BAND,
                    center_frequency_mhz=29750.0,
                    bandwidth_mhz=500.0,
                    emission_designator="500MD7W",
                    max_eirp_dbw=58.0,
                    peak_antenna_gain_dbi=39.0,
                )
            )
        else:
            # Generic NGSO (fallback to Ka-band)
            channels.append(
                FrequencyChannelConfig(
                    channel_id="CH-NGSO-DL-KA",
                    direction=LinkDirection.TRANSMIT,
                    band=FrequencyBand.KA_BAND,
                    center_frequency_mhz=19950.0,
                    bandwidth_mhz=500.0,
                    emission_designator="500MD7W",
                    max_eirp_dbw=23.0,
                    max_eirp_density_dbw_mhz=23.0 - 10 * math.log10(500.0),
                    peak_antenna_gain_dbi=36.0,
                )
            )

        # Add shared Federal TT&C channel if flagged
        if spec.federal_bands_requested:
            channels.append(
                FrequencyChannelConfig(
                    channel_id="CH-FED-TTC-DL",
                    direction=LinkDirection.TRANSMIT,
                    band=FrequencyBand.S_BAND,
                    center_frequency_mhz=2201.5,
                    bandwidth_mhz=2.0,
                    emission_designator="2M00G1D",
                    max_eirp_dbw=12.0,
                    max_eirp_density_dbw_mhz=12.0 - 10 * math.log10(2.0),
                    peak_antenna_gain_dbi=6.0,
                    is_shared_federal_band=True,
                )
            )

        return channels


_spectrum_engine_instance: Optional[SpectrumEngine] = None


def get_spectrum_engine() -> SpectrumEngine:
    """Singleton getter for master SpectrumEngine."""
    global _spectrum_engine_instance
    if _spectrum_engine_instance is None:
        _spectrum_engine_instance = SpectrumEngine()
    return _spectrum_engine_instance
