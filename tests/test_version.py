import os
from configparser import ConfigParser, ParsingError
from pathlib import Path


def _path_to_config(path: Path) -> ConfigParser:
    config = ConfigParser(allow_no_value=True)

    try:
        if os.fspath(path) not in config.read(path):
            raise IOError(f"Config is not valid at: {path.absolute()}")
    except ParsingError as e:
        raise IOError(f"Config is not valid at: {path.absolute()}") from e

    return config


def test_from_path(game_project_path: Path, pyproject_toml_path: Path) -> None:
    config_parser = ConfigParser(allow_no_value=True)

    config_parser.read(game_project_path)
    game_project_version = config_parser['project']['version'].strip()

    config_parser.read(pyproject_toml_path)
    pyproject_toml_version = config_parser['tool.poetry']['version'][1:-1].strip()

    assert game_project_version == pyproject_toml_version
