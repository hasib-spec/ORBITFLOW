"""
OrbitFlow Atmospheric Density Model
===================================

Physics-grounded atmospheric density calculator parameterized by orbital altitude,
solar 10.7cm radio flux (F10.7), and geomagnetic activity (Ap).

Combines US Standard Atmosphere 1976 lower-thermosphere profiles with Jacchia-Roberts /
NRLMSISE-00 empirical solar cycle density scaling.
"""

from __future__ import annotations

import math
from typing import NamedTuple


class AtmosphereLayer(NamedTuple):
    base_alt_km: float
    base_density_kg_m3: float
    scale_height_km: float


# Empirical scale height tables (US Standard Atmosphere / Jacchia 1977)
ATMOSPHERE_LAYERS: list[AtmosphereLayer] = [
    AtmosphereLayer(100.0, 5.297e-7, 5.877),
    AtmosphereLayer(110.0, 9.661e-8, 7.263),
    AtmosphereLayer(120.0, 2.438e-8, 9.473),
    AtmosphereLayer(130.0, 8.484e-9, 12.636),
    AtmosphereLayer(140.0, 3.845e-9, 16.149),
    AtmosphereLayer(150.0, 2.070e-9, 22.523),
    AtmosphereLayer(180.0, 5.464e-10, 29.740),
    AtmosphereLayer(200.0, 2.789e-10, 37.105),
    AtmosphereLayer(250.0, 7.248e-11, 45.546),
    AtmosphereLayer(300.0, 2.418e-11, 53.628),
    AtmosphereLayer(350.0, 9.518e-12, 53.298),
    AtmosphereLayer(400.0, 3.725e-12, 58.515),
    AtmosphereLayer(450.0, 1.585e-12, 60.828),
    AtmosphereLayer(500.0, 6.967e-13, 63.822),
    AtmosphereLayer(600.0, 1.454e-13, 71.835),
    AtmosphereLayer(700.0, 3.614e-14, 88.667),
    AtmosphereLayer(800.0, 1.170e-14, 124.64),
    AtmosphereLayer(900.0, 5.245e-15, 181.05),
    AtmosphereLayer(1000.0, 3.019e-15, 268.00),
]


class AtmosphereModel:
    """Calculates atmospheric density at any arbitrary LEO/MEO altitude."""

    @staticmethod
    def get_density(altitude_km: float, f107_solar_flux: float = 120.0, ap_index: float = 15.0) -> float:
        """
        Calculate total mass density rho (kg/m^3) at specified altitude.

        Parameters
        ----------
        altitude_km : float
            Geodetic altitude in kilometers.
        f107_solar_flux : float
            Penticton 10.7cm solar radio flux (sfu). Nominal average = 120.0, Solar Max = 200.0, Solar Min = 70.0.
        ap_index : float
            Geomagnetic planetary amplitude index (gamma). Nominal = 15.0.

        Returns
        -------
        float
            Atmospheric density in kg/m^3.
        """
        if altitude_km <= 0.0:
            return 1.225  # Sea level standard density

        if altitude_km < 100.0:
            # Barometric formula for lower atmosphere
            h = altitude_km * 1000.0
            return 1.225 * math.exp(-h / 7200.0)

        # Above 1000 km, density decays exponentially with exospheric scale height ~ 350 km
        if altitude_km >= 1000.0:
            layer = ATMOSPHERE_LAYERS[-1]
            dh = altitude_km - layer.base_alt_km
            base_rho = layer.base_density_kg_m3 * math.exp(-dh / 350.0)
        else:
            # Find the appropriate bounding layer
            layer = ATMOSPHERE_LAYERS[0]
            for i in range(len(ATMOSPHERE_LAYERS) - 1):
                if ATMOSPHERE_LAYERS[i].base_alt_km <= altitude_km < ATMOSPHERE_LAYERS[i + 1].base_alt_km:
                    layer = ATMOSPHERE_LAYERS[i]
                    break
            dh = altitude_km - layer.base_alt_km
            base_rho = layer.base_density_kg_m3 * math.exp(-dh / layer.scale_height_km)

        # Solar activity scaling factor (NRLMSISE-00 thermospheric response)
        # Solar heating expands thermosphere, exponentially increasing density at high altitudes
        solar_sensitivity = min(0.018, 0.0025 * (altitude_km / 200.0))
        solar_delta = f107_solar_flux - 120.0
        solar_multiplier = math.exp(solar_sensitivity * solar_delta)

        # Geomagnetic storm correction
        geomag_multiplier = 1.0 + 0.005 * (ap_index - 15.0)

        density = base_rho * solar_multiplier * geomag_multiplier
        return max(1.0e-20, density)
