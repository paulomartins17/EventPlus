# Sistema de Gestão de Eventos de Grife

Plataforma distribuída de microsserviços para gerenciar eventos de moda de alto padrão, inspirada no Met Gala.

---

## Arquitetura

```
                    ┌─────────────────┐
                    │  api-pessoas    │ :8001
                    │  (FastAPI)      │──────► postgres-db :5432
                    └─────────────────┘
                            ▲
                            │ HTTP
                    ┌─────────────────┐
                    │api-credenciamento│ :8003
                    │  (FastAPI)      │
                    └─────────────────┘
                            │ HTTP
                            ▼
                    ┌─────────────────┐
                    │  api-eventos    │ :8002
                    │  (FastAPI)      │──────► mongo-db :27017
                    └─────────────────┘

        Todos os containers conectados via: grife-network (bridge)
```

## Estrutura de Arquivos

```
sistema-grife/
├── api-pessoas/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── api-eventos/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── api-credenciamento/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
├── .env
└── README.md
```

---

## Como Executar

### Pré-requisitos
- Docker Desktop instalado e rodando
- Docker Compose v2+

### 1. Configurar variáveis de ambiente

O arquivo `.env` já está preenchido com valores padrão. Edite se necessário:

```env
POSTGRES_USER=grife_user
POSTGRES_PASSWORD=grife_pass
POSTGRES_DB=grife_db

MONGO_USER=grife_user
MONGO_PASSWORD=grife_pass
MONGO_DB=grife_db
```

### 2. Subir todos os containers

```bash
docker compose up --build
```

### 3. Verificar se os containers estão rodando

```bash
docker compose ps
```

### 4. Parar os containers

```bash
docker compose down
```

Para remover também os volumes (apaga dados persistidos):

```bash
docker compose down -v
```

---

## Endpoints das APIs

### API de Pessoas — `http://localhost:8001`

| Método | Rota            | Descrição                  |
|--------|-----------------|----------------------------|
| POST   | /pessoas        | Cadastrar nova pessoa       |
| GET    | /pessoas        | Listar todas as pessoas     |
| GET    | /pessoas/{id}   | Consultar pessoa por ID     |
| PUT    | /pessoas/{id}   | Atualizar dados de pessoa   |
| DELETE | /pessoas/{id}   | Remover pessoa              |

### API de Eventos — `http://localhost:8002`

| Método | Rota            | Descrição                  |
|--------|-----------------|----------------------------|
| POST   | /eventos        | Criar evento                |
| GET    | /eventos        | Listar eventos              |
| GET    | /eventos/{id}   | Consultar evento por ID     |
| PUT    | /eventos/{id}   | Atualizar evento            |
| DELETE | /eventos/{id}   | Remover evento              |

### API de Credenciamento — `http://localhost:8003`

| Método | Rota                      | Descrição                        |
|--------|---------------------------|----------------------------------|
| POST   | /convites                 | Emitir convite (valida pessoa + evento) |
| GET    | /convites                 | Listar todos os convites         |
| GET    | /convites/{id}            | Consultar convite por ID         |
| PUT    | /convites/{id}/confirmar  | Confirmar presença               |
| DELETE | /convites/{id}            | Cancelar convite                 |

---

## Exemplos de Uso (curl)

```bash
# Criar uma pessoa
curl -X POST http://localhost:8001/pessoas \
  -H "Content-Type: application/json" \
  -d '{"nome": "Anna Wintour", "tipo": "produtor", "email": "anna@vogue.com"}'

# Listar pessoas
curl http://localhost:8001/pessoas

# Criar um evento
curl -X POST http://localhost:8002/eventos \
  -H "Content-Type: application/json" \
  -d '{"nome": "Met Gala 2025", "tema": "Tempo e Moda", "data": "2025-05-05", "local": "Metropolitan Museum, NY", "dress_code": "Black Tie"}'

# Listar eventos
curl http://localhost:8002/eventos

# Emitir um convite
curl -X POST http://localhost:8003/convites \
  -H "Content-Type: application/json" \
  -d '{"pessoa_id": 1, "evento_id": "<id_do_evento>"}'

# Confirmar presença
curl -X PUT http://localhost:8003/convites/<id_do_convite>/confirmar
```

---

## Variáveis de Ambiente Disponíveis para as APIs

### api-pessoas
| Variável          | Descrição                  |
|-------------------|----------------------------|
| `POSTGRES_HOST`   | Hostname do banco (postgres-db) |
| `POSTGRES_PORT`   | Porta do PostgreSQL (5432)  |
| `POSTGRES_USER`   | Usuário do banco            |
| `POSTGRES_PASSWORD` | Senha do banco            |
| `POSTGRES_DB`     | Nome do banco               |

### api-eventos
| Variável          | Descrição                  |
|-------------------|----------------------------|
| `MONGO_HOST`      | Hostname do MongoDB (mongo-db) |
| `MONGO_PORT`      | Porta do MongoDB (27017)    |
| `MONGO_USER`      | Usuário do MongoDB          |
| `MONGO_PASSWORD`  | Senha do MongoDB            |
| `MONGO_DB`        | Nome do banco               |

### api-credenciamento
Recebe todas as variáveis do MongoDB acima, mais:

| Variável            | Descrição                       |
|---------------------|---------------------------------|
| `API_PESSOAS_URL`   | URL interna da api-pessoas      |
| `API_EVENTOS_URL`   | URL interna da api-eventos      |

---

## Documentação Automática (Swagger)

Com os containers rodando, acesse a documentação interativa:

- API Pessoas: http://localhost:8001/docs
- API Eventos: http://localhost:8002/docs
- API Credenciamento: http://localhost:8003/docs
