from pathlib import Path

import pytest


@pytest.fixture
def game_project_path() -> Path:
    return Path('game.project')


@pytest.fixture
def pyproject_toml_path() -> Path:
    return Path('pyproject.toml')
