"""Gera as Figuras 1, 2 e 3 da monografia. Uso: python gerar_figuras.py [pasta_de_saida]"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
OUT.mkdir(parents=True, exist_ok=True)
ARIAL = ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf")
if all(Path(f).exists() for f in ARIAL):
    for f in ARIAL:
        font_manager.fontManager.addfont(f)
    plt.rcParams["font.family"] = "Arial"

INK = "#2E3A46"
LINE = "#4A5868"
FILL = "#EEF3F8"
GROUP = "#F7F9FB"
ACCENT = "#E3F1E8"
ACCENT_LINE = "#2F6B4A"
DENY = "#FBE9E7"
DENY_LINE = "#A23B2A"


def canvas(w_in, h_in):
    fig = plt.figure(figsize=(w_in, h_in), dpi=300)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w_in)
    ax.set_ylim(0, h_in)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, fill=FILL, edge=LINE, size=7.6, bold=False, lw=0.9, dashed=False, color=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.06",
                                fc=fill, ec=edge, lw=lw, ls=(0, (3, 2)) if dashed else "solid"))
    if text:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size,
                fontweight="bold" if bold else "normal", color=color, linespacing=1.25)


def group(ax, x, y, w, h, title, fill=GROUP, edge=LINE, size=8.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.09",
                                fc=fill, ec=edge, lw=1.0))
    ax.text(x + 0.12, y + h - 0.13, title, ha="left", va="top", fontsize=size, fontweight="bold", color=INK)


def arrow(ax, p, q, both=False, color=LINE, dashed=False, lw=0.9, rad=0.0, label=None, lpos=0.5,
          loff=(0, 0.09), lsize=6.6, lcolor=None):
    st = "<|-|>" if both else "-|>"
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=st, mutation_scale=7, color=color, lw=lw,
                                 ls=(0, (3, 2)) if dashed else "solid",
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=1.5, shrinkB=1.5))
    if label:
        lx = p[0] + (q[0] - p[0]) * lpos + loff[0]
        ly = p[1] + (q[1] - p[1]) * lpos + loff[1]
        ax.text(lx, ly, label, ha="center", va="center", fontsize=lsize, color=lcolor or color,
                linespacing=1.2, bbox=dict(fc="white", ec="none", pad=0.6))


def save(fig, name):
    fig.savefig(OUT / name, dpi=300, facecolor="white")
    plt.close(fig)


# ---------------- Figura 1: arquitetura de um cluster Kubernetes ----------------
fig, ax = canvas(6.3, 3.75)
group(ax, 0.15, 0.2, 2.85, 2.95, "Plano de controle")
box(ax, 1.95, 3.25, 0.95, 0.42, "kubectl\n(usuário)", fill="white", size=7.0)
box(ax, 1.95, 0.4, 0.95, 2.3, "kube-\napiserver", fill=ACCENT, edge=ACCENT_LINE, bold=True, size=8)
comps = ["etcd", "kube-scheduler", "kube-controller-\nmanager", "cloud-controller-\nmanager"]
for i, lab in enumerate(comps):
    yy = 2.2 - i * 0.6
    box(ax, 0.3, yy, 1.3, 0.47, lab, size=7.0)
    arrow(ax, (1.6, yy + 0.235), (1.95, yy + 0.235), both=True)
arrow(ax, (2.425, 3.25), (2.425, 2.7))
for i, (yy, title) in enumerate(((1.8, "Nó de trabalho 1"), (0.2, "Nó de trabalho 2"))):
    group(ax, 3.35, yy, 2.8, 1.4, title)
    box(ax, 3.5, yy + 0.67, 0.78, 0.38, "kubelet")
    box(ax, 4.37, yy + 0.67, 0.78, 0.38, "kube-proxy", size=7.0)
    box(ax, 5.24, yy + 0.67, 0.78, 0.38, "Runtime\n(CRI)", size=6.8)
    box(ax, 3.5, yy + 0.14, 1.22, 0.38, "Pod", fill="white")
    box(ax, 4.8, yy + 0.14, 1.22, 0.38, "Pod", fill="white")
arrow(ax, (2.9, 2.2), (3.5, 2.66), both=True)
arrow(ax, (2.9, 0.9), (3.5, 1.06), both=True)
save(fig, "fig1-cluster.png")

# ---------------- Figura 2: fluxo de requisição pelos Admission Controllers ----------------
fig, ax = canvas(6.3, 2.85)
labels = ["Requisição\n(kubectl apply)", "Autenticação", "Autorização\n(RBAC)", "Admissão de\nmutação",
          "Validação do\nesquema", "Admissão de\nvalidação", "Persistência\n(etcd)"]
w, h, gap, x0, y0 = 0.78, 0.62, 0.115, 0.1, 1.95
xs = [x0 + i * (w + gap) for i in range(len(labels))]
for i, (x, lab) in enumerate(zip(xs, labels)):
    fill = ACCENT if i in (3, 5) else ("white" if i in (0, 6) else FILL)
    edge = ACCENT_LINE if i in (3, 5) else LINE
    box(ax, x, y0, w, h, lab, fill=fill, edge=edge, size=7.0, bold=i in (3, 5))
    if i:
        arrow(ax, (xs[i - 1] + w, y0 + h / 2), (x, y0 + h / 2))
ax.text(xs[1], y0 + h + 0.12, "kube-apiserver", fontsize=7.4, fontweight="bold", color=INK, ha="left")
ax.plot([xs[1], xs[6] + w], [y0 + h + 0.07] * 2, color=LINE, lw=0.7)
for i, lab in ((3, "Webhooks de mutação\n(ex.: Kyverno)"), (5, "Webhooks de validação\n(ex.: Kyverno)")):
    box(ax, xs[i] - 0.17, 0.9, w + 0.34, 0.55, lab, fill=ACCENT, edge=ACCENT_LINE, size=6.6)
    arrow(ax, (xs[i] + w / 2, y0), (xs[i] + w / 2, 1.45), both=True)
box(ax, 4.55, 0.1, 1.65, 0.5, "Requisição negada:\nerro devolvido ao solicitante",
    fill=DENY, edge=DENY_LINE, size=6.6, color=DENY_LINE)
arrow(ax, (xs[5] + w / 2, 0.9), (xs[5] + w / 2, 0.6), color=DENY_LINE, dashed=True,
      label="nega", lpos=0.5, loff=(0.2, 0.0), lcolor=DENY_LINE)
ax.text(0.1, 0.12, "Qualquer etapa pode recusar a requisição;\nnesse caso, nada é gravado no etcd.",
        fontsize=6.4, color="#5B6773", ha="left", va="bottom", linespacing=1.3)
save(fig, "fig2-admissao.png")

# ---------------- Figura 3: arquitetura do Kyverno como Admission Controller ----------------
fig, ax = canvas(6.3, 3.6)
box(ax, 0.1, 2.75, 1.35, 0.55, "Usuário ou pipeline\n(kubectl apply)", fill="white", size=7.0)
box(ax, 0.1, 1.55, 1.35, 0.6, "kube-apiserver", fill=FILL, bold=True, size=7.8)
box(ax, 0.1, 0.3, 1.35, 0.5, "etcd", fill="white")
arrow(ax, (0.78, 2.75), (0.78, 2.15))
arrow(ax, (0.78, 1.55), (0.78, 0.8), label="se admitido", lpos=0.5, loff=(0.0, 0.0), lsize=6.3)
group(ax, 2.25, 0.3, 3.95, 3.0, "Kyverno (namespace kyverno)", fill="#F3F8F5", edge=ACCENT_LINE)
box(ax, 2.45, 1.75, 1.7, 0.85, "Controlador de admissão\n(webhooks de mutação\ne de validação)", fill=ACCENT,
    edge=ACCENT_LINE, size=6.8, bold=True)
box(ax, 2.45, 0.5, 1.7, 0.75, "Controlador de\nbackground\n(varre recursos existentes)", size=6.6)
box(ax, 4.35, 2.25, 1.7, 0.6, "Políticas\n(ClusterPolicy em YAML)", fill="white", size=6.8)
box(ax, 4.35, 1.55, 1.7, 0.35, "PolicyReports", fill="white", size=6.8, dashed=True)
box(ax, 4.35, 0.98, 1.7, 0.42, "Controlador de relatórios", size=6.6)
box(ax, 4.35, 0.5, 1.7, 0.36, "Controlador de limpeza", size=6.6)
arrow(ax, (4.35, 2.5), (4.15, 2.35), dashed=True, label="lê", lpos=0.5, loff=(0.0, 0.12))
arrow(ax, (5.2, 1.4), (5.2, 1.55), color="#9AA5B1")
arrow(ax, (4.15, 0.95), (4.35, 1.15), dashed=True, color="#9AA5B1")
arrow(ax, (1.45, 2.0), (2.45, 2.35))
ax.text(1.85, 2.42, "AdmissionReview", fontsize=6.6, color=LINE, ha="center", va="bottom")
arrow(ax, (2.45, 1.95), (1.45, 1.7), color=ACCENT_LINE)
ax.text(1.85, 1.55, "permitir / negar\n+ mensagem", fontsize=6.6, color=ACCENT_LINE, ha="center", va="top",
        linespacing=1.2)
save(fig, "fig3-kyverno.png")
print("ok")
