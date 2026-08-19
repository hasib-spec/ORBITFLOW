"""
OrbitFlow Rules-as-Data Loader
==============================

Loads YAML rule definitions from disk and provides typed accessors.
This is Module 1 of the v3.0 architecture — every other engine queries
rules through this loader.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from backend.app.core.config import RULES_DIR, get_logger

log = get_logger(__name__)


class RulesLoader:
    """Loads and caches YAML rule files from the ``rules/`` directory."""

    def __init__(self, rules_dir: Path | None = None) -> None:
        self._rules_dir = rules_dir or RULES_DIR
        self._cache: dict[str, Any] = {}
        log.info("RulesLoader initialized — rules_dir=%s", self._rules_dir)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_file(self, filename: str) -> dict[str, Any]:
        """Load a single YAML file, using cache if available."""
        if filename in self._cache:
            return self._cache[filename]

        path = self._rules_dir / filename
        if not path.exists():
            log.error("Rules file not found: %s", path)
            raise FileNotFoundError(f"Rules file not found: {path}")

        with open(path, "r", encoding="utf-8") as fh:
            data: dict[str, Any] = yaml.safe_load(fh) or {}

        self._cache[filename] = data
        log.info("Loaded rules file: %s (%d top-level keys)", filename, len(data))
        return data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_part_100_rules(self) -> dict[str, Any]:
        """Return the full Part 100 adopted rules dictionary."""
        return self._load_file("part_100_adopted.yaml")

    def get_targeted_reviews(self) -> dict[str, Any]:
        """Return targeted review category definitions."""
        return self._load_file("targeted_reviews.yaml")

    def get_certifications(self, system_type: str) -> list[dict[str, Any]]:
        """
        Return the certification list for a given system type.

        Parameters
        ----------
        system_type : str
            One of ``"ngso"``, ``"gso"``, ``"vtss"``.

        Returns
        -------
        list[dict]
            List of certification rule dictionaries.
        """
        rules = self.get_part_100_rules()
        key_map: dict[str, str] = {
            "ngso": "schedule_o_ngso",
            "gso": "schedule_o_gso",
            "vtss": "schedule_o_vtss",
        }
        key = key_map.get(system_type.lower(), "")
        if not key or key not in rules:
            log.warning("No certifications found for system_type=%s", system_type)
            return []
        return rules[key]  # type: ignore[return-value]

    def get_deltas(self) -> list[dict[str, str]]:
        """Return the Part 25 → Part 100 delta matrix rows."""
        rules = self.get_part_100_rules()
        return rules.get("deltas", [])  # type: ignore[return-value]

    def get_bond_rules(self) -> dict[str, Any]:
        """Return bond configuration."""
        rules = self.get_part_100_rules()
        return rules.get("bonds", {})  # type: ignore[return-value]

    def get_milestone_rules(self) -> dict[str, Any]:
        """Return milestone schedule configuration."""
        rules = self.get_part_100_rules()
        return rules.get("milestones", {})  # type: ignore[return-value]

    def invalidate_cache(self) -> None:
        """Clear the in-memory rules cache (useful for hot-reload)."""
        self._cache.clear()
        log.info("Rules cache invalidated")


# ---------------------------------------------------------------------------
# Module-level singleton for convenience
# ---------------------------------------------------------------------------
_default_loader: RulesLoader | None = None


def get_rules_loader() -> RulesLoader:
    """Return (or create) the default singleton RulesLoader."""
    global _default_loader  # noqa: PLW0603
    if _default_loader is None:
        _default_loader = RulesLoader()
    return _default_loader
