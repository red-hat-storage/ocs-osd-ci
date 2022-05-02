import json
import logging
import subprocess
from logging.config import dictConfig
from typing import Dict, List

import httpx
from environs import Env

env = Env()
env.read_env()
logger = logging.getLogger()


def create_json_file(file_path: str, body: Dict) -> str:
    with open(file_path, encoding="utf-8", mode="w") as file:
        file.write(json.dumps(body, indent=2))
    return file_path


def download_file(url: str, file_path: str) -> None:
    logger.info("Downloading: %s to %s", url, file_path)
    with open(file_path, "wb") as file:
        try:
            response = httpx.get(url, follow_redirects=True)
        except httpx.RequestError as error:
            logger.exception("Error requesting %s", repr(error.request.url))
        file.write(response.content)


def run_cmd(cmd: List[str]) -> subprocess.CompletedProcess:
    try:
        logger.info(cmd)
        completed_process: subprocess.CompletedProcess = subprocess.run(
            cmd, check=True, text=True, capture_output=True, timeout=10
        )
    except subprocess.CalledProcessError as error:
        logger.exception("Command failed:\n%s", error.stderr)
        raise
    if completed_process.stdout:
        logger.info(completed_process.stdout)
    return completed_process


def setup_logging():
    dictConfig(
        {
            "version": 1,
            "formatters": {
                "BASE_FORMAT": {
                    "format": " %(asctime)s [%(levelname)s] %(message)s",
                },
                "FILE_FORMAT": {
                    "format": " %(asctime)s [%(levelname)s] %(filename)s %(message)s",
                },
            },
            "handlers": {
                "cli": {
                    "class": "logging.StreamHandler",
                    "level": "INFO",
                    "formatter": "BASE_FORMAT",
                },
                "file": {
                    "class": "logging.FileHandler",
                    "level": "DEBUG",
                    "formatter": "FILE_FORMAT",
                    "filename": env("LOG_FILE", default="test-output.log"),
                    "mode": "w+",
                },
            },
            "root": {"level": "INFO", "handlers": ["cli", "file"]},
        }
    )
