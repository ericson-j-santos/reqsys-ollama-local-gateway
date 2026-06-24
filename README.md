# ReqSys Ollama Local Gateway

Gateway local governado para integração do ReqSys com providers locais compatíveis com Ollama.

## Objetivo

Fornecer uma camada isolada, auditável e segura para chamadas locais de IA, mantendo separação entre o repositório principal ReqSys e o runtime/provider local.

## Escopo inicial

- Healthcheck operacional.
- Configuração por variáveis de ambiente.
- Contratos JSON versionáveis.
- Logs estruturados com `correlation_id`.
- Guardrails para evitar exposição de secrets e PII.

## Fora do escopo inicial

- Deploy em produção sem aprovação humana.
- Exposição pública sem autenticação.
- Administração remota de modelos sem RBAC.
- Persistência de prompts sensíveis.

## Execução local planejada

```bash
python -m reqsys_ollama_gateway.app
```

## Segurança

Consulte `SECURITY.md`.
