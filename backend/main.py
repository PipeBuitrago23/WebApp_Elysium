import uuid
import bcrypt
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine, SessionLocal
from models.usuario import Usuario
from routes import auth as auth_router
from routes import pacientes


def _seed_admin():
    hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
    db = SessionLocal()
    try:
        if not db.query(Usuario).filter(Usuario.email == "admin@elysium.com").first():
            db.add(Usuario(
                id=str(uuid.uuid4()),
                email="admin@elysium.com",
                hashed_password=hashed,
                nombre="Administrador",
                es_admin=True,
            ))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    yield


app = FastAPI(title="Elysium Agenda API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(pacientes.router, prefix="/pacientes", tags=["pacientes"])


@app.get("/health")
def health():
    return {"status": "ok"}
