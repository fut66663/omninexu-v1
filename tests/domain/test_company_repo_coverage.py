"""Coverage supplement for CompanyRepository.update_gics."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from omninexu.domain.company import Company, IndustryClassification
from omninexu.infrastructure.db import Base
from omninexu.infrastructure.gics_mapping import GicsClassification
from omninexu.infrastructure.models import CompanyModel
from omninexu.infrastructure.repositories import CompanyRepository


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


class TestCompanyRepoUpdateGics:
    def test_update_gics_writes_all_fields(self, db_session):
        """update_gics persists GICS fields to the company row."""
        repo = CompanyRepository(db_session)
        repo.create_or_update(Company(
            ticker="AAPL", cik="0000320193", name="Apple Inc.",
            industry=IndustryClassification(),
        ))

        gics = GicsClassification(
            sic="3571",
            gics_sector="Technology",
            gics_industry_group="Hardware",
            gics_industry="Computers",
            gics_sub_industry="Consumer Electronics",
        )
        repo.update_gics("AAPL", gics)

        model = db_session.query(CompanyModel).filter_by(ticker="AAPL").first()
        assert model.gics_sector == "Technology"
        assert model.gics_industry_group == "Hardware"
        assert model.gics_industry == "Computers"
        assert model.gics_sub_industry == "Consumer Electronics"

    def test_update_gics_unknown_ticker_noop(self, db_session):
        """update_gics on a missing ticker logs warning and returns."""
        repo = CompanyRepository(db_session)
        gics = GicsClassification(
            sic="0000", gics_sector="X", gics_industry_group="Y",
            gics_industry="Z", gics_sub_industry="W",
        )
        # Should not raise
        repo.update_gics("UNKNOWN", gics)
        assert db_session.query(CompanyModel).count() == 0
