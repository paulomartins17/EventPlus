-- ============================================================
-- Schema PostgreSQL — API de Pessoas
-- Sistema de Gestão de Eventos de Grife (EventPlus)
-- ============================================================

-- Tabela principal de pessoas
CREATE TABLE IF NOT EXISTS pessoas (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(100) NOT NULL,
    tipo        VARCHAR(50),          -- celebridade | produtor | agente | empresario | estilista
    agencia     VARCHAR(100),
    email       VARCHAR(100) UNIQUE,
    telefone    VARCHAR(20),
    criado_em   TIMESTAMP DEFAULT NOW()
);

-- Índice para busca por tipo
CREATE INDEX IF NOT EXISTS idx_pessoas_tipo ON pessoas (tipo);

-- Índice para busca por email (além do UNIQUE já existente)
CREATE INDEX IF NOT EXISTS idx_pessoas_email ON pessoas (email);
