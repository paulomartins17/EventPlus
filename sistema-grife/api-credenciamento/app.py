from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from bson.errors import InvalidId
from typing import Optional
import os
import requests
from datetime import datetime, timezone

# ─── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="API de Credenciamento",
    description="Microsserviço de convites e credenciamento — Sistema EventPlus",
    version="1.0.0",
)

# ─── Configurações ──────────────────────────────────────────────────────────

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_USER = os.getenv("MONGO_USER", "grife_user")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "grife_pass")
MONGO_DB = os.getenv("MONGO_DB", "grife_db")

API_PESSOAS_URL = os.getenv("API_PESSOAS_URL", "http://localhost:8001")
API_EVENTOS_URL = os.getenv("API_EVENTOS_URL", "http://localhost:8002")

# ─── MongoDB ────────────────────────────────────────────────────────────────

client = MongoClient(
    host=MONGO_HOST,
    port=MONGO_PORT,
    username=MONGO_USER,
    password=MONGO_PASSWORD,
    authSource="admin",
)
db = client[MONGO_DB]
convites_col = db["convites"]

# ─── Schemas ────────────────────────────────────────────────────────────────

class ConviteCreate(BaseModel):
    pessoa_id: int = Field(..., example=1, description="ID da pessoa na api-pessoas")
    evento_id: str = Field(..., example="664f1a2b3c4d5e6f7a8b9c0d", description="ID do evento na api-eventos")

class ConviteUpdate(BaseModel):
    observacao: Optional[str] = Field(None, example="VIP — mesa 1")

# ─── Helpers ────────────────────────────────────────────────────────────────

def serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc

def get_convite_or_404(convite_id: str) -> dict:
    try:
        oid = ObjectId(convite_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de convite inválido.")
    doc = convites_col.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Convite não encontrado.")
    return doc

def validar_pessoa(pessoa_id: int) -> dict:
    """Consulta api-pessoas e valida existência da pessoa."""
    try:
        resp = requests.get(f"{API_PESSOAS_URL}/pessoas/{pessoa_id}", timeout=5)
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="api-pessoas indisponível.")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Pessoa com id={pessoa_id} não encontrada.")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Erro ao consultar api-pessoas.")
    return resp.json()

def validar_evento(evento_id: str) -> dict:
    """Consulta api-eventos e valida existência do evento."""
    try:
        resp = requests.get(f"{API_EVENTOS_URL}/eventos/{evento_id}", timeout=5)
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="api-eventos indisponível.")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Evento com id={evento_id} não encontrado.")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Erro ao consultar api-eventos.")
    return resp.json()

# ─── Health ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health():
    try:
        client.admin.command("ping")
        mongo_ok = True
    except ConnectionFailure:
        mongo_ok = False

    pessoas_ok = False
    try:
        r = requests.get(f"{API_PESSOAS_URL}/health", timeout=3)
        pessoas_ok = r.status_code == 200
    except Exception:
        pass

    eventos_ok = False
    try:
        r = requests.get(f"{API_EVENTOS_URL}/health", timeout=3)
        eventos_ok = r.status_code == 200
    except Exception:
        pass

    status = "ok" if all([mongo_ok, pessoas_ok, eventos_ok]) else "degradado"
    return {
        "status": status,
        "dependencias": {
            "mongodb": "ok" if mongo_ok else "falha",
            "api_pessoas": "ok" if pessoas_ok else "falha",
            "api_eventos": "ok" if eventos_ok else "falha",
        },
    }

# ─── Endpoints ──────────────────────────────────────────────────────────────

@app.post("/convites", status_code=201, tags=["Convites"])
def emitir_convite(convite: ConviteCreate):
    """
    Emite um convite para uma pessoa em um evento.
    Valida a existência da pessoa (api-pessoas) e do evento (api-eventos)
    antes de registrar o credenciamento.
    """
    # Verifica se já existe convite ativo para essa combinação
    existente = convites_col.find_one({
        "pessoa_id": convite.pessoa_id,
        "evento_id": convite.evento_id,
        "status": {"$ne": "cancelado"},
    })
    if existente:
        raise HTTPException(
            status_code=409,
            detail="Já existe um convite ativo para esta pessoa neste evento.",
        )

    # Valida pessoa e evento nas APIs externas
    pessoa = validar_pessoa(convite.pessoa_id)
    evento = validar_evento(convite.evento_id)

    doc = {
        "pessoa_id": convite.pessoa_id,
        "pessoa_nome": pessoa.get("nome", ""),
        "evento_id": convite.evento_id,
        "evento_nome": evento.get("nome", ""),
        "status": "pendente",
        "emitido_em": datetime.now(timezone.utc).isoformat(),
        "confirmado_em": None,
        "observacao": None,
    }
    result = convites_col.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@app.get("/convites", tags=["Convites"])
def listar_convites(status: Optional[str] = None):
    """
    Lista todos os convites. Filtra pelo status se informado
    (pendente | confirmado | cancelado).
    """
    filtro = {}
    if status:
        filtro["status"] = status
    return [serialize(doc) for doc in convites_col.find(filtro)]


@app.get("/convites/{convite_id}", tags=["Convites"])
def consultar_convite(convite_id: str):
    """Consulta um convite pelo ID."""
    return serialize(get_convite_or_404(convite_id))


@app.put("/convites/{convite_id}/confirmar", tags=["Convites"])
def confirmar_presenca(convite_id: str):
    """Confirma a presença de um convidado no evento."""
    doc = get_convite_or_404(convite_id)

    if doc["status"] == "confirmado":
        raise HTTPException(status_code=400, detail="Presença já confirmada anteriormente.")
    if doc["status"] == "cancelado":
        raise HTTPException(status_code=400, detail="Não é possível confirmar um convite cancelado.")

    convites_col.update_one(
        {"_id": doc["_id"]},
        {"$set": {
            "status": "confirmado",
            "confirmado_em": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return serialize(convites_col.find_one({"_id": doc["_id"]}))


@app.delete("/convites/{convite_id}", status_code=200, tags=["Convites"])
def cancelar_convite(convite_id: str):
    """Cancela um convite (soft delete — mantém o registro com status 'cancelado')."""
    doc = get_convite_or_404(convite_id)

    if doc["status"] == "cancelado":
        raise HTTPException(status_code=400, detail="Convite já está cancelado.")

    convites_col.update_one(
        {"_id": doc["_id"]},
        {"$set": {
            "status": "cancelado",
            "cancelado_em": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"mensagem": f"Convite de '{doc['pessoa_nome']}' para '{doc['evento_nome']}' cancelado com sucesso."}
