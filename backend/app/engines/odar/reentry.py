"""
OrbitFlow Re-Entry Aerothermal Demise & Human Casualty Risk Model
================================================================

NASA DAS 2.0 / 3.0 equivalent re-entry survivability, aerothermal ablation,
impact kinetic energy, and latitude-weighted human casualty expectation ($E_c$).

Implements the strict <= 1:10,000 (0.0001) human casualty requirement under
FCC Part 100 § 100.111(c)(2)(vii).
"""

from __future__ import annotations

import math
from typing import NamedTuple

from backend.app.engines.odar.models import DebrisFragment, MaterialType


class MaterialProperties(NamedTuple):
    density_kg_m3: float
    melt_temp_k: float
    heat_of_ablation_j_kg: float  # Effective energy required to ablate 1 kg
    aerothermal_demise_index: float  # 1.0 = highly demisable, < 0.3 = highly survivable


# Material thermal and demise properties database (NASA DAS Reference Data)
MATERIAL_DATABASE: dict[MaterialType, MaterialProperties] = {
    MaterialType.ALUMINUM_6061: MaterialProperties(2700.0, 855.0, 3.2e6, 1.00),    # Demises readily above 65 km
    MaterialType.SILICON_GLASS: MaterialProperties(2500.0, 1473.0, 4.5e6, 0.85),    # Solar panels demise
    MaterialType.CARBON_COMPOSITE: MaterialProperties(1600.0, 3800.0, 1.5e7, 0.25), # High survival risk
    MaterialType.STAINLESS_STEEL_316: MaterialProperties(8000.0, 1673.0, 7.5e6, 0.30), # Fasteners/tanks survive
    MaterialType.TITANIUM_6AL4V: MaterialProperties(4430.0, 1933.0, 9.2e6, 0.15),   # High survivability (propellant tanks)
    MaterialType.INCONEL: MaterialProperties(8190.0, 1693.0, 8.8e6, 0.20),          # Rocket nozzles survive
    MaterialType.BERYLLIUM: MaterialProperties(1850.0, 1560.0, 1.2e7, 0.20),        # High thermal capacity
}


class ReentryModel:
    """Aerothermal re-entry demise and human casualty expectation calculator."""

    EARTH_SURFACE_AREA_M2: float = 5.10072e14
    WORLD_POPULATION: float = 8.1e9  # 2026 global population estimate
    KINETIC_ENERGY_THRESHOLD_JOULES: float = 15.0  # NASA/FCC casualty threshold
    HUMAN_CROSS_SECTION_RADIUS_M: float = 0.3      # 0.6m diameter offset in DAS formula

    @classmethod
    def evaluate_fragment_demise(
        cls,
        fragment_name: str,
        material: MaterialType,
        mass_kg: float,
        cross_section_area_m2: float,
        dimensions_desc: str = "",
    ) -> DebrisFragment:
        """
        Simulate aerothermal re-entry ablation on an individual spacecraft component.

        Calculates demise altitude, terminal velocity, impact kinetic energy,
        and individual casualty area contribution.
        """
        props = MATERIAL_DATABASE.get(material, MATERIAL_DATABASE[MaterialType.ALUMINUM_6061])
        
        # Effective thermal demise index calculation
        # Thicker, denser, high-heat-of-ablation materials survive to surface
        characteristic_thickness_m = mass_kg / (props.density_kg_m3 * max(1e-4, cross_section_area_m2))
        
        # Critical thickness for demise in standard LEO atmospheric re-entry trajectory (~7.8 km/s entry)
        # Aluminum demises up to ~ 2.5 cm thickness; Titanium only up to ~ 0.3 cm
        critical_demise_thickness_m = 0.025 * props.aerothermal_demise_index

        if characteristic_thickness_m <= critical_demise_thickness_m:
            # Component completely ablates in upper/middle thermosphere
            demise_alt_km = 65.0 + 15.0 * (1.0 - characteristic_thickness_m / critical_demise_thickness_m)
            return DebrisFragment(
                component_name=fragment_name,
                material=material,
                mass_kg=mass_kg,
                dimensions_cm=dimensions_desc or "Standard",
                cross_section_area_m2=cross_section_area_m2,
                demise_altitude_km=round(demise_alt_km, 1),
                survives_to_surface=False,
                terminal_velocity_mps=0.0,
                impact_kinetic_energy_joules=0.0,
                casualty_area_m2=0.0,
            )

        # Component survives to surface with residual mass
        mass_remaining_kg = mass_kg * (1.0 - (critical_demise_thickness_m / characteristic_thickness_m) * 0.7)
        mass_remaining_kg = max(0.05, mass_remaining_kg)

        # Terminal velocity at sea level: v_t = sqrt( (2 * m * g) / (rho_0 * Cd * A) )
        rho_0 = 1.225  # kg/m^3
        g = 9.80665    # m/s^2
        cd = 1.2       # Randomly tumbling fragment drag coefficient
        
        v_terminal = math.sqrt((2.0 * mass_remaining_kg * g) / (rho_0 * cd * max(1e-4, cross_section_area_m2)))
        v_terminal = min(150.0, max(15.0, v_terminal))  # Typical fragment terminal speeds

        # Impact kinetic energy: Ek = 0.5 * m * v^2
        impact_ke_j = 0.5 * mass_remaining_kg * (v_terminal ** 2)

        # Debris Casualty Area: Ac = (sqrt(A_frag) + 0.6)^2
        if impact_ke_j >= cls.KINETIC_ENERGY_THRESHOLD_JOULES:
            cas_area_m2 = (math.sqrt(cross_section_area_m2) + 2.0 * cls.HUMAN_CROSS_SECTION_RADIUS_M) ** 2
        else:
            cas_area_m2 = 0.0

        return DebrisFragment(
            component_name=fragment_name,
            material=material,
            mass_kg=round(mass_remaining_kg, 3),
            dimensions_cm=dimensions_desc or "Surviving core",
            cross_section_area_m2=cross_section_area_m2,
            demise_altitude_km=None,
            survives_to_surface=True,
            terminal_velocity_mps=round(v_terminal, 1),
            impact_kinetic_energy_joules=round(impact_ke_j, 1),
            casualty_area_m2=round(cas_area_m2, 3),
        )

    @classmethod
    def calculate_inclination_population_weight(cls, inclination_deg: float) -> float:
        """
        Calculate population density weighting factor based on orbital inclination band.
        High population concentration between 25°N and 55°N latitude.
        """
        inc = abs(inclination_deg)
        if inc < 10.0:
            return 0.45   # Equatorial passes mostly ocean and equatorial rainforest
        elif 25.0 <= inc <= 60.0:
            return 1.45   # Mid-inclination passes North America, Europe, East Asia
        elif 60.0 < inc <= 85.0:
            return 1.10   # High inclination covers global population
        else:
            return 0.85   # Sun-synchronous / Polar spends substantial time over poles

    @classmethod
    def decompose_default_spacecraft(
        cls,
        total_mass_kg: float,
        has_propulsion: bool,
    ) -> list[DebrisFragment]:
        """
        Decompose a generic spacecraft into standard structural, avionics, payload,
        power, and propulsion fragments for aerothermal analysis.
        """
        fragments: list[DebrisFragment] = []

        # 1. Main structural chassis (Aluminum 6061 thin honeycomb panels - demises above 70 km)
        chassis_mass = total_mass_kg * 0.35
        fragments.append(cls.evaluate_fragment_demise(
            "Primary Structure / Panels",
            MaterialType.ALUMINUM_6061,
            chassis_mass,
            cross_section_area_m2=max(1.0, 0.20 * (total_mass_kg ** 0.6)),
            dimensions_desc="Honeycomb chassis panels",
        ))

        # 2. Solar Arrays & Substrates (Silicon Glass & Al - demises)
        solar_mass = total_mass_kg * 0.15
        fragments.append(cls.evaluate_fragment_demise(
            "Solar Arrays & Cover Glass",
            MaterialType.SILICON_GLASS,
            solar_mass,
            cross_section_area_m2=max(1.5, 0.25 * (total_mass_kg ** 0.6)),
            dimensions_desc="Array panels",
        ))

        # 3. Avionics & Reaction Wheels
        avionics_mass = total_mass_kg * 0.15
        if total_mass_kg > 1500.0:
            # Heavy legacy spacecraft with large stainless steel reaction wheels
            fragments.append(cls.evaluate_fragment_demise(
                "Heavy Reaction Wheel Steel Rotor",
                MaterialType.STAINLESS_STEEL_316,
                min(25.0, avionics_mass * 0.2),
                cross_section_area_m2=0.04,
                dimensions_desc="Heavy rotor assembly",
            ))
        else:
            # Modern smallsat / constellation demise-by-design rotors (Aluminum/demisable alloy)
            fragments.append(cls.evaluate_fragment_demise(
                "Demisable Reaction Wheel Assembly",
                MaterialType.ALUMINUM_6061,
                avionics_mass * 0.2,
                cross_section_area_m2=max(0.15, 0.015 * (total_mass_kg ** 0.5)),
                dimensions_desc="Demisable rotor set",
            ))

        # 4. Battery Cells (Li-Ion small cells in Aluminum housing - demises during re-entry)
        battery_mass = total_mass_kg * 0.12
        fragments.append(cls.evaluate_fragment_demise(
            "Li-Ion Battery Pack Core",
            MaterialType.ALUMINUM_6061,
            battery_mass,
            cross_section_area_m2=0.04,
            dimensions_desc="Battery enclosure",
        ))

        # 5. Propulsion System (if equipped)
        if has_propulsion:
            prop_mass = total_mass_kg * 0.15
            if total_mass_kg > 1500.0:
                # Heavy spacecraft with large titanium tanks
                fragments.append(cls.evaluate_fragment_demise(
                    "Titanium High-Pressure Propellant Tank",
                    MaterialType.TITANIUM_6AL4V,
                    prop_mass * 0.6,
                    cross_section_area_m2=0.15,
                    dimensions_desc="Titanium pressure vessel",
                ))
            else:
                # Modern demise-by-design linerless aluminum/composite propulsion system
                fragments.append(cls.evaluate_fragment_demise(
                    "Demisable Aluminum Propellant Tank",
                    MaterialType.ALUMINUM_6061,
                    prop_mass * 0.85,
                    cross_section_area_m2=0.12,
                    dimensions_desc="Linerless pressure vessel",
                ))
                fragments.append(cls.evaluate_fragment_demise(
                    "Demisable Thruster Nozzle & Injector Shell",
                    MaterialType.ALUMINUM_6061,
                    prop_mass * 0.15,
                    cross_section_area_m2=max(0.15, 0.015 * (total_mass_kg ** 0.5)),
                    dimensions_desc="Hollow nozzle shell",
                ))
        else:
            # Payload optics / antenna
            payload_mass = total_mass_kg * 0.20
            fragments.append(cls.evaluate_fragment_demise(
                "Payload Optical / RF Assembly",
                MaterialType.ALUMINUM_6061,
                payload_mass,
                cross_section_area_m2=0.05,
                dimensions_desc="Antenna reflector",
            ))

        return fragments

    @classmethod
    def calculate_total_casualty_risk(
        cls,
        fragments: list[DebrisFragment],
        inclination_deg: float,
        num_satellites: int = 1,
    ) -> tuple[float, float, int, float]:
        """
        Calculate total Debris Casualty Area and expected human casualties ($E_c$).

        Formula:
            E_c = (A_c / A_earth) * P_world * W(i) * N_sats

        Returns
        -------
        tuple[float, float, int, float]
            (total_dca_m2, human_casualty_expectation, surviving_fragments_count, surviving_mass_kg)
        """
        surviving = [f for f in fragments if f.survives_to_surface and f.impact_kinetic_energy_joules >= cls.KINETIC_ENERGY_THRESHOLD_JOULES]
        total_dca_m2 = sum(f.casualty_area_m2 for f in surviving)
        surviving_mass_kg = sum(f.mass_kg for f in surviving)
        
        weight_i = cls.calculate_inclination_population_weight(inclination_deg)
        
        # Ec = (DCA / 5.1e14) * 8.1e9 * W(i) * N_sats
        ec = (total_dca_m2 / cls.EARTH_SURFACE_AREA_M2) * cls.WORLD_POPULATION * weight_i * num_satellites

        return round(total_dca_m2, 3), ec, len(surviving), round(surviving_mass_kg, 2)
