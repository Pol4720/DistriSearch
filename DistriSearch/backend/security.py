from fastapi import Request, HTTPException
import os

def require_api_key(request: Request):
    """Checks X-API-KEY header if ADMIN_API_KEY env var is set.

    In dev, if ADMIN_API_KEY is empty or unset, allow requests.
    """
    required = os.getenv("ADMIN_API_KEY")
    if not required:
        return
    provided = request.headers.get("X-API-KEY")
    if provided != required:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
