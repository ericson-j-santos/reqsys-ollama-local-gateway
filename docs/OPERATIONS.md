# Operação — ReqSys Ollama Local Gateway

## Estado funcional

O gateway possui healthcheck e, na versão 0.2.0, contrato não-streaming
`POST /v1/chat/completions` para encaminhamento ao Ollama local.

## Checklist operacional

- [x] README
- [x] SECURITY.md
- [x] CODEOWNERS
- [x] Dependabot
- [x] Workflows CI/Governance
- [x] Healthcheck inicial
- [x] Contrato OpenAI-compatible de chat
- [x] Bearer token fail-closed
- [x] Timeout configurável
- [x] Propagação de correlation_id
- [x] Testes de contrato, autenticação e falha upstream
- [ ] E2E real contra Ollama local no runtime autorizado
- [ ] Branch protection em `main`
- [ ] Environments `dev`, `hml`, `prod`
- [ ] Secrets governados, quando necessários
- [ ] Required checks configurados

## Validação do runtime

A integração só deve ser considerada ponta a ponta quando uma chamada real ao endpoint do gateway
atingir o Ollama local e a resposta for observada no mesmo SHA/ambiente/correlation_id. Testes com
mock comprovam o contrato e os controles de erro, mas não substituem essa evidência.

## Próximo passo operacional

Após CI/Governance da PR, executar smoke E2E no PC24x7 com Ollama acessível, registrando
`correlation_id`, modelo, SHA e resultado sem persistir prompt sensível.
