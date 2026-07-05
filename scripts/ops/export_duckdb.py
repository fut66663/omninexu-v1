r"""Export PostgreSQL data to DuckDB for analytical queries.

DuckDB schema isolation (matching raw/ physical isolation):

    main.companies             ← S&P 500 company registry
    main.financial_facts       ← SimFin + SEC EDGAR financials (long form)
    main.financials_pivot      ← Analytical wide table (Revenue, NetIncome, ...)
    main.institutional         ← SEC 13F institutional holdings
    main.insider               ← SEC Form-4 insider transactions
    fred.series_data           ← FRED macro-economic series (future)
    fred.series_meta           ← FRED series metadata (future)

Each data source lives in its own DuckDB schema.  Cross-schema writes
are forbidden — the export function explicitly targets one schema per
data source.

Usage::

    uv run python scripts/ops/export_duckdb.py
"""

from __future__ import annotations

import duckdb
import pandas as pd
from sqlalchemy import text

from omninexu.config import data_paths
from omninexu.infrastructure.db import SessionLocal
from omninexu.observability import get_logger

logger = get_logger(__name__)

DUCKDB_PATH = str(data_paths.duckdb_path)

# ── schema definition ────────────────────────────────────────────
# Each entry: (schema, table_name, pg_query)
# Schema maps to data source — same naming as raw/ directories.
# NEVER write one data source's data into another's schema.

SCHEMA_TABLES: list[tuple[str, str, str]] = [
    # ── main schema: SimFin + SEC EDGAR ──
    ("main", "companies",
     "SELECT id, ticker, cik, name, sic_code, gics_sector, "
     "is_snp500, created_at, updated_at FROM companies"),
    ("main", "financial_facts",
     "SELECT id, company_id, ticker, fiscal_year, fiscal_period, "
     "report_date, concept, label, value, unit, source_filing, "
     "statement_type, source, created_at FROM financial_facts"),
    ("main", "institutional",
     "SELECT id, company_id, ticker, reporting_manager, shares, "
     "value, report_date, source_filing FROM institutional_holdings"),
    ("main", "insider",
     "SELECT id, company_id, ticker, insider_name, insider_title, "
     "transaction_type, shares, price, transaction_date, "
     "created_at FROM insider_transactions"),
]

# Schema ownership map: which raw/ directory each DuckDB schema belongs to.
# Used by verification to detect cross-contamination.
SCHEMA_OWNERS: dict[str, str] = {
    "main": "simfin+sec",   # combined financial data
    "fred": "fred",          # macro-economic
}

# ── pivot: financials wide table ─────────────────────────────────

FINANCIALS_PIVOT_SQL = """
CREATE OR REPLACE TABLE main.financials_pivot AS
PIVOT main.financial_facts
ON concept
USING FIRST(value)
GROUP BY ticker, fiscal_year, fiscal_period;
"""


# ── export ───────────────────────────────────────────────────────

def export_duckdb() -> dict[str, int]:
    """Export PG to DuckDB, respecting schema boundaries.

    Returns ``{"schema.table": row_count, ...}``.
    """
    db = SessionLocal()
    results: dict[str, int] = {}

    try:
        con = duckdb.connect(DUCKDB_PATH)
        logger.info(f"DuckDB connected: {DUCKDB_PATH}")

        # Ensure schemas exist
        for schema_name in {s for s, _, _ in SCHEMA_TABLES}:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")

        for schema_name, table_name, query in SCHEMA_TABLES:
            full_name = f"{schema_name}.{table_name}"
            try:
                df = pd.read_sql(text(query), db.bind)
                con.execute(f"DROP TABLE IF EXISTS {full_name}")
                con.execute(f"CREATE TABLE {full_name} AS SELECT * FROM df")
                results[full_name] = len(df)
                logger.info(f"  {full_name}: {len(df):,} rows")
            except Exception as exc:
                logger.error(f"  {full_name}: FAILED — {exc}")
                results[full_name] = -1

        # Build pivot table (analytical wide form)
        try:
            con.execute(FINANCIALS_PIVOT_SQL)
            pivot_rows = con.execute(
                "SELECT count(*) FROM main.financials_pivot"
            ).fetchone()[0]
            results["main.financials_pivot"] = pivot_rows
            logger.info(f"  main.financials_pivot: {pivot_rows:,} rows")
        except Exception as exc:
            logger.error(f"  main.financials_pivot: FAILED — {exc}")
            results["main.financials_pivot"] = -1

        con.close()
    finally:
        db.close()

    return results


def verify_isolation() -> list[str]:
    """Check DuckDB schema isolation. Returns list of violations."""
    violations: list[str] = []
    try:
        con = duckdb.connect(DUCKDB_PATH)
        schemas = con.execute(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('main', 'pg_catalog', 'information_schema')"
        ).fetchall()

        for (schema_name,) in schemas:
            tables = con.execute(
                f"SELECT table_name FROM information_schema.tables "
                f"WHERE table_schema='{schema_name}'"
            ).fetchall()

            owner = SCHEMA_OWNERS.get(schema_name, "unknown")
            for (table_name,) in tables:
                # Check for source column if it exists
                cols = con.execute(
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_schema='{schema_name}' AND table_name='{table_name}'"
                ).fetchall()
                col_names = {c[0].lower() for c in cols}

                if "source" in col_names:
                    sources = con.execute(
                        f"SELECT DISTINCT source FROM {schema_name}.{table_name}"
                    ).fetchall()
                    for (src,) in sources:
                        if (
                            src
                            and owner != "simfin+sec"
                            and src != owner
                            and src not in owner.split("+")
                        ):
                            violations.append(
                                f"{schema_name}.{table_name}: source={src} "
                                f"(owner={owner})"
                            )
        con.close()
    except Exception as exc:
        logger.warning(f"Isolation check failed: {exc}")

    return violations


# ── CLI ──────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Export PostgreSQL → DuckDB"
    )
    parser.add_argument("--verify", action="store_true",
                        help="Only run schema isolation check")
    args = parser.parse_args()

    if args.verify:
        violations = verify_isolation()
        if violations:
            logger.warning(f"Isolation violations: {len(violations)}")
            for v in violations:
                logger.warning(f"  {v}")
        else:
            logger.info("DuckDB schema isolation: PASS")
        return

    logger.info("Exporting PostgreSQL → DuckDB ...")
    results = export_duckdb()
    ok = sum(1 for v in results.values() if v >= 0)
    failed = sum(1 for v in results.values() if v == -1)
    total = sum(v for v in results.values() if v > 0)
    logger.info(f"DuckDB export done: {ok} ok, {failed} failed, {total:,} rows")

    # Auto-verify isolation after export
    violations = verify_isolation()
    if violations:
        logger.warning(f"Schema isolation violations: {len(violations)}")
        for v in violations:
            logger.warning(f"  VIOLATION: {v}")
    else:
        logger.info("Schema isolation check: PASS")


if __name__ == "__main__":
    main()
