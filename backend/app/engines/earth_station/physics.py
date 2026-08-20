"""
OrbitFlow Module 19: Earth Station RF Physics & Link Budget Engine
==================================================================
Implements ITU-R P.676 Gaseous Absorption, ITU-R P.618-13 Rain Attenuation,
Antenna Thermodynamics (T_sys, G/T), and Eb/N0 Link Budgets.
"""

from __future__ import annotations

import math

from backend.app.engines.earth_station.models import LinkBudgetCalculation


class EarthStationRFPhysics:
    """Rigorous astrodynamics and RF thermodynamic engine for Earth Station links."""

    R_EARTH_KM: float = 6378.137
    SPEED_OF_LIGHT: float = 299792458.0
    BOLTZMANN_K_DBW_K_HZ: float = -228.60  # 10*log10(1.380649e-23)

    @classmethod
    def calculate_antenna_gain_dbi(
        cls, diameter_m: float, frequency_ghz: float, efficiency: float = 0.65
    ) -> float:
        """Peak directive antenna gain from aperture diameter and efficiency."""
        wavelength_m = cls.SPEED_OF_LIGHT / (frequency_ghz * 1e9)
        gain_linear = efficiency * ((math.pi * diameter_m) / wavelength_m) ** 2
        return 10.0 * math.log10(max(1.0, gain_linear))

    @classmethod
    def calculate_slant_range_km(
        cls, elevation_deg: float, altitude_km: float = 600.0
    ) -> float:
        """Topocentric slant range geometry for spherical Earth."""
        elev = max(0.0, min(90.0, float(elevation_deg)))
        delta_rad = math.radians(elev)
        r = cls.R_EARTH_KM
        h = altitude_km
        term = (r * math.sin(delta_rad)) ** 2 + 2.0 * r * h + h ** 2
        return (2.0 * r * h + h ** 2) / (math.sqrt(term) + r * math.sin(delta_rad))

    @classmethod
    def calculate_free_space_loss_db(
        cls, slant_range_km: float, frequency_ghz: float
    ) -> float:
        """Free space basic transmission loss."""
        return 92.4478 + 20.0 * math.log10(slant_range_km) + 20.0 * math.log10(frequency_ghz)

    @classmethod
    def calculate_atmospheric_loss_p676(
        cls, frequency_ghz: float, elevation_deg: float
    ) -> float:
        """Gaseous absorption by oxygen and water vapor per ITU-R P.676-13."""
        elev = max(5.0, min(90.0, float(elevation_deg)))
        f = frequency_ghz
        if f < 50.0:
            gamma_o = (7.2e-3 / (1.0 + (f / 60.0) ** 2)) * (f ** 2 / (f ** 2 + 0.36))
        else:
            gamma_o = 15.0 / (1.0 + ((f - 60.0) / 2.0) ** 2)
        gamma_w = 0.05 + 0.0021 * 7.5 + (3.6 / ((f - 22.235) ** 2 + 9.0)) * (f ** 2 / 100.0)
        return (gamma_o * 6.0 + gamma_w * 2.0) / math.sin(math.radians(elev))

    @classmethod
    def calculate_rain_attenuation_p618(
        cls,
        frequency_ghz: float,
        elevation_deg: float,
        lat_deg: float,
        availability_pct: float = 99.9,
    ) -> float:
        """Rain attenuation for Earth-space links per ITU-R P.618-13."""
        elev = max(5.0, min(90.0, float(elevation_deg)))
        r001 = 42.0 if abs(lat_deg) > 25.0 else 95.0
        k = 0.187 if frequency_ghz > 25.0 else 0.075
        alpha = 1.05 if frequency_ghz > 25.0 else 1.15
        gamma_r = k * (r001 ** alpha)

        h_0 = 4.0 if abs(lat_deg) < 30.0 else 2.5
        h_r = h_0 + 0.36
        l_s = (h_r - 0.01) / math.sin(math.radians(elev))
        l_g = l_s * math.cos(math.radians(elev))
        r_001 = 1.0 / (1.0 + 0.78 * math.sqrt(max(0.01, l_g * gamma_r / frequency_ghz)) - 0.38 * (1.0 - math.exp(-2.0 * l_g)))
        l_e = l_s * r_001
        a_001 = gamma_r * l_e

        p = 100.0 - availability_pct
        beta = 0.0
        exp_factor = -(0.655 + 0.033 * math.log(p) - 0.045 * math.log(max(0.01, a_001)) - beta * (1.0 - p) * math.sin(math.radians(elev)))
        return max(0.1, a_001 * ((p / 0.01) ** exp_factor))

    @classmethod
    def calculate_gt_and_noise_temp(
        cls,
        rx_gain_dbi: float,
        feed_loss_db: float,
        lna_temp_k: float,
        a_total_db: float,
    ) -> tuple[float, float]:
        """Calculates system noise temperature and G/T figure of merit."""
        l_feed = 10.0 ** (feed_loss_db / 10.0)
        t_m = 275.0
        t_cosmic = 2.73
        loss_lin = 10.0 ** (-a_total_db / 10.0)
        t_sky = t_m * (1.0 - loss_lin) + t_cosmic * loss_lin
        t_ground = 290.0 * 0.05
        t_ant = (t_sky / l_feed) + t_ground
        t_sys = t_ant + 290.0 * (l_feed - 1.0) + l_feed * lna_temp_k
        g_t = rx_gain_dbi - 10.0 * math.log10(t_sys)
        return g_t, t_sys

    @classmethod
    def evaluate_downlink_budget(
        cls,
        frequency_ghz: float = 19.7,
        satellite_altitude_km: float = 600.0,
        elevation_deg: float = 25.0,
        lat_deg: float = 28.5,
        sat_eirp_dbw: float = 52.0,
        dish_diameter_m: float = 9.0,
        feed_loss_db: float = 0.45,
        lna_temp_k: float = 95.0,
        user_bit_rate_mbps: float = 500.0,
        required_eb_n0_db: float = 8.5,
    ) -> LinkBudgetCalculation:
        """Comprehensive downlink clear-sky vs. rain-faded link budget."""
        slant_km = cls.calculate_slant_range_km(elevation_deg, satellite_altitude_km)
        fsl_db = cls.calculate_free_space_loss_db(slant_km, frequency_ghz)
        a_atm = cls.calculate_atmospheric_loss_p676(frequency_ghz, elevation_deg)
        a_rain = cls.calculate_rain_attenuation_p618(frequency_ghz, elevation_deg, lat_deg)

        rx_gain = cls.calculate_antenna_gain_dbi(dish_diameter_m, frequency_ghz)
        gt_clear, _ = cls.calculate_gt_and_noise_temp(rx_gain, feed_loss_db, lna_temp_k, a_atm)
        gt_rain, _ = cls.calculate_gt_and_noise_temp(rx_gain, feed_loss_db, lna_temp_k, a_atm + a_rain)

        c_n0_clear = sat_eirp_dbw - fsl_db - a_atm + gt_clear - cls.BOLTZMANN_K_DBW_K_HZ
        c_n0_rain = sat_eirp_dbw - fsl_db - (a_atm + a_rain) + gt_rain - cls.BOLTZMANN_K_DBW_K_HZ

        bit_rate_hz = user_bit_rate_mbps * 1e6
        eb_n0_rain = c_n0_rain - 10.0 * math.log10(bit_rate_hz)
        margin = eb_n0_rain - required_eb_n0_db

        return LinkBudgetCalculation(
            frequency_ghz=frequency_ghz,
            elevation_deg=elevation_deg,
            slant_range_km=round(slant_km, 2),
            free_space_loss_db=round(fsl_db, 2),
            atmospheric_loss_db=round(a_atm, 2),
            rain_attenuation_db=round(a_rain, 2),
            clear_sky_g_t_db_k=round(gt_clear, 2),
            rain_faded_g_t_db_k=round(gt_rain, 2),
            eirp_dbw=sat_eirp_dbw,
            c_n0_clear_sky_db_hz=round(c_n0_clear, 2),
            c_n0_rain_faded_db_hz=round(c_n0_rain, 2),
            user_bit_rate_mbps=user_bit_rate_mbps,
            eb_n0_received_rain_db=round(eb_n0_rain, 2),
            eb_n0_required_db=required_eb_n0_db,
            link_margin_rain_db=round(margin, 2),
            is_link_closed=(margin >= 0.0),
        )
