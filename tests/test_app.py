import shutil

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from label_data.main import Headline, app, get_db
from label_data.models import Base

# Setup a test database
DB_NAME = "test.db"
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False)


@pytest.fixture(scope="module")
def test_db(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("data") / DB_NAME
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal.configure(bind=engine)

    # Insert a test headline
    db = TestingSessionLocal()
    db.add(
        Headline(id=1, headline="Test headline", name="Test name", identifier="Test id")
    )
    db.commit()
    db.close()

    yield db_url

    # Cleanup: remove the test database file
    engine.dispose()
    if db_path.exists():
        db_path.unlink()
    shutil.rmtree(db_path.parent)


@pytest.fixture(scope="module")
def client(test_db):
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c


def test_homepage(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Test headline" in response.text


def test_classify_headline(client):
    response = client.post(
        "/classify",
        data={"headline_id": 1, "sentiment": "neutral", "category": "other"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    # Check that the sentiment and category were updated correctly
    db = TestingSessionLocal()
    headline = db.scalars(select(Headline).where(Headline.id == 1).limit(1)).first()
    assert headline.sentiment == "neutral"
    assert headline.category == "other"
    db.close()

    response = client.get("/")
    assert response.status_code == 200
    assert "All headlines have been classified." in response.text


def test_undo_endpoint(client):
    # First, classify a headline
    response = client.post(
        "/classify",
        data={"headline_id": 1, "sentiment": "positive", "category": "ads"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    # Then, undo the classification
    response = client.post("/undo/1", follow_redirects=False)
    assert response.status_code == 303

    # Verify that the sentiment and category for the headline are back to None
    db = TestingSessionLocal()
    headline = db.scalars(select(Headline).where(Headline.id == 1).limit(1)).first()
    assert headline.sentiment is None
    assert headline.category is None
    db.close()


def test_csv_upload(client):
    csv_data = (
        "id,identifier,headline,name\n" "3,Another id,Another headline,Another name\n"
    )
    response = client.post(
        "/upload", files={"file": ("test.csv", csv_data, "text/csv")}
    )
    assert response.status_code == 200

    # Check that the new headline was inserted into the database
    db = TestingSessionLocal()
    headline = db.scalars(select(Headline).where(Headline.id == 2).limit(1)).first()
    assert headline.headline == "Another headline"
    assert headline.name == "Another name"
    assert headline.identifier == "Another id"
    db.close()


def test_finished(client):
    client.post(
        "/classify",
        data={"headline_id": 1, "sentiment": "positive", "category": "ads"},
    )
    response = client.post(
        "/classify",
        data={"headline_id": 2, "sentiment": "negative", "category": "lawsuit"},
    )
    assert response.status_code == 200
    assert "All headlines have been classified." in response.text
    assert "Test headline" in response.text
    assert "Another headline" in response.text


def test_download_csv(client):
    response = client.get("/download_csv")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    # Check that the downloaded CSV contains the correct data
    expected_text = (
        "id,identifier,headline,name,sentiment,category\n"
        "1,Test id,Test headline,Test name,positive,ads\n"
        "2,Another id,Another headline,Another name,negative,lawsuit\n"
    )
    assert response.text == expected_text
