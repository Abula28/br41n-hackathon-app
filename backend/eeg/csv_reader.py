"""
CSV-backed EEG data source.

Reads backend/assets/data/raw-data.csv when available and maps flexible column
names into the existing EEGReading shape. Invalid or exhausted CSV data returns
None so callers can fall back to the simulator without crashing.
"""

from __future__ import annotations

import csv
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from eeg.simulator import EEGContinuousSimulator, EEGReading

logger = logging.getLogger(__name__)

EEG_CSV_PATH = Path(__file__).resolve().parents[1] / "assets" / "data" / "raw-data.csv"

BAND_KEYS = ("delta", "theta", "alpha", "beta", "gamma")
FEATURE_KEYS = (*BAND_KEYS, "heart_rate", "movement")

_ALIASES: dict[str, tuple[str, ...]] = {
    "delta": ("delta", "delta_power", "deltapower", "slow_wave", "slowwave"),
    "theta": ("theta", "theta_power", "thetapower"),
    "alpha": ("alpha", "alpha_power", "alphapower"),
    "beta": ("beta", "beta_power", "betapower"),
    "gamma": ("gamma", "gamma_power", "gammapower"),
    "heart_rate": (
        "heart_rate",
        "heartrate",
        "heart",
        "hr",
        "bpm",
        "pulse",
        "pulse_rate",
    ),
    "movement": (
        "movement",
        "motion",
        "accelerometer",
        "accel",
        "activity",
        "body_movement",
    ),
}

_DEFAULTS = {
    "delta": 0.30,
    "theta": 0.35,
    "alpha": 0.20,
    "beta": 0.12,
    "gamma": 0.06,
    "heart_rate": 62,
    "movement": 0.05,
}


@dataclass(frozen=True)
class EEGSample:
    source: str
    reading: EEGReading


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.strip().lower())


def _parse_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        text = text.replace(",", "")
        try:
            number = float(text)
        except ValueError:
            return None
    if not math.isfinite(number):
        return None
    return number


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _normalize_unit(value: float) -> float:
    value = abs(value)
    if value <= 1.0:
        return _clamp(value)
    if value <= 100.0:
        return _clamp(value / 100.0)
    return _clamp(value / 1_000_000.0)


def _normalize_bands(raw_bands: dict[str, float]) -> dict[str, float]:
    if not raw_bands:
        return {key: float(_DEFAULTS[key]) for key in BAND_KEYS}

    values = [abs(value) for value in raw_bands.values()]
    max_value = max(values) if values else 0.0

    normalized: dict[str, float] = {}
    for key in BAND_KEYS:
        if key not in raw_bands:
            normalized[key] = float(_DEFAULTS[key])
            continue
        value = abs(raw_bands[key])
        if max_value <= 1.0:
            normalized[key] = _clamp(value)
        elif max_value <= 100.0 and all(value <= 100.0 for value in values):
            normalized[key] = _clamp(value / 100.0)
        else:
            normalized[key] = _clamp(value / max_value) if max_value else float(_DEFAULTS[key])
    return normalized


def _normalize_numeric_columns(row: dict[str, str]) -> dict[str, float]:
    numeric: dict[str, float] = {}
    for column, value in row.items():
        number = _parse_float(value)
        if number is not None:
            numeric[column] = number
    return numeric


class EEGCsvReader:
    """Session-scoped reader for one CSV file."""

    def __init__(self, path: Path = EEG_CSV_PATH) -> None:
        self.path = path
        self._rows: list[dict[str, str]] = []
        self._fieldnames: list[str] = []
        self._position = 0
        self._loaded = False
        self._load_error: str | None = None

    @property
    def position(self) -> int:
        return self._position

    @property
    def total_rows(self) -> int:
        self._ensure_loaded()
        return len(self._rows)

    @property
    def available_columns(self) -> list[str]:
        self._ensure_loaded()
        return list(self._fieldnames)

    @property
    def last_error(self) -> str | None:
        return self._load_error

    def reset(self) -> None:
        self._position = 0

    def next(self) -> EEGReading | None:
        self._ensure_loaded()
        if not self._rows:
            return None

        while self._position < len(self._rows):
            row = self._rows[self._position]
            self._position += 1
            try:
                reading = self._row_to_reading(row)
            except Exception as exc:
                logger.warning("Skipping invalid EEG CSV row %d: %s", self._position, exc)
                continue
            if reading is not None:
                return reading

        return None

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        if not self.path.exists():
            self._load_error = f"CSV not found: {self.path}"
            logger.info(self._load_error)
            return

        try:
            with self.path.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                self._fieldnames = list(reader.fieldnames or [])
                self._rows = [row for row in reader if row]
        except Exception as exc:
            self._load_error = f"Could not read EEG CSV: {exc}"
            logger.warning(self._load_error)
            self._rows = []
            self._fieldnames = []
            return

        if not self._fieldnames or not self._rows:
            self._load_error = "EEG CSV is empty or has no header row."
            logger.info(self._load_error)

    def _row_to_reading(self, row: dict[str, str]) -> EEGReading | None:
        numeric = _normalize_numeric_columns(row)
        if not numeric:
            return None

        by_normalized_name = {_normalize_name(name): name for name in row.keys()}
        values: dict[str, float] = {}

        mapped_columns: set[str] = set()
        for feature in FEATURE_KEYS:
            column = self._find_column(feature, by_normalized_name)
            if column is None:
                continue
            number = _parse_float(row.get(column))
            if number is not None:
                values[feature] = number
                mapped_columns.add(column)

        fallback_columns = [
            column for column in numeric.keys() if column not in mapped_columns
        ]
        bands = {key: values[key] for key in BAND_KEYS if key in values}

        if len(bands) < len(BAND_KEYS):
            fallback_values = self._scaled_fallback_values(
                numeric[column] for column in fallback_columns
            )
            for key, value in zip((key for key in BAND_KEYS if key not in bands), fallback_values):
                bands[key] = value

        normalized_bands = _normalize_bands(bands)
        heart_rate = self._heart_rate(values.get("heart_rate"), normalized_bands)
        movement = self._movement(values.get("movement"), numeric.values())

        return EEGReading(
            delta=normalized_bands["delta"],
            theta=normalized_bands["theta"],
            alpha=normalized_bands["alpha"],
            beta=normalized_bands["beta"],
            gamma=normalized_bands["gamma"],
            heart_rate=heart_rate,
            movement=movement,
        )

    def _find_column(
        self,
        feature: str,
        by_normalized_name: dict[str, str],
    ) -> str | None:
        aliases = _ALIASES[feature]
        for alias in aliases:
            normalized_alias = _normalize_name(alias)
            if normalized_alias in by_normalized_name:
                return by_normalized_name[normalized_alias]

        tokens = tuple(_normalize_name(alias) for alias in aliases)
        for normalized_name, original_name in by_normalized_name.items():
            if any(token and token in normalized_name for token in tokens):
                return original_name
        return None

    def _scaled_fallback_values(self, values: Iterable[float]) -> list[float]:
        numbers = [abs(value) for value in values if math.isfinite(value)]
        if not numbers:
            return []
        max_value = max(numbers)
        if max_value <= 0:
            return []
        return [_normalize_unit(value) if max_value <= 100.0 else _clamp(value / max_value) for value in numbers]

    def _heart_rate(self, value: float | None, bands: dict[str, float]) -> int:
        if value is not None and 30 <= value <= 220:
            return int(round(value))
        arousal = bands["beta"] + bands["gamma"]
        return int(round(54 + _clamp(arousal) * 28))

    def _movement(self, value: float | None, numeric_values: Iterable[float]) -> float:
        if value is not None:
            return _normalize_unit(value)
        values = [abs(number) for number in numeric_values]
        if not values:
            return float(_DEFAULTS["movement"])
        return _clamp((max(values) - min(values)) / max(max(values), 1.0))


class EEGDataSource:
    """CSV-first EEG source with permanent simulator fallback."""

    def __init__(
        self,
        csv_reader: EEGCsvReader | None = None,
        simulator: EEGContinuousSimulator | None = None,
    ) -> None:
        self.csv_reader = csv_reader or EEGCsvReader()
        self.simulator = simulator or EEGContinuousSimulator()

    def reset_csv(self) -> None:
        self.csv_reader.reset()

    def next(self) -> EEGSample:
        csv_reading = self.csv_reader.next()
        if csv_reading is not None:
            return EEGSample(source="csv", reading=csv_reading)
        return EEGSample(source="simulated", reading=self.simulator.next())
