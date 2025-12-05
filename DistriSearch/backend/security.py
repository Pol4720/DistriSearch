from fastapi import Request, HTTPException
import os

def require_api_key(request: Request):
    """Checks X-API-KEY header if ADMIN_API_KEY env var is set."""
    required = os.getenv("ADMIN_API_KEY")
    
    # ✅ En desarrollo, si no hay API_KEY configurada, permitir
    if not required:
        return
    
    provided = request.headers.get("X-API-KEY")
    
    # ✅ AGREGAR LOG para debugging
    if provided != required:
        print(f"❌ API Key mismatch: expected '{required}', got '{provided}'")
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    
    print(f"✅ API Key válida")
