from __future__ import annotations

import logging
from typing import Any, Protocol

from google.cloud import bigquery

LOGGER = logging.getLogger(__name__)


class AnalyticsRepository(Protocol):
    def record(self, table: str, row: dict[str, Any]) -> None: ...


class NoopAnalyticsRepository:
    def record(self, table: str, row: dict[str, Any]) -> None:
        return None


class BigQueryAnalyticsRepository:
    """Operational index only; Firestore and GCS remain the source of truth."""

    def __init__(self, client: bigquery.Client, dataset: str = "income_tax_ops"):
        self._client = client
        self._dataset = dataset

    def record(self, table: str, row: dict[str, Any]) -> None:
        table_id = f"{self._client.project}.{self._dataset}.{table}"
        try:
            errors = self._client.insert_rows_json(table_id, [row])
            if errors:
                LOGGER.warning("BigQuery insert failed for %s: %s", table, errors)
        except Exception:
            LOGGER.exception("BigQuery insert failed for %s", table)
