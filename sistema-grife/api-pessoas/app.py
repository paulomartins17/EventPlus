from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
import psycopg2
import psycopg2.extras
import os
from datetime import datetime

# ─── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="API de Pessoas",
    description="Microsserviço de gestão de pessoas (celebridades, produtores, agentes, empresários e estilistas) — Sistema EventPlus",
    version="1.0.0",
)

# ─── PostgreSQL ─────────────────────────────────────────────────────────────

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_USER = os.getenv("POSTGRES_USER", "grife_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "grife_pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "grife_db")

TIPOS_VALIDOS = {"celebridade", "produtor", "agente", "empresario", "estilista"}

def get_conn():
    """Retorna uma nova conexão com o PostgreSQL."""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=POSTGRES_DB,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

# ─── Schema SQL (executado na inicialização) ─────────────────────────────────

def init_db():
    """Cria a tabela pessoas se ela não existir."""
    ddl = """
    CREATE TABLE IF NOT EXISTS pessoas (
        id          SERIAL PRIMARY KEY,
        nome        VARCHAR(100) NOT NULL,
        tipo        VARCHAR(50),
        agencia     VARCHAR(100),
        email       VARCHAR(100) UNIQUE,
        telefone    VARCHAR(20),
        criado_em   TIMESTAMP DEFAULT NOW()
    );
    """
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[init_db] Erro ao criar tabela: {e}")

@app.on_event("startup")
def startup():
    init_db()

# ─── Schemas ────────────────────────────────────────────────────────────────

class PessoaCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=100, example="Zendaya")
    tipo: Optional[str] = Field(
        None,
        example="celebridade",
        description="celebridade | produtor | agente | empresario | estilista",
    )
    agencia: Optional[str] = Field(None, max_length=100, example="IMG Models")
    email: Optional[str] = Field(None, max_length=100, example="zendaya@example.com")
    telefone: Optional[str] = Field(None, max_length=20, example="+1 310-555-0100")

class PessoaUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=2, max_length=100)
    tipo: Optional[str] = Field(None)
    agencia: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    telefone: Optional[str] = Field(None, max_length=20)

# ─── Helpers ────────────────────────────────────────────────────────────────

def validar_tipo(tipo: Optional[str]):
    if tipo and tipo not in TIPOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo inválido. Use um dos seguintes: {', '.join(sorted(TIPOS_VALIDOS))}.",
        )

def get_pessoa_or_404(cur, pessoa_id: int) -> dict:
    cur.execute("SELECT * FROM pessoas WHERE id = %s", (pessoa_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Pessoa com id={pessoa_id} não encontrada.")
    return dict(row)

def serialize(row: dict) -> dict:
    """Converte tipos não-serializáveis (datetime) para string."""
    for k, v in row.items():
        if isinstance(v, datetime):
            row[k] = v.isoformat()
    return row

# ─── Health ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health():
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        return {"status": "ok", "banco": "postgresql", "host": POSTGRES_HOST}
    except Exception:
        raise HTTPException(status_code=503, detail="PostgreSQL indisponível.")

# ─── Endpoints ──────────────────────────────────────────────────────────────

@app.post("/pessoas", status_code=201, tags=["Pessoas"])
def cadastrar_pessoa(pessoa: PessoaCreate):
    """Cadastra uma nova pessoa no sistema."""
    validar_tipo(pessoa.tipo)
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pessoas (nome, tipo, agencia, email, telefone)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (pessoa.nome, pessoa.tipo, pessoa.agencia, pessoa.email, pessoa.telefone),
            )
            nova = dict(cur.fetchone())
        conn.commit()
        conn.close()
        return serialize(nova)
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=400, detail="Já existe uma pessoa cadastrada com este e-mail.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno ao cadastrar pessoa: {str(e)}")


@app.get("/pessoas", tags=["Pessoas"])
def listar_pessoas(tipo: Optional[str] = None):
    """Lista todas as pessoas cadastradas. Filtra pelo tipo se informado."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            if tipo:
                validar_tipo(tipo)
                cur.execute("SELECT * FROM pessoas WHERE tipo = %s ORDER BY id", (tipo,))
            else:
                cur.execute("SELECT * FROM pessoas ORDER BY id")
            rows = [serialize(dict(r)) for r in cur.fetchall()]
        conn.close()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno ao listar pessoas: {str(e)}")


@app.get("/pessoas/{pessoa_id}", tags=["Pessoas"])
def consultar_pessoa(pessoa_id: int):
    """Consulta uma pessoa pelo ID."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            pessoa = get_pessoa_or_404(cur, pessoa_id)
        conn.close()
        return serialize(pessoa)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno ao consultar pessoa: {str(e)}")


@app.put("/pessoas/{pessoa_id}", tags=["Pessoas"])
def atualizar_pessoa(pessoa_id: int, dados: PessoaUpdate):
    """Atualiza os dados de uma pessoa existente."""
    validar_tipo(dados.tipo)
    atualizacoes = {k: v for k, v in dados.model_dump().items() if v is not None}
    if not atualizacoes:
        raise HTTPException(status_code=400, detail="Nenhum campo válido para atualizar.")
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            get_pessoa_or_404(cur, pessoa_id)  # garante que existe
            set_clause = ", ".join(f"{col} = %s" for col in atualizacoes)
            valores = list(atualizacoes.values()) + [pessoa_id]
            cur.execute(
                f"UPDATE pessoas SET {set_clause} WHERE id = %s RETURNING *",
                valores,
            )
            atualizada = dict(cur.fetchone())
        conn.commit()
        conn.close()
        return serialize(atualizada)
    except HTTPException:
        raise
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=400, detail="Já existe uma pessoa cadastrada com este e-mail.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno ao atualizar pessoa: {str(e)}")


@app.delete("/pessoas/{pessoa_id}", status_code=200, tags=["Pessoas"])
def remover_pessoa(pessoa_id: int):
    """Remove uma pessoa pelo ID."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            pessoa = get_pessoa_or_404(cur, pessoa_id)
            cur.execute("DELETE FROM pessoas WHERE id = %s", (pessoa_id,))
        conn.commit()
        conn.close()
        return {"mensagem": f"Pessoa '{pessoa['nome']}' removida com sucesso."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno ao remover pessoa: {str(e)}")
