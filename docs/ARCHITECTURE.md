# Arquitetura — ReqSys Ollama Local Gateway

## Visão

O gateway isola o runtime local de IA do repositório principal ReqSys.

## Componentes

- API FastAPI.
- Configuração governada por ambiente.
- Healthcheck com `correlation_id`.
- Guardrails de produção.
- CI e workflow de governança.

## Ambientes

- `dev`: execução local.
- `hml`: validação controlada.
- `prod`: bloqueado sem autenticação real e CORS restrito.

## Decisões iniciais

- Python 3.12.
- FastAPI.
- Testes com pytest.
- Lint com ruff.
- Dependabot ativo.
