# Operação — ReqSys Ollama Local Gateway

## Estado funcional

O gateway possui healthcheck e, na versão 0.3.0, contratos OpenAI-compatible para
`GET /v1/models` e `POST /v1/chat/completions`, ambos protegidos pela mesma autenticação
governada.

## Checklist operacional

- [x] README
- [x] SECURITY.md
- [x] CODEOWNERS
- [x] Dependabot
- [x] Workflows CI/Governance
- [x] Healthcheck inicial
- [x] Descoberta OpenAI-compatible de modelos
- [x] Contrato OpenAI-compatible de chat
- [x] Bearer token fail-closed
- [x] Timeout configurável
- [x] Propagação de correlation_id
- [x] Testes de contrato, autenticação e falha upstream
- [x] E2E real hermético Gateway → Ollama em DEV/CI
- [ ] Smoke adicional no PC24x7 com runtime local autorizado
- [ ] Branch protection em `main`
- [ ] Environments `dev`, `hml`, `prod`
- [ ] Secrets governados, quando necessários
- [ ] Required checks configurados

## Validação do runtime

O E2E hermético deve obter a lista de modelos diretamente do Ollama, consultar `/v1/models`
pelo gateway e provar que o mesmo modelo está presente antes de executar o chat. A evidência deve
permanecer vinculada ao mesmo SHA, ambiente e `correlation_id`.

Testes com mock comprovam contrato e controles de erro, mas não substituem a evidência real.

## Próximo passo operacional

Concluir o hardening administrativo registrado na issue #3 e executar smoke adicional no PC24x7
quando o runtime autorizado estiver disponível, sem promover automaticamente para HML/PROD.
