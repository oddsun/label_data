from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Headline(Base):
    __tablename__ = "headlines"

    id = Column(Integer, primary_key=True)
    identifier = Column(String, unique=True)
    headline = Column(String)
    name = Column(String)
    sentiment = Column(String, index=True)
    category = Column(String, index=True)
