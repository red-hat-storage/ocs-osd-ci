import json
import logging
import subprocess
import time
from collections.abc import Callable
from functools import wraps
from logging.config import dictConfig
from math import ceil
from typing import Any

import httpx
from environs import Env

env = Env()
env.read_env()
logger = logging.getLogger()


def download_file(url: str, file_path: str) -> None:
    logger.info("Downloading: %s to %s", url, file_path)
    with open(file_path, "wb") as file:
        try:
            response = httpx.get(url, follow_redirects=True)
        except httpx.RequestError as error:
            logger.exception("Error requesting %s", repr(error.request.url))
        file.write(response.content)


def get_file_content(file_path: str) -> str:
    with open(file_path, encoding="utf-8", mode="r") as file:
        return file.read()


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    logger.info(cmd)
    try:
        completed_process = subprocess.run(
            cmd, check=True, text=True, capture_output=True, timeout=10
        )
    except subprocess.CalledProcessError as error:
        logger.debug("Command failed:\n%s", error.stderr, exc_info=True)
        raise
    if completed_process.stdout:
        logger.debug(completed_process.stdout)
    return completed_process


def save_to_file(file_path: str, body: str) -> str:
    with open(file_path, encoding="utf-8", mode="w") as file:
        file.write(body)
    return file_path


def save_to_json_file(file_path: str, body: dict[str, Any]) -> str:
    return save_to_file(file_path, json.dumps(body, indent=2))


def setup_logging() -> None:
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
            "root": {"level": "DEBUG", "handlers": ["cli", "file"]},
        }
    )


def wait_for(timeout: int = 5400, check_period: int = 300) -> Callable[[Any], Any]:
    if timeout <= 0 or check_period <= 0:
        raise ValueError("Timeout and check period must be positive integers.")

    def inner(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> None:
            for _ in range(ceil(timeout / check_period)):
                check_start = time.time()
                if func(*args, **kwargs):
                    return
                check_duration = time.time() - check_start
                if check_period > check_duration:
                    time.sleep(check_period - check_duration)
            raise RuntimeError("Timeout while waiting for condition to be met.")

        return wrapper

    return inner
