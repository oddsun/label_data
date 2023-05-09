import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi import File, UploadFile
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from more_itertools import batched
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from starlette.responses import StreamingResponse

from label_data.models import Headline

# from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
BASE_DIR = Path(__file__).parent
# don't need since using `alembic upgrade head`
# Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
async def read_headline(request: Request, db: Session = Depends(get_db)):
    headline = db.scalars(
        select(Headline).where(Headline.sentiment == None).limit(1)
    ).first()

    if headline:
        return templates.TemplateResponse("index.html",
                                          {"request": request, "headline": headline})
    else:
        first_ten_records = db.scalars(select(Headline).limit(10)).all()
        return templates.TemplateResponse("finished.html",
                                          {"request": request,
                                           "headlines": first_ten_records})


@app.post("/classify")
async def rate_headline(sentiment: str = Form(...), headline_id: int = Form(...),
                        category: str = Form(...),
                        db: Session = Depends(get_db)):
    headline = db.scalars(
        select(Headline).where(Headline.id == headline_id).limit(1)
    ).first()
    headline.sentiment = sentiment
    headline.category = category
    db.commit()
    return RedirectResponse("/", 303)


@app.post("/undo/{headline_id}")
async def undo_headline(headline_id: int, db: Session = Depends(get_db)):
    headline = db.scalars(
        select(Headline).where(Headline.id == headline_id).limit(1)
    ).first()
    headline.sentiment = None
    db.commit()
    return RedirectResponse("/", 303)


def csv_reader(content: str):
    """ basic csv reader

    This does not handle escaped commas within quotes. The user needs to ensure the
    commas are correctly escaped as `&comma;` (html entity).
    """
    for row in content.splitlines()[1:]:
        items = row.split(',')
        if len(items) <= 1:
            continue
        index, identifier, headline, name = items
        yield identifier, headline, name


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if file.filename.endswith('.csv'):
        content = await file.read()

        for chunk in batched(csv_reader(content.decode('utf-8')), n=1000):
            db.add_all([
                Headline(identifier=identifier, headline=headline, name=name)
                for identifier, headline, name in chunk
            ])
            db.flush()
        db.commit()
    else:
        raise HTTPException(status_code=400,
                            detail="Invalid file format. Please upload a CSV file.")

    return RedirectResponse("/", 303)


@app.get("/upload")
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


def generate_csv_content(db: Session):
    # Write the header row
    header = ["id", "identifier", "headline", "name", "sentiment", "category"]
    yield ','.join(header) + '\n'

    # Write the data rows
    stmt = select(Headline).execution_options(yield_per=10)
    for headline in db.scalars(stmt):
        row = [str(headline.id), headline.identifier, headline.headline, headline.name,
               headline.sentiment, headline.category]
        yield ','.join(row) + '\n'


@app.get("/download_csv", response_class=FileResponse)
async def download_csv(db: Session = Depends(get_db)):
    return StreamingResponse(generate_csv_content(db), media_type="text/csv", headers={
        "Content-Disposition": "attachment;filename=headlines.csv"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
