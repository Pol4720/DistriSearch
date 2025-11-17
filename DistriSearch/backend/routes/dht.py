from fastapi import APIRouter, HTTPException
from typing import Optional
from services import dht_service

router = APIRouter(prefix="/dht", tags=["dht"])


@router.post("/start")
def start_dht():
    try:
        dht_service.service.start()
        return {"status": "started", "mode": dht_service.service.mode}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/join")
def join_dht(seed_ip: str, seed_port: Optional[int] = None):
    try:
        res = dht_service.service.join(seed_ip, seed_port)
        return {"result": str(res)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
def upload_file(filename: str, data: str):
    try:
        res = dht_service.service.upload(filename, data)
        return {"result": str(res)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/download")
def download_file(filename: str):
    try:
        res = dht_service.service.download(filename)
        return {"result": str(res)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/finger")
def finger_table():
    try:
        res = dht_service.service.finger_table()
        return {"finger": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sucpred")
def suc_pred():
    try:
        res = dht_service.service.suc_pred()
        return {"sucpred": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
