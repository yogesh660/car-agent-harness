import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from car_agent.data.seed import seed_database
from car_agent.db import connect_readonly


@pytest.fixture(scope="session")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("data") / "listings.db"
    seed_database(path)  # default rows + seed, same data as `make seed`
    return path


@pytest.fixture
def conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    c = connect_readonly(db_path)
    yield c
    c.close()
