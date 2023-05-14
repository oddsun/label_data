import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from more_itertools import batched
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import StreamingResponse

from label_data.models import Headline

# from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///headlines.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
BASE_DIR = Path(__file__).parent
# don't need since using `alembic upgrade head`
# Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# Dependency
def get_db():
    """get db session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
async def read_headline(request: Request, db: Session = Depends(get_db)):
    """show page for classification if any else show finished page"""
    headline = db.scalars(
        select(Headline).where(Headline.sentiment == None).limit(1)  # noqa
    ).first()

    if headline:
        return templates.TemplateResponse(
            "index.html", {"request": request, "headline": headline}
        )
    else:
        first_ten_records = db.scalars(select(Headline).limit(10)).all()
        return templates.TemplateResponse(
            "finished.html", {"request": request, "headlines": first_ten_records}
        )


@app.post("/classify")
async def rate_headline(
    sentiment: str = Form(...),
    headline_id: int = Form(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
):
    """record headline classification"""
    headline = await select_headline_by_id(db, headline_id)
    headline.sentiment = sentiment
    headline.category = category
    db.commit()
    return RedirectResponse("/", 303)


async def select_headline_by_id(db: Session, headline_id: int):
    """select headline from db by id"""
    headline = db.scalars(
        select(Headline).where(Headline.id == headline_id).limit(1)
    ).first()
    if not headline:
        raise ValueError(f"headline with {headline_id=} not found")
    return headline


@app.post("/undo/{headline_id}")
async def undo_classification(headline_id: int, db: Session = Depends(get_db)):
    """undo classification"""
    headline = await select_headline_by_id(db, headline_id)
    headline.sentiment = None
    headline.category = None
    db.commit()
    return RedirectResponse("/", 303)


def csv_reader(content: str):
    """basic csv reader

    This does not handle escaped commas within quotes. The user needs to ensure the
    commas are correctly escaped as `&comma;` (html entity).
    """
    for row in content.splitlines()[1:]:
        items = row.split(",")
        if len(items) <= 1:
            continue
        index, identifier, headline, name = items
        yield identifier, headline, name


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """upload csv file into db"""
    if file.filename and file.filename.endswith(".csv"):
        content = await file.read()

        for chunk in batched(csv_reader(content.decode("utf-8")), n=1000):
            db.add_all(
                [
                    Headline(identifier=identifier, headline=headline, name=name)
                    for identifier, headline, name in chunk
                ]
            )
            db.flush()
        db.commit()
    else:
        raise HTTPException(
            status_code=400, detail="Invalid file format. Please upload a CSV file."
        )

    return RedirectResponse("/", 303)


@app.get("/upload")
async def upload_page(request: Request):
    """upload page"""
    return templates.TemplateResponse("upload.html", {"request": request})


def generate_csv_content(db: Session):
    """streamer for downloading csv file"""
    # Write the header row
    header = ["id", "identifier", "headline", "name", "sentiment", "category"]
    yield ",".join(header) + "\n"

    # Write the data rows
    stmt = select(Headline).execution_options(yield_per=10)
    for headline in db.scalars(stmt):
        row = [
            str(headline.id),
            headline.identifier,
            headline.headline,
            headline.name,
            headline.sentiment,
            headline.category,
        ]
        yield ",".join(map(str, row)) + "\n"


@app.get("/download_csv", response_class=FileResponse)
async def download_csv(db: Session = Depends(get_db)):
    """download csv endpoint"""
    return StreamingResponse(
        generate_csv_content(db),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment;filename=headlines.csv"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
