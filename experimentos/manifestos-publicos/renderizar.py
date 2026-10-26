"""Renderiza (helm template, valores padrão) os charts mais populares do Artifact Hub.

Uso: corpus-render.py <ah-search.json> <pasta_saida> <helm>
Grava <pasta_saida>/<repo>__<chart>.yaml e <pasta_saida>/charts.json com versão e status de cada chart.
"""
import json
import subprocess
import sys
from pathlib import Path

search, out, helm = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
out.mkdir(parents=True, exist_ok=True)
packages = json.loads(search.read_text())["packages"]

records = []
for rank, p in enumerate(packages, 1):
    repo, chart, url = p["repository"]["name"], p["name"], p["repository"]["url"]
    rec = {"rank": rank, "repo": repo, "chart": chart, "stars": p.get("stars", 0), "url": url}
    show = subprocess.run([helm, "show", "chart", chart, "--repo", url], capture_output=True, text=True, timeout=180)
    if show.returncode == 0:
        meta = {l.split(":", 1)[0]: l.split(":", 1)[1].strip() for l in show.stdout.splitlines()
                if ":" in l and not l.startswith(" ")}
        rec["version"] = meta.get("version", "").strip("'\"")
        rec["appVersion"] = meta.get("appVersion", "").strip("'\"")
    tpl = subprocess.run([helm, "template", "tcc", chart, "--repo", url, "--namespace", "corpus",
                          "--kube-version", "v1.35.8"], capture_output=True, text=True, timeout=300)
    if tpl.returncode == 0 and tpl.stdout.strip():
        (out / f"{repo}__{chart}.yaml").write_text(tpl.stdout)
        rec["status"] = "ok"
    else:
        rec["status"] = "falhou"
        rec["erro"] = (tpl.stderr.strip().splitlines() or [""])[-1][:300]
    records.append(rec)
    print(f"{rank:>2} {repo}/{chart} {rec.get('version', '?')}: {rec['status']} {rec.get('erro', '')[:120]}", flush=True)

(out / "charts.json").write_text(json.dumps(records, ensure_ascii=False, indent=1))
print("ok:", sum(r["status"] == "ok" for r in records), "de", len(records))
