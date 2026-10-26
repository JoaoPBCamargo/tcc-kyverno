#!/bin/bash
# Compara o Pod Security Admission (perfil restricted) com as políticas do Kyverno num cluster local (kind).
#
# Cenários:
#   A = só PSA restricted            (namespace com o rótulo enforce=restricted, sem políticas do Kyverno)
#   B = só Kyverno, políticas corrigidas
#   C = PSA restricted + Kyverno, políticas corrigidas
#   D = só Kyverno, políticas originais (como impressas na monografia)
#
# Requisitos: Docker, kind 0.33.0, kubectl 1.35, Helm 3.21 e python3 no PATH.
# Uso (na raiz do repositório): bash experimentos/psa/comparar-psa.sh
# Saída: experimentos/psa/resultados.jsonl (um caso por linha) e experimentos/psa/versoes.txt
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$REPO/experimentos/psa"
IMAGE="kindest/node:v1.35.8@sha256:07b2536e30b803ed61d1677a79df6115f798ce64c80f9e22f6ed45afd09323c0"
CLUSTER=tcc-psa
export KUBECONFIG="$OUT/.kubeconfig"
: > "$OUT/resultados.jsonl"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "criando o cluster kind (Kubernetes 1.35.8)"
kind create cluster --name "$CLUSTER" --image "$IMAGE" --wait 180s || exit 1
trap 'kind delete cluster --name "$CLUSTER" >/dev/null 2>&1; rm -f "$KUBECONFIG"' EXIT
kubectl version >"$OUT/versoes.txt" 2>&1

log "instalando o Kyverno 1.18.1 (chart 3.8.1)"
helm install kyverno kyverno --repo https://kyverno.github.io/kyverno/ --version 3.8.1 \
  -n kyverno --create-namespace --wait --timeout 12m >/dev/null || exit 1
helm list -n kyverno >>"$OUT/versoes.txt" 2>&1

kubectl create ns psa-restrito >/dev/null
kubectl label ns psa-restrito pod-security.kubernetes.io/enforce=restricted pod-security.kubernetes.io/enforce-version=v1.35 \
  pod-security.kubernetes.io/warn=restricted pod-security.kubernetes.io/warn-version=v1.35 >/dev/null
kubectl create ns sem-psa >/dev/null

CASES=(tests/t0-seguro.yaml tests/t1-privilegiado.yaml tests/t2-root.yaml tests/t3-latest.yaml tests/t4-sem-limites.yaml
       tests/b1-root-no-conteiner.yaml tests/b2-imagem-sem-tag.yaml tests/b3-initcontainer-privilegiado.yaml
       tests/d1-deployment-privilegiado.yaml original/tests/test-privileged.yaml original/tests/test-root.yaml
       original/tests/test-latest.yaml original/tests/test-secure.yaml)

run_case() { # cenario namespace arquivo
  local sc="$1" ns="$2" f="$3" out rc kind pods="" events=""
  kind=$(awk '/^kind:/{print $2; exit}' "$REPO/$f")
  out=$(kubectl apply -n "$ns" -f "$REPO/$f" 2>&1); rc=$?
  if [ $rc -eq 0 ] && [ "$kind" = "Deployment" ]; then
    sleep 12   # tempo para o controlador tentar criar os Pods
    pods=$(kubectl get pods -n "$ns" -l app=d1 --no-headers 2>/dev/null | wc -l | tr -d ' ')
    events=$(kubectl get events -n "$ns" --field-selector reason=FailedCreate \
      -o jsonpath='{range .items[*]}{.message}{"\n"}{end}' 2>/dev/null | tail -1)
  fi
  python3 - "$sc" "$f" "$kind" "$rc" "$out" "$pods" "$events" >>"$OUT/resultados.jsonl" <<'PY'
import json, sys
sc, f, kind, rc, out, pods, events = sys.argv[1:8]
print(json.dumps({"cenario": sc, "caso": f, "kind": kind, "admitido": rc == "0", "saida": out,
                  "pods_criados": pods, "evento": events}, ensure_ascii=False))
PY
  kubectl delete -n "$ns" -f "$REPO/$f" --ignore-not-found --wait=false >/dev/null 2>&1
}

run_all() { # cenario namespace
  for f in "${CASES[@]}"; do run_case "$1" "$2" "$f"; done
  kubectl delete pods,deploy --all -n "$2" --wait=false >/dev/null 2>&1; sleep 3
}

log "cenário A: só PSA restricted"; run_all A psa-restrito
kubectl apply -f "$REPO/policies/" >/dev/null && kubectl wait --for=condition=Ready clusterpolicy --all --timeout=180s >/dev/null
log "cenário B: só Kyverno (corrigidas)"; run_all B sem-psa
log "cenário C: PSA + Kyverno (corrigidas)"; run_all C psa-restrito
kubectl delete -f "$REPO/policies/" >/dev/null 2>&1; sleep 5
kubectl apply -f "$REPO/original/policies/" >/dev/null && kubectl wait --for=condition=Ready clusterpolicy --all --timeout=180s >/dev/null
log "cenário D: só Kyverno (originais)"; run_all D sem-psa
log "fim: $(wc -l < "$OUT/resultados.jsonl") resultados em $OUT/resultados.jsonl"
