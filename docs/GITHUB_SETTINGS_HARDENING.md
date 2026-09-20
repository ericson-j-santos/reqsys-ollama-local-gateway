# GitHub Settings Hardening

## Objetivo

Registrar as configurações administrativas necessárias para consolidar o repositório `reqsys-ollama-local-gateway` como gateway governado.

## Estado atual

Bootstrap técnico inicial aplicado:

- README.md
- SECURITY.md
- CODEOWNERS
- Dependabot
- Pull Request template
- Workflows CI e Governance
- App FastAPI mínimo
- Configuração governada
- Teste inicial
- Documentação de arquitetura e operação

## Pendências administrativas

Estas configurações dependem de tela/API administrativa do GitHub fora das ações expostas nesta sessão.

| Item | Configuração recomendada | Risco se ausente |
|---|---|---|
| Branch protection | Proteger `main` | Merge direto sem gate |
| Required checks | Exigir `CI` e `Governance` | Código sem validação obrigatória |
| Environments | Criar `dev`, `hml`, `prod` | Ambientes sem segregação formal |
| Production approval | Aprovação obrigatória em `prod` | Promoção sem aceite humano |
| Secrets/variables | Criar apenas quando necessários | Configuração local/manual dispersa |
| Auto-merge | Habilitar após estabilidade dos gates | Esteira continua manual |
| Update branch | Habilitar sugestão/update de branch | PRs podem ficar defasados |

## Configuração recomendada para `main`

- Require a pull request before merging.
- Require status checks to pass before merging.
- Required checks:
  - `CI`
  - `Governance`
- Require branches to be up to date before merging.
- Require conversation resolution before merging.
- Include administrators quando a esteira estiver estável.

## Environments recomendados

| Environment | Regras |
|---|---|
| `dev` | Sem approval obrigatório, sem secrets produtivos |
| `hml` | Approval opcional, secrets de homologação |
| `prod` | Approval obrigatório, secrets produtivos segregados |

## Critério de conclusão

O hardening administrativo estará concluído quando:

- `main` estiver protegida;
- `CI` e `Governance` forem required checks;
- `dev`, `hml`, `prod` existirem;
- `prod` exigir aprovação humana;
- secrets/variables estiverem segregados por environment;
- auto-merge/update branch estiverem habilitados, se a política operacional permitir.
