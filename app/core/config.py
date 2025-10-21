import os
import toml
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

BASE_PATH = "/api/v1"
HOST: str = "0.0.0.0"
PORT: int = int(os.getenv("PORT", "8090"))
COMMIT_SHA: str = os.getenv("COMMIT_SHA", "unknown")

# TODO: get it from the Secret Manager
API_KEY = os.getenv("API_KEY", "ss")
PROJECT_NAME: str = "ORCA BOT"


def get_version_from_pyproject_toml(file_path: str) -> Optional[str]:
    with open(file_path, "r") as f:
        pyproject_toml = toml.load(f)
        # Check if there's a version specified in pyproject.toml
        if (
            "tool" in pyproject_toml
            and "poetry" in pyproject_toml["tool"]
            and "version" in pyproject_toml["tool"]["poetry"]
        ):
            return pyproject_toml["tool"]["poetry"]["version"]
        else:
            return None


API_KEY_NAME = "api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)


async def verify_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="api-key header invalid")
    return api_key


VERSION = get_version_from_pyproject_toml("../pyproject.toml")
