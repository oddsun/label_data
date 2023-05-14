[![Coverage badge](https://raw.githubusercontent.com/oddsun/label_data/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/oddsun/label_data/blob/python-coverage-comment-action-data/htmlcov/index.html)
[![GitHub license](https://img.shields.io/github/license/oddsun/label_data)](https://github.com/oddsun/timer-electron/blob/master/LICENSE)
[![build](https://github.com/oddsun/label_data/actions/workflows/python-ci.yml/badge.svg)](https://github.com/oddsun/label_data/actions/workflows/python-ci.yml)
![GitHub top language](https://img.shields.io/github/languages/top/oddsun/label_data)

## Overview

A quick, simple fastapi app to help manually label data.


## To run

In project root:

```bash
poetry install
poetry shell
alembic upgrade head
uvicorn label_data.main:app
```


## Setup alembic (only for initial dev)

### 1. To initialize alembic

```bash
alembic init alembic
```

### 2. Update `alembic/env.py` to use database url from env, and import model

add

```python
from dotenv import load_dotenv
import os

load_dotenv()

# overwriting url
config.set_main_option('sqlalchemy.url', os.environ.get("DATABASE_URL"))

from label_data.models import Base

target_metadata = Base.metadata
```

### 3. Autogenerate migration

```bash
alembic revision --autogenerate -m "message"
```
