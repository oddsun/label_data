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
