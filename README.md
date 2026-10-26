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
original/            políticas e testes exatamente como impressos na monografia (Códigos 1 a 8)
figuras/             Figuras 1, 2 e 3 da monografia (PNG) e o script que as gera
.github/workflows/   CI: roda `kyverno test` com o Kyverno CLI 1.11.5, 1.18.1 e 1.19.2
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
impresso, a `restrict-privileged` **não** barra o `test-root` nem o `test-latest`, o que bate com
as Figuras 6 e 7: o `test-root` é recusado só pela `require-nonroot`, e o `test-latest`, pela
`require-nonroot` (o falso positivo) e pela `restrict-latest-tag`.

## Ambiente da monografia

Os testes no cluster (Tabela 6 e Figuras 5 a 8 da monografia) usaram este ambiente:

| Componente | Versão |
|---|---|
| Kubernetes (GKE, canal Regular) | 1.35 (`1.35.8-gke.1796000`) |
| Nós | 2 × `e2-medium` (2 vCPUs e 4 GB de RAM), zona `us-central1-a` |
| Kyverno | 1.18.1, instalado pelo chart do Helm 3.8.1 |
| Helm | 3.21.2 |
| kubectl | 1.35.9 |

Com dois nós `e2-medium`, os componentes do GKE e os quatro controladores do Kyverno (100m de
CPU cada, no padrão do chart) reservaram cerca de 90% da CPU alocável de cada nó. Um Pod que pede
100m de CPU, como o `test-secure`, fica `Pending`. Por isso, para verificar a execução dos Pods no
Teste 4, o cluster foi ampliado temporariamente para três nós.

## Aplicar no cluster

Para recriar o ambiente no GKE, é preciso um projeto com faturamento ativo e a API do
Kubernetes Engine habilitada. Se a versão `1.35.8-gke.1796000` não estiver mais disponível,
usem o patch 1.35 mais recente da lista:

```bash
gcloud container get-server-config --zone us-central1-a --flatten="channels" \
  --filter="channels.channel=REGULAR" --format="yaml(channels.validVersions)"

gcloud container clusters create tcc-kyverno \
  --zone us-central1-a --release-channel regular \
  --cluster-version 1.35.8-gke.1796000 \
  --machine-type e2-medium --num-nodes 2
gcloud container clusters get-credentials tcc-kyverno --zone us-central1-a
```

Instalem o Kyverno com a versão fixada. A versão do chart (3.8.1) é diferente da versão do
Kyverno (1.18.1); a correspondência aparece em `helm search repo kyverno/kyverno --versions`.

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm install kyverno kyverno/kyverno -n kyverno --create-namespace --version 3.8.1
kubectl -n kyverno rollout status deploy/kyverno-admission-controller --timeout=300s
```

Para reproduzir a Tabela 6 e as Figuras 5 a 8, apliquem as políticas e os testes de `original/`,
um teste de cada vez:

```bash
kubectl apply -f original/policies/
kubectl get clusterpolicies     # ADMISSION e BACKGROUND true, READY True, MESSAGE Ready

kubectl apply -f original/tests/test-privileged.yaml   # Figura 5: recusado por 3 políticas
kubectl apply -f original/tests/test-root.yaml         # Figura 6: só a require-nonroot
kubectl apply -f original/tests/test-latest.yaml       # Figura 7: require-nonroot e restrict-latest-tag
kubectl apply -f original/tests/test-secure.yaml       # Figura 8: admitido, mas o nginx falha
kubectl logs test-secure        # após alguns segundos: "Read-only file system"
```

Para testar as políticas corrigidas, troquem as políticas e rodem os testes um de cada vez:

```bash
kubectl delete -f original/policies/
kubectl apply -f policies/

kubectl apply -f tests/t0-seguro.yaml
kubectl get pod t0-seguro              # deve ficar Running
kubectl apply -f tests/t1-privilegiado.yaml   # recusado só pela restrict-privileged
kubectl apply -f tests/d1-deployment-privilegiado.yaml   # recusado na criação do Deployment
```

Se um Pod ficar `Pending` por falta de CPU, adicionem um nó com
`gcloud container clusters resize tcc-kyverno --zone us-central1-a --num-nodes 3`. Para registrar
o ambiente, guardem a saída de `kubectl version` e `helm list -n kyverno`. No fim, apaguem o
cluster para não gerar custo:

```bash
gcloud container clusters delete tcc-kyverno --zone us-central1-a --quiet
```

## Versões

- Testado com o Kyverno CLI **1.11.5**, **1.18.1** (a versão do cluster) e **1.19.2**.
- A partir do Kyverno 1.13, `spec.validationFailureAction` foi substituído por
  `spec.rules[*].validate.failureAction`. O campo antigo ainda funciona, com aviso de
  deprecação.
- Na 1.19, o tipo `ClusterPolicy` (`kyverno.io/v1`) está marcado como deprecated em favor do
  `ValidatingPolicy` (CEL). O CLI emite um aviso, mas as políticas funcionam.
- Os testes de conformidade do Kyverno 1.18.1 rodam em Kubernetes 1.33, 1.34 e 1.35, faixa que
  inclui o 1.35 do cluster. O Kyverno 1.11 suportava oficialmente só Kubernetes 1.25–1.28, por
  isso não serve para esse cluster; o CLI 1.11.5 continua no CI porque a Seção 4.3 da monografia
  cita os resultados nessa versão.

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
