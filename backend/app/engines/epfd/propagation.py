"""
OrbitFlow Module 10: Spectrum & EPFD Engine — Atmospheric & Geometric Propagation
=================================================================================
Implements exact slant range geometry, free-space basic transmission loss, 
and ITU-R P.676 atmospheric gaseous absorption under clear-sky conditions.
"""

from __future__ import annotations

import math
from backend.app.engines.epfd.models import SlantRangeResult

# Physical Constants
R_EARTH_KM: float = 6378.137  # WGS-84 Equatorial Radius in km
SPEED_OF_LIGHT_MPS: float = 299792458.0


def calculate_slant_range(
    elevation_deg: float,
    altitude_km: float,
    r_earth: float = R_EARTH_KM,
) -> SlantRangeResult:
    """
    Computes exact topocentric slant range d(delta, h) from an Earth station to a satellite
    using IEEE-754 rationalized algebraic form to avoid catastrophic floating-point cancellation.

    Parameters:
        elevation_deg: Topocentric elevation angle above horizon in degrees [0.0, 90.0]
        altitude_km: Satellite orbital altitude above mean Earth radius in km (> 0)
        r_earth: Equatorial Earth radius in km (default: 6378.137 km)

    Returns:
        SlantRangeResult with slant range, Earth central angle, and satellite off-nadir angle.
    """
    elev = max(0.0, min(90.0, float(elevation_deg)))
    h = max(0.1, float(altitude_km))

    delta_rad = math.radians(elev)
    sin_delta = math.sin(delta_rad)
    cos_delta = math.cos(delta_rad)

    term_under_sqrt = (r_earth * sin_delta) ** 2 + 2.0 * r_earth * h + h ** 2
    sqrt_term = math.sqrt(term_under_sqrt)

    # Rationalized numerical stable form: (2*R*h + h^2) / (sqrt(...) + R*sin(delta))
    numerator = 2.0 * r_earth * h + h ** 2
    denominator = sqrt_term + r_earth * sin_delta
    d = numerator / denominator

    # Satellite off-nadir angle eta: sin(eta) = (R_E / (R_E + h)) * cos(delta)
    sin_eta = (r_earth / (r_earth + h)) * cos_delta
    sin_eta = min(1.0, max(-1.0, sin_eta))
    eta_deg = math.degrees(math.asin(sin_eta))

    # Earth central angle psi: psi = arccos((R_E / (R_E + h)) * cos(delta)) - delta
    cos_psi_plus_delta = sin_eta
    psi_plus_delta_deg = math.degrees(math.acos(cos_psi_plus_delta))
    psi_deg = max(0.0, psi_plus_delta_deg - elev)

    return SlantRangeResult(
        elevation_deg=round(elev, 2),
        altitude_km=round(h, 2),
        slant_range_km=round(d, 3),
        earth_central_angle_deg=round(psi_deg, 3),
        satellite_off_nadir_deg=round(eta_deg, 3),
    )


def calculate_free_space_loss(slant_range_km: float, frequency_ghz: float) -> float:
    """
    Computes free-space basic transmission loss L_bf (dB) per ITU-R P.525.
    L_bf = 92.4478 + 20*log10(d_km) + 20*log10(f_GHz)
    """
    d = max(0.1, float(slant_range_km))
    f = max(0.01, float(frequency_ghz))
    return 92.447781 + 20.0 * math.log10(d) + 20.0 * math.log10(f)


def calculate_atmospheric_loss(frequency_ghz: float, elevation_deg: float) -> float:
    """
    Computes clear-sky atmospheric gaseous absorption loss A_atm (dB) using ITU-R P.676-13
    equivalent scale height approximation (Oxygen h_o=6.0 km and Water Vapor h_w=2.0 km).
    """
    f = max(0.1, float(frequency_ghz))
    elev = max(0.0, min(90.0, float(elevation_deg)))
    sin_delta = math.sin(math.radians(elev))

    # Specific attenuation at sea level gamma_o (dB/km) for Oxygen (ITU-R P.676 approx)
    # Strong resonance around 60 GHz
    if f < 50.0:
        gamma_o = (7.2e-3 / (1.0 + (f / 60.0) ** 2)) * (f ** 2 / (f ** 2 + 0.36))
    else:
        # Near 60 GHz oxygen complex
        gamma_o = 15.0 / (1.0 + ((f - 60.0) / 2.0) ** 2)

    # Specific attenuation at sea level gamma_w (dB/km) for Water Vapor (7.5 g/m^3 humidity)
    # Resonance peak around 22.235 GHz
    f_w_term = (f - 22.235) ** 2 + 9.0
    gamma_w = 0.05 + 0.0021 * 7.5 + (3.6 / f_w_term) * (f ** 2 / 100.0)

    # Equivalent scale heights
    h_o = 6.0  # km
    h_w = 2.0  # km

    # Path length through atmosphere accounting for Earth curvature (P.676 Section 2.2)
    path_o = h_o / math.sqrt(sin_delta ** 2 + (2.0 * h_o / R_EARTH_KM))
    path_w = h_w / math.sqrt(sin_delta ** 2 + (2.0 * h_w / R_EARTH_KM))

    total_loss_db = (gamma_o * path_o) + (gamma_w * path_w)
    return max(0.02, round(total_loss_db, 3))
