from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from routes import search, register, download
from routes import central  # nuevo router para modo centralizado

app = FastAPI(
    title="DistriSearch API",
    description="API centralizada para búsqueda distribuida de archivos",
    version="0.1.0"
)

# Configurar CORS para permitir peticiones desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, limitar a dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(search.router)
app.include_router(register.router)
app.include_router(download.router)
app.include_router(central.router)

@app.get("/")
async def root():
    return {"message": "Bienvenido a DistriSearch API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
