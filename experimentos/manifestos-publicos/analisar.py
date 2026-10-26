"""Aplica as políticas originais e corrigidas aos manifestos renderizados e resume os resultados.

Uso: corpus-analyze.py <pasta_renderizada> <repo_tcc> <kyverno_cli> <saida.json>
"""
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

RENDER, REPO, CLI, OUT = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
WORKLOADS = {"Pod", "Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Job", "CronJob", "ReplicationController"}
POLICIES = ["restrict-privileged", "require-nonroot", "require-limits", "restrict-latest-tag"]


def pod_spec(doc):
    k = doc.get("kind")
    spec = doc.get("spec") or {}
    if k == "Pod":
        return spec
    if k == "CronJob":
        return (((spec.get("jobTemplate") or {}).get("spec") or {}).get("template") or {}).get("spec") or {}
    return (spec.get("template") or {}).get("spec") or {}


def has_tag(image):
    last = image.split("/")[-1]
    return "@" in image or ":" in last


def features(ps):
    """Características usadas para explicar as diferenças entre versões das políticas."""
    pod_sc = ps.get("securityContext") or {}
    conts = ps.get("containers") or []
    inits = ps.get("initContainers") or []
    allc = conts + inits + (ps.get("ephemeralContainers") or [])
    sc = lambda c: c.get("securityContext") or {}
    return {
        "init_count": len(inits),
        "init_privileged": any(sc(c).get("privileged") is True for c in inits),
        "init_no_limits": any(not ((c.get("resources") or {}).get("limits") or {}).get("cpu")
                              or not ((c.get("resources") or {}).get("limits") or {}).get("memory") for c in inits),
        "image_no_tag": any(not has_tag(str(c.get("image", ""))) for c in allc),
        "init_latest": any(str(c.get("image", "")).endswith(":latest") for c in inits),
        "pod_nonroot": pod_sc.get("runAsNonRoot") is True,
        "all_containers_nonroot": bool(allc) and all(sc(c).get("runAsNonRoot") is True for c in allc),
        "container_overrides_root": any(sc(c).get("runAsNonRoot") is False or sc(c).get("runAsUser") == 0 for c in allc),
        "uid0": pod_sc.get("runAsUser") == 0 or any(sc(c).get("runAsUser") == 0 for c in allc),
        "images": [str(c.get("image", "")) for c in allc],
    }


def run(policy_dir, resource):
    p = subprocess.run([CLI, "apply", str(policy_dir), "-r", str(resource), "--policy-report",
                        "--output-format", "json", "--remove-color"], capture_output=True, text=True, timeout=600)
    start = p.stdout.find("{")
    report = json.loads(p.stdout[start:]) if start >= 0 else {"results": []}
    out = defaultdict(set)   # (kind, name) -> {policy: set(result)}
    per = defaultdict(lambda: defaultdict(set))
    for r in report.get("results", []):
        for res in r.get("resources", []):
            per[(res.get("kind"), res.get("name"))][r["policy"]].add(r["result"])
    return per, p.returncode


def verdict(results):
    if not results:
        return "n/a"
    if "fail" in results or "error" in results:
        return "fail"
    if "pass" in results:
        return "pass"
    return "skip"


charts = json.loads((RENDER / "charts.json").read_text())
summary = {"charts": [], "workloads": []}
for ch in charts:
    if ch["status"] != "ok":
        summary["charts"].append({**ch, "workloads": 0})
        continue
    f = RENDER / f"{ch['repo']}__{ch['chart']}.yaml"
    docs = [d for d in yaml.safe_load_all(f.read_text()) if isinstance(d, dict)]
    wl = [d for d in docs if d.get("kind") in WORKLOADS]
    ch_rec = {**ch, "workloads": len(wl)}
    summary["charts"].append(ch_rec)
    if not wl:
        continue
    orig, _ = run(REPO / "original" / "policies", f)
    corr, _ = run(REPO / "policies", f)
    for d in wl:
        key = (d["kind"], (d.get("metadata") or {}).get("name"))
        rec = {"chart": f"{ch['repo']}/{ch['chart']}", "kind": key[0], "name": key[1],
               "features": features(pod_spec(d))}
        for pol in POLICIES:
            rec[f"orig:{pol}"] = verdict(orig.get(key, {}).get(pol, set()))
            rec[f"corr:{pol}"] = verdict(corr.get(key, {}).get(pol, set()))
        summary["workloads"].append(rec)
    print(f"{ch['repo']}/{ch['chart']}: {len(wl)} workloads", flush=True)

OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1))
w = summary["workloads"]
print("\ncharts renderizados:", sum(c["status"] == "ok" for c in summary["charts"]),
      "| com workloads:", sum(c["workloads"] > 0 for c in summary["charts"]), "| workloads:", len(w))
for pol in POLICIES:
    o = Counter(x[f"orig:{pol}"] for x in w); c = Counter(x[f"corr:{pol}"] for x in w)
    newly = sum(x[f"orig:{pol}"] == "pass" and x[f"corr:{pol}"] == "fail" for x in w)
    fixed = sum(x[f"orig:{pol}"] == "fail" and x[f"corr:{pol}"] == "pass" for x in w)
    print(f"{pol:<20} original {dict(o)} | corrigida {dict(c)} | só a corrigida barra: {newly} | só a original barra: {fixed}")
