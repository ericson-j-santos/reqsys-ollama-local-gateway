# Arquitetura — ReqSys Ollama Local Gateway

## Visão

O gateway isola o runtime local de IA dos consumidores. A partir da versão 0.2.0, expõe um
contrato de chat reutilizável e encaminha a chamada ao Ollama sem expor diretamente o provider.

## Fluxo

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
- endpoint de chat falha fechado se autenticação estiver habilitada sem token;
- token é lido somente de variável de ambiente;
- corpo de erro do Ollama não é devolvido ao consumidor;
- `correlation_id` é propagado ao provider e devolvido ao cliente;
- streaming não está habilitado neste incremento.

## Decisões

- Python 3.12.
- FastAPI.
- Pydantic v2.
- HTTPX.
- Testes com pytest.
- Lint com ruff.
- Dependabot ativo.
