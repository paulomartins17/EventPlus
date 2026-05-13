from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from bson.errors import InvalidId
from typing import Optional
import os
from datetime import datetime, timezone

# ─── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="API de Eventos",
    description="Microsserviço de gestão de eventos de grife — Sistema EventPlus",
    version="1.0.0",
)

# ─── MongoDB ────────────────────────────────────────────────────────────────

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_USER = os.getenv("MONGO_USER", "grife_user")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "grife_pass")
MONGO_DB = os.getenv("MONGO_DB", "grife_db")

client = MongoClient(
    host=MONGO_HOST,
    port=MONGO_PORT,
    username=MONGO_USER,
    password=MONGO_PASSWORD,
    authSource="admin",
)
db = client[MONGO_DB]
eventos_col = db["eventos"]

# ─── Schemas ────────────────────────────────────────────────────────────────

class EventoCreate(BaseModel):
    nome: str = Field(..., min_length=2, example="Met Gala 2025")
    tema: str = Field(..., min_length=2, example="Tempo e Moda")
    data: str = Field(..., example="2025-05-05")
    local: str = Field(..., example="Metropolitan Museum, NY")
    dress_code: str = Field(..., example="Black Tie / Haute Couture")
    descricao: Optional[str] = Field(None, example="A maior noite da moda mundial.")

class EventoUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=2)
    tema: Optional[str] = Field(None, min_length=2)
    data: Optional[str] = None
    local: Optional[str] = None
    dress_code: Optional[str] = None
    descricao: Optional[str] = None

# ─── Helpers ────────────────────────────────────────────────────────────────

def serialize(doc: dict) -> dict:
    """Converte ObjectId para string e padroniza o campo id."""
    doc["id"] = str(doc.pop("_id"))
    return doc

def get_evento_or_404(evento_id: str) -> dict:
    try:
        oid = ObjectId(evento_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de evento inválido.")
    doc = eventos_col.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    return doc

# ─── Health ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health():
    try:
        client.admin.command("ping")
        return {"status": "ok", "banco": "mongodb", "host": MONGO_HOST}
    except ConnectionFailure:
        raise HTTPException(status_code=503, detail="MongoDB indisponível.")

# ─── Endpoints ──────────────────────────────────────────────────────────────

@app.post("/eventos", status_code=201, tags=["Eventos"])
def criar_evento(evento: EventoCreate):
    """Cadastra um novo evento de grife."""
    doc = evento.model_dump()
    doc["criado_em"] = datetime.now(timezone.utc).isoformat()
    result = eventos_col.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@app.get("/eventos", tags=["Eventos"])
def listar_eventos():
    """Retorna todos os eventos cadastrados."""
    return [serialize(doc) for doc in eventos_col.find()]


@app.get("/eventos/{evento_id}", tags=["Eventos"])
def consultar_evento(evento_id: str):
    """Consulta um evento pelo ID."""
    return serialize(get_evento_or_404(evento_id))


@app.put("/eventos/{evento_id}", tags=["Eventos"])
def atualizar_evento(evento_id: str, dados: EventoUpdate):
    """Atualiza os dados de um evento existente."""
    doc = get_evento_or_404(evento_id)
    atualizacoes = {k: v for k, v in dados.model_dump().items() if v is not None}
    if not atualizacoes:
        raise HTTPException(status_code=400, detail="Nenhum campo válido para atualizar.")
    atualizacoes["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    eventos_col.update_one({"_id": doc["_id"]}, {"$set": atualizacoes})
    return serialize(eventos_col.find_one({"_id": doc["_id"]}))


@app.delete("/eventos/{evento_id}", status_code=200, tags=["Eventos"])
def remover_evento(evento_id: str):
    """Remove um evento pelo ID."""
    doc = get_evento_or_404(evento_id)
    eventos_col.delete_one({"_id": doc["_id"]})
    return {"mensagem": f"Evento '{doc['nome']}' removido com sucesso."}
