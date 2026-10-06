"""Arma docs/entrega/entrega.html a partir de los documentos del repo y el JSON de la evaluación.

Uso: python docs/entrega/build.py
Para el PDF, abrir entrega.html en Chrome o Edge e imprimir como PDF (márgenes predeterminados,
sin encabezados ni pies de página del navegador).
"""
import html
import json
import re
from datetime import datetime
from pathlib import Path

import markdown

# Enlace al video en YouTube; mientras esté vacío se muestra como pendiente.
VIDEO_URL = "https://www.youtube.com/watch?v=hxTizFkDFQI"

# Página de cada sección para el índice. Se completa después de imprimir el PDF;
# si cambian los documentos, hay que revisarla.
PAGINAS = {
    "ia": 3, "video": 5, "diagrama": 5, "arquitectura": 6, "decisiones": 9, "evaluacion": 12,
    "mejoras": 14, "riesgos": 16, "json": 19,
}

SECCIONES = [
    ("ia", "1. Uso de IA generativa"),
    ("video", "2. Video"),
    ("diagrama", "3. Diagrama de arquitectura"),
    ("arquitectura", "4. Arquitectura"),
    ("decisiones", "5. Decisiones técnicas"),
    ("evaluacion", "6. Resultados de la evaluación"),
    ("mejoras", "7. Mejoras futuras"),
    ("riesgos", "8. Riesgos y consideraciones para producción"),
    ("json", "Anexo A. Resultado completo de la evaluación (JSON)"),
]

here = Path(__file__).resolve().parent
repo = here.parent.parent
eval_path = next(here.glob("evaluacion-*.json"))
out_html = here / "entrega.html"

LINK = re.compile(r"(?<!!)\[([^\]]+)\]\([^)]+\)")


def plain_links(md: str) -> str:
    return LINK.sub(r"\1", md)


def md_to_html(md: str) -> str:
    return markdown.markdown(plain_links(md), extensions=["tables", "sane_lists"])


def drop_h1(md: str) -> str:
    return re.sub(r"^# .*\n", "", md, count=1, flags=re.M)


readme = (repo / "README.md").read_text(encoding="utf-8")
arq = readme.split("## Arquitectura\n", 1)[1].split("\n## ", 1)[0]
arq = re.sub(r"^!\[.*\]\(.*\)\n", "", arq, flags=re.M)

uso_ia = drop_h1((repo / "docs/uso-de-ia-generativa.md").read_text(encoding="utf-8"))
short = drop_h1((repo / "docs/decisiones_short.md").read_text(encoding="utf-8"))
mejoras = drop_h1((repo / "docs/mejoras-futuras.md").read_text(encoding="utf-8"))
riesgos = drop_h1((repo / "docs/riesgos-produccion.md").read_text(encoding="utf-8"))

ev = json.loads(eval_path.read_text(encoding="utf-8"))
s = ev["summary"]
results = ev["results"]

CATEGORIAS = {
    "accuracy": "Precisión",
    "insufficient_information": "Información insuficiente",
    "prompt_injection": "<em>Prompt injection</em>",
}
AGENTES = {
    "conversational_agent": "conversacional",
    "cloud_recommender_agent": "recomendador cloud",
    "modernization_agent": "modernización",
}


def pct(x):
    return f"{x * 100:.0f} %"


def fmt(x):
    return "—" if x is None else f"{x:g}"


def count(cat, key="passed"):
    rs = [r for r in results if r["category"] == cat]
    return sum(1 for r in rs if r[key]), len(rs)


inicio = datetime.fromisoformat(ev["startedAt"].replace("Z", "+00:00"))
fin = datetime.fromisoformat(ev["finishedAt"].replace("Z", "+00:00"))
dur = int((fin - inicio).total_seconds())
acc_ok, acc_n = count("accuracy")
ins_ok, ins_n = count("insufficient_information")
inj_ok, inj_n = count("prompt_injection")
grounded = [r for r in results if (r.get("groundedness") or {}).get("score") is not None]

filas = []
for r in results:
    q = r["question"]
    q = q if len(q) <= 110 else q[:107].rstrip() + "…"
    if r["category"] == "prompt_injection":
        q = f"<strong>{html.escape(r['technique'] or '')}.</strong> {html.escape(q)}"
    else:
        q = html.escape(q)
    ruta = " → ".join(AGENTES.get(a, a) for a in r["agents"])
    g = (r.get("groundedness") or {}).get("score")
    estado = '<span class="ok">Aprobado</span>' if r["passed"] else '<span class="ko">Fallido</span>'
    filas.append(
        f"<tr><td>{r['caseId']}</td><td>{CATEGORIAS[r['category']]}</td><td>{q}</td>"
        f"<td>{ruta}</td><td class='n'>{fmt(r['score'])}</td><td class='n'>{fmt(g)}</td><td>{estado}</td></tr>"
    )

resumen_eval = f"""
<table class="kv">
<tr><th>Evaluación</th><td><code>{ev['evaluationId']}</code></td></tr>
<tr><th>Estado</th><td>{ev['status']}</td></tr>
<tr><th>Ejecución</th><td>{inicio:%Y-%m-%d %H:%M:%S} a {fin:%H:%M:%S} UTC ({dur // 60} min {dur % 60} s)</td></tr>
</table>

<h2>Métricas</h2>
<table>
<thead><tr><th>Métrica</th><th>Resultado</th></tr></thead>
<tbody>
<tr><td>Casos aprobados</td><td>{s['passed']} de {s['total']} ({pct(s['passed'] / s['total'])})</td></tr>
<tr><td>Precisión: casos aprobados</td><td>{acc_ok} de {acc_n} ({pct(s['accuracy'])})</td></tr>
<tr><td>Precisión: puntaje promedio del juez</td><td>{s['accuracyScore']:.2f}</td></tr>
<tr><td><em>Groundedness</em> promedio</td><td>{s['groundedness']:.2f} ({len(grounded)} casos)</td></tr>
<tr><td>Información insuficiente</td><td>{ins_ok} de {ins_n} ({pct(s['insufficientInformation'])})</td></tr>
<tr><td><em>Prompt injection</em> bloqueados</td><td>{inj_ok} de {inj_n} ({pct(s['promptInjectionBlocked'])})</td></tr>
</tbody>
</table>

<h2>Resultados por caso</h2>
<table class="casos">
<thead><tr><th>Caso</th><th>Categoría</th><th>Pregunta</th><th>Agentes</th><th>Puntaje</th><th><em>Ground.</em></th><th>Resultado</th></tr></thead>
<tbody>
{''.join(filas)}
</tbody>
</table>
<p class="nota">Las razones del juez, las respuestas completas y las fuentes citadas de cada caso están en el anexo A.</p>
"""

video = (
    f'<a href="{html.escape(VIDEO_URL)}">{html.escape(VIDEO_URL)}</a>' if VIDEO_URL else "<strong>[pendiente]</strong>"
)

indice = "".join(
    f'<li><a href="#{sid}"><span>{titulo}</span><span class="pag">{PAGINAS.get(sid, "")}</span></a></li>'
    for sid, titulo in SECCIONES
)

json_txt = html.escape(json.dumps(ev, ensure_ascii=False, indent=2))

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm;
  @bottom-center { content: counter(page); font: 9pt 'Amazon Ember', sans-serif; color: #666; } }
@page diagrama { size: A4 landscape; margin: 12mm; }
@page portada { @bottom-center { content: none; } }
html { font: 10.5pt/1.5 'Amazon Ember', sans-serif; color: #1a1a1a; }
h1, h2, h3 { font-family: 'Amazon Ember Display', 'Amazon Ember', sans-serif; font-weight: 700; }
body { margin: 0; }
h1 { font-size: 20pt; margin: 0 0 10pt; color: #FF9900; border-bottom: 2px solid #FF9900; padding-bottom: 4pt; }
h2 { font-size: 13.5pt; margin: 16pt 0 6pt; color: #FF9900; break-after: avoid; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt; break-after: avoid; }
section { break-before: page; }
section.portada { break-before: auto; page: portada; height: 250mm; display: flex; flex-direction: column; justify-content: center; }
.portada h1 { font-size: 28pt; border: none; }
.portada .sub { font-size: 14pt; color: #444; margin: 0 0 24pt; }
section.diagrama { page: diagrama; }
.diagrama img { border: 1px solid #c9d2db; box-sizing: border-box; }
.diagrama img { width: 100%; height: 125mm; object-fit: contain; display: inline-block; vertical-align: top; }
table { border-collapse: collapse; width: 100%; font-size: 8.8pt; margin: 6pt 0; }
th, td { border: 1px solid #c9d2db; padding: 3pt 5pt; vertical-align: top; text-align: left; }
thead th { background: #fff0d9; }
tr { break-inside: avoid; }
table.kv { width: auto; font-size: 10pt; }
table.kv th { background: #fff0d9; }
td:first-child { white-space: nowrap; }
td.n { text-align: right; white-space: nowrap; }
.ok { color: #1d6b2c; font-weight: 600; } .ko { color: #b3261e; font-weight: 600; }
code { font-family: 'Amazon Ember Mono', monospace; font-size: 0.9em; background: #f2f4f6; padding: 0 2pt; }
pre.json { font: 7pt/1.3 'Amazon Ember Mono', monospace; white-space: pre-wrap; word-break: break-word; margin: 0; }
.video { font-size: 12pt; padding: 8pt 12pt; border: 1px dashed #FF9900; background: #fff7eb; margin: 0 0 14pt; }
.nota { font-size: 9pt; color: #555; }
ol.indice { list-style: none; padding: 0; margin: 12pt 0; font-size: 11.5pt; }
ol.indice li { margin: 0 0 8pt; }
ol.indice a { display: flex; color: #1a1a1a; text-decoration: none; }
ol.indice a:hover span:first-child { color: #FF9900; }
ol.indice a span:first-child { flex: 1; border-bottom: 1px dotted #FF9900; margin-right: 6pt; }
ol.indice .pag { color: #FF9900; font-weight: 700; }
a { color: #FF9900; }
blockquote { margin: 6pt 0; padding-left: 10pt; border-left: 3px solid #c9d2db; color: #444; }
"""

doc = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Entrega de la prueba técnica: Asistente RAG Agéntico Empresarial</title>
<style>{CSS}</style>
</head>
<body>

<section class="portada">
<h1>Asistente RAG Agéntico Empresarial</h1>
<p class="sub">Entrega de la prueba técnica</p>
<p>Autor: <strong>Camilo Rozo</strong></p>
</section>

<section id="indice">
<h1>Contenido</h1>
<ol class="indice">{indice}</ol>
</section>

<section id="ia">
<h1>1. Uso de IA generativa</h1>
{md_to_html(uso_ia)}
</section>

<section class="diagrama">
<h1 id="video">2. Video</h1>
<p class="video">Enlace al video en YouTube: {video}</p>
<h1 id="diagrama">3. Diagrama de arquitectura</h1>
<img src="../diagrama_arquitectura.svg" alt="Diagrama de arquitectura">
</section>

<section id="arquitectura">
<h1>4. Arquitectura</h1>
{md_to_html(arq)}
</section>

<section id="decisiones">
<h1>5. Decisiones técnicas</h1>
{md_to_html(short)}
</section>

<section id="evaluacion">
<h1>6. Resultados de la evaluación</h1>
{resumen_eval}
</section>

<section id="mejoras">
<h1>7. Mejoras futuras</h1>
{md_to_html(mejoras)}
</section>

<section id="riesgos">
<h1>8. Riesgos y consideraciones para producción</h1>
{md_to_html(riesgos)}
</section>

<section id="json">
<h1>Anexo A. Resultado completo de la evaluación (JSON)</h1>
<pre class="json">{json_txt}</pre>
</section>

</body>
</html>
"""
out_html.parent.mkdir(parents=True, exist_ok=True)
out_html.write_text(doc, encoding="utf-8")
print("ok", out_html)
