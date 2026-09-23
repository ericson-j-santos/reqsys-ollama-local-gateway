# Arquitetura — ReqSys Ollama Local Gateway

## Visão

O gateway isola o runtime local de IA dos consumidores. A partir da versão 0.3.0, expõe
descoberta de modelos e chat por contratos OpenAI-compatible, sem exigir que consumidores
conheçam a API nativa do Ollama.

## Fluxos

```text
Consumidor
  -> GET /v1/models
  -> autenticação Bearer
  -> correlation_id
  -> Ollama /api/tags
  -> normalização para lista OpenAI-compatible
```

```text
Consumidor
  -> POST /v1/chat/completions
  -> autenticação Bearer
  -> correlation_id
  -> validação do contrato
  -> Ollama /api/chat (stream=false)
  -> normalização da resposta
  -> resposta OpenAI-compatible
```

## Componentes

- API FastAPI.
- Configuração governada por ambiente.
- Healthcheck com `correlation_id`.
- Endpoint `/v1/models`.
- Endpoint `/v1/chat/completions`.
- Cliente HTTP com timeout limitado.
- Normalização de erros do provider sem propagação de corpo upstream.
- Guardrails de produção.
- CI e workflow de governança.

## Ambientes

- `dev`: execução local.
- `hml`: validação controlada.
- `prod`: bloqueado sem autenticação real e CORS restrito.

## Segurança

- autenticação permanece ligada por padrão;
- endpoints OpenAI-compatible falham fechado se autenticação estiver habilitada sem token;
- token é lido somente de variável de ambiente;
- corpo de erro do Ollama não é devolvido ao consumidor;
- `correlation_id` é propagado ao provider e devolvido ao cliente;
- descoberta de modelos é somente leitura;
- streaming não está habilitado neste incremento.

## Decisões

- Python 3.12.
- FastAPI.
- Pydantic v2.
- HTTPX.
- Testes com pytest.
- Lint com ruff.
- Dependabot ativo.
