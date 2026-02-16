"""Serialize pandas DataFrames and values for JSON API responses."""
import pandas as pd
import numpy as np
from datetime import date, datetime
from typing import Any


def serialize_dict(d: dict) -> dict:
    """Serialize a dict for JSON (e.g. database row)."""
    return {k: _serialize_value(v) for k, v in d.items()}


def _serialize_value(val: Any) -> Any:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, (np.integer, np.int64, np.int32)):
        return int(val)
    if isinstance(val, (np.floating, np.float64, np.float32)):
        return float(val)
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    if isinstance(val, (list, tuple)):
        return [_serialize_value(v) for v in val]
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    return val


def dataframe_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to list of dicts with JSON-serializable values."""
    if df is None or df.empty:
        return []
    records = df.replace({np.nan: None}).to_dict(orient="records")
    return [{k: _serialize_value(v) for k, v in r.items()} for r in records]
