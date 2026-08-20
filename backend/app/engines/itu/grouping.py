"""
OrbitFlow Module 12: ITU Frequency Grouping Optimization Algorithm
==================================================================
Partitions raw RF carrier specs into canonical ITU Radiocommunication Bureau (BR)
Groups (grp) in accordance with ITU Radio Regulations Appendix 4.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List

from backend.app.engines.itu.models import ITUCarrier, ITUGroupData


def partition_and_build_itu_groups(carriers: List[ITUCarrier]) -> List[ITUGroupData]:
    """
    Partitions raw carriers into canonical ITU Appendix 4 Groups.

    Grouping Invariant Key:
        K_grp = (beam_id, direction, station_class, nature_of_service,
                 polarization, service_area_id, pattern_co_id, pattern_cross_id)
    """
    grouped_buckets: dict[tuple, list[ITUCarrier]] = defaultdict(list)

    for c in carriers:
        key = (
            c.beam_id,
            c.direction.value,
            c.station_class.value,
            c.nature_of_service,
            c.polarization.value,
            c.service_area_id,
            c.co_polar_pattern_id,
            c.cross_polar_pattern_id,
        )
        grouped_buckets[key].append(c)

    itu_groups: list[ITUGroupData] = []
    grp_counter = 1

    for key, carrier_list in grouped_buckets.items():
        (beam_id, direction, stn_class, nat_srv, pol, srv_area, pat_co, pat_cross) = key

        # 1. Frequency Spans
        freq_segments = []
        for c in carrier_list:
            f_center = c.center_frequency_mhz
            bw = c.bandwidth_mhz
            f_min = f_center - (bw / 2.0)
            f_max = f_center + (bw / 2.0)
            freq_segments.append((f_min, f_max, f_center))

        # 2. Aggregate Power Characteristics
        total_pwr_watts = sum(10.0 ** (c.emission.peak_eirp_dbw / 10.0) for c in carrier_list)
        envelope_eirp_max = 10.0 * math.log10(max(1e-12, total_pwr_watts))

        max_psd = max(c.emission.max_psd_dbw_hz for c in carrier_list)
        min_psd = min(
            (c.emission.min_psd_dbw_hz if c.emission.min_psd_dbw_hz is not None else max_psd - 20.0)
            for c in carrier_list
        )

        emission_designators = sorted(list(set(c.emission.designator for c in carrier_list)))

        itu_groups.append(
            ITUGroupData(
                grp_id=grp_counter,
                beam_id=beam_id,
                direction=direction,
                station_class=stn_class,
                nature_of_service=nat_srv,
                polarization=pol,
                service_area_id=srv_area,
                pattern_co_id=pat_co,
                pattern_cross_id=pat_cross,
                eirp_max_dbw=round(envelope_eirp_max, 2),
                psd_max_dbw_hz=round(max_psd, 2),
                psd_min_dbw_hz=round(min_psd, 2),
                carrier_frequencies=sorted(freq_segments, key=lambda x: x[0]),
                emissions=emission_designators,
            )
        )
        grp_counter += 1

    return itu_groups
