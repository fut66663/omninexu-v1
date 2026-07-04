"""SQLAlchemy models for OmniNexu."""

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from omninexu.infrastructure.db import Base


def _utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(UTC)


class CompanyModel(Base):
    """Company metadata."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    cik: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Industry classification
    sic_code: Mapped[str | None] = mapped_column(String(4))
    naics_code: Mapped[str | None] = mapped_column(String(10))
    gics_sector: Mapped[str | None] = mapped_column(String(100))
    gics_industry_group: Mapped[str | None] = mapped_column(String(100))
    gics_industry: Mapped[str | None] = mapped_column(String(100))
    gics_sub_industry: Mapped[str | None] = mapped_column(String(100))

    is_snp500: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)


class FinancialFactModel(Base):
    """Financial facts extracted from SEC filings."""

    __tablename__ = "financial_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_period: Mapped[str] = mapped_column(String(10), nullable=False)  # FY, Q1, Q2, Q3
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    concept: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(255))
    value: Mapped[float | None] = mapped_column(Numeric(20, 4))
    unit: Mapped[str] = mapped_column(String(20), default="USD")
    source_filing: Mapped[str | None] = mapped_column(String(255))
    statement_type: Mapped[str | None] = mapped_column(String(50))  # income, balance, cashflow
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="simfin")  # simfin | edgar
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_period",
            "concept",
            name="uq_financial_fact",
        ),
    )


class InstitutionalHoldingModel(Base):
    """13F institutional holdings."""

    __tablename__ = "institutional_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    reporting_manager: Mapped[str] = mapped_column(String(255), nullable=False)
    cusip: Mapped[str | None] = mapped_column(String(9))
    shares: Mapped[float | None] = mapped_column(Numeric(20, 0))
    value: Mapped[float | None] = mapped_column(Numeric(20, 2))
    report_date: Mapped[date | None] = mapped_column(Date)
    source_filing: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class InsiderTransactionModel(Base):
    """Form 4 insider transactions."""

    __tablename__ = "insider_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    insider_name: Mapped[str | None] = mapped_column(String(255))
    insider_title: Mapped[str | None] = mapped_column(String(255))
    transaction_type: Mapped[str | None] = mapped_column(String(10))  # P or S
    shares: Mapped[float | None] = mapped_column(Numeric(20, 0))
    price: Mapped[float | None] = mapped_column(Numeric(20, 4))
    transaction_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
