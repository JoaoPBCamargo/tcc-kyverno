# Políticas Kyverno — repositório de apoio ao TCC

Repositório de apoio à monografia **"Utilização do Kyverno como ferramenta de segurança em
clusters Kubernetes"** (Bacharelado em Ciência da Computação, IFSP – Campus Salto, 2026).

Aqui estão as políticas, os manifestos de teste e os resultados esperados de cada teste.
Com isso, qualquer pessoa consegue reproduzir os experimentos, com ou sem um cluster.

## Estrutura

```
policies/            políticas corrigidas (as que devem ser aplicadas no cluster)
tests/               manifestos de teste: T0–T4 (isolados), B1–B3 (brechas), D1 (Deployment)
kyverno-test.yaml    resultados esperados das políticas corrigidas
original/            políticas e testes exatamente como impressos na versão de 20/10 da monografia
figuras/             Figuras 1, 2 e 3 da monografia (PNG) e o script que as gera
.github/workflows/   CI: roda `kyverno test` com o Kyverno CLI 1.11.5 e 1.19.2
```

## Rodar os testes sem cluster

Só é preciso o Kyverno CLI (`brew install kyverno` ou o binário em
<https://github.com/kyverno/kyverno/releases>):

```bash
kyverno test .
```

O resultado esperado é `Test Summary: 77 tests passed and 0 tests failed`: 49 verificações das
políticas corrigidas e 28 da versão original.

O CLI usa o mesmo motor de políticas do cluster, mas sem passar pela API do Kubernetes. A API
preenche alguns valores padrão (por exemplo, `securityContext: {}` no Pod). Por isso, os caminhos
citados nas mensagens de erro podem diferir um pouco dos que aparecem no `kubectl`.

## Matriz de testes

Cada teste parte do Pod seguro (T0) e muda **uma única coisa**. Assim, cada um deve ser barrado
por exatamente uma política.

| Manifesto | Mudança em relação ao T0 | Deve ser barrado por |
|---|---|---|
| `t0-seguro` | nenhuma (Pod seguro que roda de verdade) | nada; fica `Running` |
| `t1-privilegiado` | `privileged: true`, sem `allowPrivilegeEscalation: false` (a API recusa essa combinação antes de consultar o Kyverno) | `restrict-privileged` |
| `t2-root` | `runAsNonRoot: false` e `runAsUser: 0` | `require-nonroot` |
| `t3-latest` | imagem com a tag `latest` | `restrict-latest-tag` |
| `t4-sem-limites` | sem `resources` | `require-limits` |
| `d1-deployment-privilegiado` | Deployment com template privilegiado | `restrict-privileged` (regra gerada automaticamente pelo autogen) |

O T0 usa `nginxinc/nginx-unprivileged:1.25.0` (porta 8080) com um `emptyDir` em `/tmp`.
A imagem `nginx:1.25.0` não inicia com `runAsUser: 101` e `readOnlyRootFilesystem: true`: o
nginx tenta criar `/var/cache/nginx/client_temp` e falha com "Read-only file system". O T0 também
declara `seccompProfile: RuntimeDefault`, então deve atender ao perfil `restricted` do Pod Security
Admission, o que é útil para comparar PSA e Kyverno.

## Brechas das políticas originais

| Manifesto | Brecha | Versão original | Versão corrigida |
|---|---|---|---|
| `b1-root-no-conteiner` | O Pod declara não-root, mas o contêiner sobrescreve com `runAsUser: 0` | admite | barra (`require-nonroot`) |
| `b2-imagem-sem-tag` | `image: nginx` vira `:latest` implicitamente | admite | barra (`restrict-latest-tag`) |
| `b3-initcontainer-privilegiado` | initContainer privilegiado, com `:latest` e sem limites | admite | barra (3 políticas) |

O que mudou em cada política:

- `restrict-privileged`: passa a verificar também `initContainers` e `ephemeralContainers`.
- `require-nonroot`: aceita `runAsNonRoot: true` no Pod **ou** em todos os contêineres
  (`anyPattern`) e exige `runAsUser > 0` em todos os níveis. Isso também elimina o falso positivo
  do `test-latest` original, que declarava não-root no contêiner.
- `require-limits`: passa a verificar também `initContainers`.
- `restrict-latest-tag`: ganhou uma regra que exige tag explícita (`*:*`). A regra do `:latest`
  passa a cobrir também os `initContainers`.

As correções seguem a biblioteca oficial de políticas do Kyverno (licença Apache-2.0):
`disallow-privileged-containers`, `require-run-as-nonroot`, `require-run-as-non-root-user`,
`require-pod-requests-limits` e `disallow-latest-tag`. Diferença intencional: a política oficial
de recursos não exige limite de CPU (por causa de *throttling*); a deste trabalho exige.

A pasta `original/` documenta o comportamento da versão impressa na monografia. Com o YAML
impresso, a `restrict-privileged` **não** barra o `test-root` nem o `test-latest`, mas nas
Figuras 5 e 6 ela barra. Isso indica que a política aplicada no cluster era diferente da
impressa.

## Aplicar no cluster

Instalem o Kyverno com a versão fixada. A versão do chart do Helm é diferente da versão do
Kyverno; vejam a correspondência com `helm search repo kyverno/kyverno --versions`.

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm install kyverno kyverno/kyverno -n kyverno --create-namespace --version <versão-do-chart>
```

Depois apliquem as políticas e rodem os testes um de cada vez:

```bash
kubectl apply -f policies/
kubectl get clusterpolicies            # ADMISSION, BACKGROUND e READY devem estar true

kubectl apply -f tests/t0-seguro.yaml
kubectl get pod t0-seguro              # deve ficar Running
kubectl apply -f tests/t1-privilegiado.yaml   # recusado só pela restrict-privileged
kubectl apply -f tests/d1-deployment-privilegiado.yaml   # recusado na criação do Deployment
```

Para conferir que a política aplicada é a mesma do texto, rodem
`kubectl get clusterpolicy restrict-privileged -o yaml`. Para registrar o ambiente, guardem a
saída de `kubectl version` e `helm list -n kyverno`.

## Versões

- Testado com o Kyverno CLI **1.11.5** e **1.19.2**.
- A partir do Kyverno 1.13, `spec.validationFailureAction` foi substituído por
  `spec.rules[*].validate.failureAction`. O campo antigo ainda funciona, com aviso de
  deprecação.
- Na 1.19, o tipo `ClusterPolicy` (`kyverno.io/v1`) está marcado como deprecated em favor do
  `ValidatingPolicy` (CEL). O CLI emite um aviso, mas as políticas funcionam.
- O Kyverno 1.11 suporta oficialmente Kubernetes 1.25–1.28. Confiram a matriz de
  compatibilidade da versão usada no cluster.

## Figuras

As Figuras 1, 2 e 3 da monografia são geradas por `figuras/gerar_figuras.py` (Python com matplotlib):

```bash
pip install matplotlib
python figuras/gerar_figuras.py figuras/
```

## Licença

Distribuído sob a licença Apache 2.0 (arquivo `LICENSE`). As políticas em `policies/` são versões modificadas
de políticas da biblioteca oficial do Kyverno (<https://github.com/kyverno/policies>), também licenciada sob
Apache 2.0.
