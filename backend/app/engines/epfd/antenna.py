"""
OrbitFlow Module 10: Spectrum & EPFD Engine — Antenna Radiation Patterns & Off-Axis Masks
=========================================================================================
Implements ITU-R S.1428 / S.465 / S.580 Earth station antenna gain patterns and 
FCC 47 CFR § 100.280 (§ 25.218 / § 25.138) Off-Axis EIRP Density envelopes.
"""

from __future__ import annotations

import math
from typing import Tuple, Optional
from backend.app.engines.epfd.models import FrequencyBand, OffAxisEIRPCheckResult

SPEED_OF_LIGHT_MPS: float = 299792458.0


def calculate_itu_s1428_gain(
    theta_deg: float,
    diameter_m: float,
    frequency_ghz: float,
    efficiency: float = 0.7,
) -> Tuple[float, float]:
    """
    Calculates reference Earth station antenna receive gain G(theta) in dBi and peak gain G_max
    in accordance with ITU-R S.1428 (10.7 to 30 GHz).

    Parameters:
        theta_deg: Off-axis angle in degrees from antenna boresight
        diameter_m: Circular aperture dish diameter in meters
        frequency_ghz: Carrier frequency in GHz
        efficiency: Aperture efficiency (default: 0.70)

    Returns:
        (gain_dbi, peak_gain_gmax_dbi)
    """
    diam = max(0.2, float(diameter_m))
    freq = max(0.5, float(frequency_ghz))
    wavelength_m = SPEED_OF_LIGHT_MPS / (freq * 1e9)
    d_over_lambda = diam / wavelength_m

    # Peak on-axis gain
    g_max = 10.0 * math.log10(efficiency * (math.pi * d_over_lambda) ** 2)
    g1 = 2.0 + 15.0 * math.log10(d_over_lambda)

    theta_m = (20.0 / d_over_lambda) * math.sqrt(max(0.0, g_max - g1))
    theta_r = 15.85 * (d_over_lambda ** -0.6)

    theta = abs(float(theta_deg))
    if theta < 1e-4:
        return round(g_max, 2), round(g_max, 2)

    if theta < theta_m:
        gain = g_max - 2.5e-3 * ((d_over_lambda * theta) ** 2)
    elif theta < theta_r:
        gain = g1
    elif theta < 48.0:
        gain = 29.0 - 25.0 * math.log10(theta)
    else:
        gain = -10.0

    return round(gain, 2), round(g_max, 2)


def evaluate_off_axis_eirp_density(
    theta_deg: float,
    actual_eirp_density_dbw: float,
    band: FrequencyBand,
    actual_cross_polar_dbw: Optional[float] = None,
) -> OffAxisEIRPCheckResult:
    """
    Evaluates Earth station off-axis EIRP density against FCC 47 CFR § 100.280 (§ 25.218 / § 25.138)
    for 2-degree GSO orbital spacing co-existence.

    Parameters:
        theta_deg: Off-axis angle in degrees from main beam axis
        actual_eirp_density_dbw: Operator's measured/computed off-axis EIRP density in dBW/ref_bw
        band: Operational frequency band (Ku, Ka, etc.)
        actual_cross_polar_dbw: Optional cross-polar EIRP density in dBW/ref_bw

    Returns:
        OffAxisEIRPCheckResult with compliance status and 2-degree spacing verification.
    """
    theta = abs(float(theta_deg))
    actual_copolar = float(actual_eirp_density_dbw)

    if band == FrequencyBand.KU_BAND:
        ref_bw_khz = 4.0
        # § 100.280 / § 25.218(f) Ku-band co-polar mask
        if theta < 1.5:
            copolar_limit = 15.0 - 25.0 * math.log10(1.5)  # extrapolated
        elif theta <= 7.0:
            copolar_limit = 15.0 - 25.0 * math.log10(theta)
        elif theta <= 9.2:
            copolar_limit = -6.0
        elif theta <= 48.0:
            copolar_limit = 18.0 - 25.0 * math.log10(theta)
        else:
            copolar_limit = -24.0

        # Cross-polar mask
        if theta <= 7.0:
            cross_limit = 5.0 - 25.0 * math.log10(max(1.5, theta))
        elif theta <= 9.2:
            cross_limit = -16.0
        else:
            cross_limit = -20.0

    elif band == FrequencyBand.KA_BAND:
        ref_bw_khz = 40.0
        # § 100.280 / § 25.218(i) Ka-band co-polar mask
        if theta < 2.0:
            copolar_limit = 32.5 - 25.0 * math.log10(2.0)
        elif theta <= 7.0:
            copolar_limit = 32.5 - 25.0 * math.log10(theta)
        elif theta <= 9.2:
            copolar_limit = 11.4
        elif theta <= 48.0:
            copolar_limit = 35.5 - 25.0 * math.log10(theta)
        else:
            copolar_limit = -6.5

        cross_limit = copolar_limit - 10.0

    else:
        ref_bw_khz = 4.0
        # Generic § 100.280 default envelope (29 - 25*log10(theta))
        if theta < 2.0:
            copolar_limit = 29.0 - 25.0 * math.log10(2.0)
        elif theta <= 48.0:
            copolar_limit = 29.0 - 25.0 * math.log10(theta)
        else:
            copolar_limit = -10.0
        cross_limit = copolar_limit - 10.0

    copolar_pass = (actual_copolar <= copolar_limit)
    cross_pass = (actual_cross_polar_dbw <= cross_limit) if actual_cross_polar_dbw is not None else True

    # 2-degree spacing check: at theta >= 2.0 deg, emissions must not exceed mask
    two_deg_pass = copolar_pass and (cross_pass if actual_cross_polar_dbw is not None else True)

    details = (
        f"Off-axis angle θ={theta:.2f}°: Actual={actual_copolar:.2f} dBW vs Limit={copolar_limit:.2f} dBW "
        f"({band.value}, ref BW={ref_bw_khz:.0f} kHz). "
        f"Status: {'PASS' if two_deg_pass else 'FAIL (Exceeds 2-degree spacing mask)'}."
    )

    return OffAxisEIRPCheckResult(
        frequency_band=band,
        reference_bandwidth_khz=ref_bw_khz,
        theta_deg=round(theta, 2),
        actual_eirp_density_dbw=round(actual_copolar, 2),
        copolar_limit_dbw=round(copolar_limit, 2),
        cross_polar_limit_dbw=round(cross_limit, 2) if actual_cross_polar_dbw is not None else None,
        copolar_compliant=copolar_pass,
        cross_polar_compliant=cross_pass if actual_cross_polar_dbw is not None else None,
        two_degree_spacing_compliant=two_deg_pass,
        details=details,
    )
