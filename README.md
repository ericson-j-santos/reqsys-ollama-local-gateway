# ReqSys Ollama Local Gateway

Gateway local governado para integração do ReqSys e de outros projetos com providers locais
compatíveis com Ollama.

## Objetivo

Fornecer uma camada isolada, auditável e segura para chamadas locais de IA, mantendo separação
entre os consumidores e o runtime/provider local.

## Capacidades

- Healthcheck operacional.
- Contrato `GET /v1/models` compatível com descoberta básica de modelos OpenAI.
- Contrato `POST /v1/chat/completions` compatível com o formato básico OpenAI.
- Encaminhamento não-streaming para `Ollama /api/chat`.
- Descoberta de modelos por `Ollama /api/tags`.
- Autenticação Bearer governada.
- Timeout configurável.
- Propagação de `correlation_id`.
- Erros upstream normalizados sem exposição do corpo retornado pelo provider.
- Configuração por variáveis de ambiente.
- Guardrails para evitar exposição de secrets e PII.

## Configuração

| Variável | Padrão | Uso |
| --- | --- | --- |
| `REQSYS_ENV` | `dev` | Ambiente do gateway |
| `REQSYS_OLLAMA_BASE_URL` | `http://localhost:11434` | URL do Ollama |
| `REQSYS_AUTH_REQUIRED` | `true` | Exige Bearer token nos endpoints OpenAI-compatible |
| `REQSYS_API_TOKEN` | vazio | Token esperado pelo gateway |
| `REQSYS_OLLAMA_TIMEOUT_SECONDS` | `30` | Timeout de chamada, máximo 120 s |
| `REQSYS_ALLOWED_ORIGINS` | `http://localhost:3000` | Origens governadas |

Quando `REQSYS_AUTH_REQUIRED=true` e `REQSYS_API_TOKEN` não estiver configurado, os endpoints
OpenAI-compatible falham fechado com HTTP 503.

## Execução local

```bash
python -m reqsys_ollama_gateway.app
```

## Descoberta de modelos

```http
GET /v1/models
Authorization: Bearer <token>
X-Correlation-ID: corr-models-123
```

## Exemplo de chat

```http
POST /v1/chat/completions
Authorization: Bearer <token>
X-Correlation-ID: corr-123
Content-Type: application/json

{
  "model": "qwen2.5-coder:7b",
  "messages": [
    {"role": "user", "content": "Explique este erro."}
  ],
  "stream": false
}
```

O streaming permanece fora deste incremento.

## Segurança

Consulte `SECURITY.md`. Não versione tokens, prompts sensíveis ou dados pessoais desnecessários.
