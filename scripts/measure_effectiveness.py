#!/usr/bin/env python3
"""
measure_effectiveness.py — AI Memory Brain ROI Report

Consulta el stack en vivo y produce métricas prácticas para responder:
  1. ¿Se está usando el MCP? (señales de activación)
  2. ¿Qué valor está aportando? (memorias calientes, errores evitados)
  3. ¿Qué tan sano está el cerebro? (salud biológica)
  4. Score global de utilización

Uso:
    python scripts/measure_effectiveness.py
    python scripts/measure_effectiveness.py --project mi-proyecto
    python scripts/measure_effectiveness.py --json   # salida JSON pura
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

BASE_URL = os.getenv("AI_MEMORY_BASE_URL", "http://127.0.0.1:8050")
API_KEY = os.getenv("MEMORY_API_KEY", "")

HEADERS = {"X-Api-Key": API_KEY} if API_KEY else {}


# ── Helpers HTTP ─────────────────────────────────────────────────────────────

def api_get(path: str, params: dict | None = None) -> Any:
    r = httpx.get(f"{BASE_URL}{path}", params=params, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


def api_post(path: str, body: dict) -> Any:
    r = httpx.post(
        f"{BASE_URL}{path}",
        json=body,
        headers={**HEADERS, "Content-Type": "application/json"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ── Helpers de formato ───────────────────────────────────────────────────────

WIDTH = 62


def header(title: str) -> None:
    print(f"\n{'═' * WIDTH}")
    print(f"  {title}")
    print("═" * WIDTH)


def row(label: str, value: Any, note: str = "") -> None:
    note_str = f"  ← {note}" if note else ""
    print(f"  {label:<36}{str(value):>12}{note_str}")


def bar(val: float, max_val: float = 1.0, width: int = 20) -> str:
    pct = min(1.0, max(0.0, val / max(max_val, 1e-9)))
    filled = int(pct * width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {pct * 100:.0f}%"


def clamp01(v: float) -> float:
    return min(1.0, max(0.0, v))


# ── Cálculo de métricas derivadas ────────────────────────────────────────────

def compute_score(
    total_memories: int,
    project_count: int,
    total_relations: int,
    avg_activation: float,
    hot_pct: float,
) -> tuple[float, list[tuple[str, float, float]]]:
    """Devuelve (score_final_0_1, componentes)."""
    components: list[tuple[str, float, float]] = [
        # (nombre, valor_0_1, peso)
        ("Densidad de memorias",       clamp01(total_memories / max(1, project_count * 25)),  0.15),
        ("Conectividad (rels/mem)",    clamp01(total_relations / max(1, total_memories * 1.5)), 0.20),
        ("Activación media (uso real)",clamp01(avg_activation / 0.35),                          0.35),
        ("Memorias calientes (%)",     clamp01(hot_pct / 0.20),                                 0.30),
    ]
    final = sum(v * w for _, v, w in components)
    return final, components


# ── Informe principal ────────────────────────────────────────────────────────

def run_report(project_filter: str | None, as_json: bool) -> dict:
    # ── Conectividad ─────────────────────────────────────────────────────────
    try:
        api_get("/health")
    except Exception as exc:
        print(f"\n  ✗ Stack no accesible en {BASE_URL}: {exc}")
        print("  Levanta el stack con:  make stack-up")
        sys.exit(1)

    # ── Datos globales ────────────────────────────────────────────────────────
    qdrant_stats  = api_get("/stats")
    params = {"project": project_filter} if project_filter else {}
    global_metrics = api_get("/api/graph/metrics", params or None)
    facets         = api_get("/api/graph/facets",  params or None)

    total_memories  = global_metrics.get("memory_count", 0)
    total_relations = global_metrics.get("relation_count", 0)
    active_relations= global_metrics.get("active_relation_count", 0)
    hot_memories    = global_metrics.get("hot_memory_count", 0)
    avg_activation  = global_metrics.get("avg_activation_score", 0.0)
    avg_stability   = global_metrics.get("avg_stability_score", 0.0)
    pinned          = global_metrics.get("pinned_memory_count", 0)
    bridges         = global_metrics.get("bridge_count", 0)

    projects    = facets.get("projects", [])
    hot_details = facets.get("hot_memories", [])
    top_tags    = facets.get("top_tags", [])

    project_count = len(projects) if not project_filter else 1
    hot_pct       = hot_memories / max(1, total_memories)

    # ── Salud biológica ────────────────────────────────────────────────────────
    brain_data: dict = {}
    try:
        brain_data = api_get("/brain/health")
    except Exception:
        pass

    # ── Compute score ─────────────────────────────────────────────────────────
    final_score, components = compute_score(
        total_memories, project_count, total_relations, avg_activation, hot_pct
    )

    # ── Modo JSON ─────────────────────────────────────────────────────────────
    result = {
        "generated_at": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "filter_project": project_filter,
        "totals": {
            "memories": total_memories,
            "relations": total_relations,
            "active_relations": active_relations,
            "hot_memories": hot_memories,
            "bridges": bridges,
            "pinned": pinned,
            "qdrant_vectors": qdrant_stats.get("points_count", 0),
        },
        "averages": {
            "activation_score": round(avg_activation, 4),
            "stability_score": round(avg_stability, 4),
            "hot_pct": round(hot_pct, 4),
        },
        "score": {
            "final": round(final_score, 4),
            "components": [{"name": n, "value": round(v, 4), "weight": w} for n, v, w in components],
        },
        "brain_health": brain_data,
    }

    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result

    # ── Modo legible ────────────────────────────────────────────────────────────
    scope = f" [{project_filter}]" if project_filter else " [global]"
    print(f"\n{'━' * WIDTH}")
    print(f"  🧠  AI Memory Brain — Informe de Efectividad{scope}")
    print(f"  {BASE_URL}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'━' * WIDTH}")

    # ── 1. Estado del cerebro ─────────────────────────────────────────────────
    header("1 · ESTADO DEL CEREBRO")
    row("Proyectos activos",              project_count)
    row("Memorias totales",               total_memories)
    row("Relaciones semánticas",          total_relations)
    row("Relaciones activas",             active_relations, f"{active_relations / max(1, total_relations)*100:.0f}%")
    row("Puentes entre proyectos",        bridges)
    row("Memorias ancladas (pin)",        pinned)
    row("Vectores en Qdrant",             qdrant_stats.get("points_count", "?"))

    # ── 2. ¿Se está usando el MCP? ────────────────────────────────────────────
    header("2 · SEÑALES DE USO (¿SE LLAMA AL MCP?)")
    row("Memorias calientes",  f"{hot_memories} / {total_memories}", f"{hot_pct*100:.1f}% del total")
    print(f"  {'':36}{bar(hot_pct, 0.20)}")
    row("Activación media",    f"{avg_activation:.4f}")
    print(f"  {'':36}{bar(avg_activation, 0.35)}")
    row("Estabilidad media",   f"{avg_stability:.4f}", "Ebbinghaus decay")

    if avg_activation < 0.04:
        print("\n  🔴  Activación muy baja — las memorias no se están buscando.")
        print("      → Invoca search_memory o get_project_context más seguido.")
    elif avg_activation < 0.15:
        print("\n  🟡  Activación moderada — hay uso pero puede mejorar.")
        print("      → Añade get_project_context al inicio de cada sesión.")
    else:
        print("\n  🟢  Activación saludable — el MCP está siendo consultado.")

    # ── 3. Top memorias más accedidas ─────────────────────────────────────────
    header("3 · MEMORIAS MÁS ACTIVAS (VALOR REAL)")
    if hot_details:
        for i, hm in enumerate(hot_details[:7], 1):
            content    = str(hm.get("content", hm.get("summary", "?")))[:65]
            prominence = hm.get("prominence_score", hm.get("activation_score", 0.0))
            proj       = hm.get("project", "?")
            mtype      = hm.get("memory_type", "")
            print(f"  {i}. [{prominence:.2f}] [{proj}] [{mtype}]")
            print(f"     {content}…")
    else:
        print("\n  No hay memorias calientes todavía.")
        print("  → Usa search_memory en sesiones reales para activarlas.")

    # ── 4. Top tags ───────────────────────────────────────────────────────────
    if top_tags:
        print(f"\n  Tags más frecuentes: {', '.join(str(t) for t in top_tags[:10])}")

    # ── 5. Salud biológica ────────────────────────────────────────────────────
    header("4 · SALUD BIOLÓGICA")
    if brain_data:
        connectivity = brain_data.get("connectivity", {})
        cross_score  = connectivity.get("cross_activity_score", 0.0)
        myelinated   = connectivity.get("myelinated_relations", 0)
        sleep_stats  = connectivity.get("sleep_stats", {})
        last_nrem    = sleep_stats.get("last_nrem") or "—  (nunca ejecutado)"
        last_rem     = sleep_stats.get("last_rem")  or "—  (nunca ejecutado)"

        row("Actividad cruzada (multi-proyecto)", f"{cross_score:.4f}")
        row("Relaciones mielinizadas",             myelinated)
        row("Último NREM (consolidación)",         str(last_nrem)[:35])
        row("Último REM (asociación creativa)",    str(last_rem)[:35])

        regions     = brain_data.get("regions", [])
        total_orph  = sum(r.get("orphan_memories", 0) for r in regions)
        total_sch   = sum(r.get("schemas_count", 0) for r in regions)
        kp_list     = [r.get("keyphrases_coverage", 0) for r in regions if r.get("keyphrases_coverage") is not None]
        avg_kp      = sum(kp_list) / len(kp_list) if kp_list else 0.0

        row("Memorias huérfanas (sin sinapsis)",   total_orph,
            "ideal = 0; usa link_memories para conectarlas" if total_orph else "✓ ok")
        row("Schemas abstractos extraídos",        total_sch,
            "patrones de alto nivel detectados")
        row("Cobertura keyphrases",                f"{avg_kp:.0f}%")

        alerts = brain_data.get("alerts", [])
        if alerts:
            print(f"\n  ⚠  Alertas:")
            for a in alerts:
                print(f"     • {a}")
    else:
        print("  (endpoint /brain/health no disponible)")

    # ── 6. Análisis por proyecto ──────────────────────────────────────────────
    if not project_filter and projects:
        header("5 · DESGLOSE POR PROYECTO")
        for proj in projects[:12]:
            proj_name = proj if isinstance(proj, str) else proj.get("name", str(proj))
            try:
                m  = api_get("/api/graph/metrics", {"project": proj_name})
                mc = m.get("memory_count", 0)
                rc = m.get("relation_count", 0)
                hm = m.get("hot_memory_count", 0)
                aa = m.get("avg_activation_score", 0.0)
                print(f"\n  📁 {proj_name}")
                print(f"     Memorias: {mc:4}  Relaciones: {rc:4}  Calientes: {hm:3}  Act: {aa:.3f}  {bar(aa, 0.35, 14)}")
            except Exception:
                print(f"\n  📁 {proj_name}  (error al obtener métricas)")

    # ── 7. Protocolo A/B ──────────────────────────────────────────────────────
    header("6 · PROTOCOLO DE MEDICIÓN A/B")
    print("""
  Para cuantificar el beneficio REAL frente a no usarlo:

  ┌─ CON MEMORIA (sesión instrumentada) ────────────────────┐
  │  Inicio:   get_project_context(<proyecto>)              │
  │  Durante:  search_memory al buscar contexto             │
  │  Final:    record_session_summary con outcome y errores │
  └─────────────────────────────────────────────────────────┘

  ┌─ SIN MEMORIA (sesión control) ──────────────────────────┐
  │  Trabaja sin invocar ninguna tool del MCP               │
  │  Al final: busca con search_memory qué había disponible │
  │  → Eso es lo que el MCP te habría dado                  │
  └─────────────────────────────────────────────────────────┘

  MÉTRICAS OBJETIVAS QUE PUEDES OBSERVAR AHORA:
    • known_errors.occurrence_count > 1  → error repetido sin MCP
    • hot_memories con type=decision     → decisiones consultadas
    • avg_activation_score > 0.20        → cerebro en uso activo
    • Nuevas memorias con novelty < 0.15 → sabías la respuesta""")

    # ── 8. Score final ────────────────────────────────────────────────────────
    header("7 · BRAIN UTILIZATION SCORE")
    print()
    for name, val, weight in components:
        print(f"  {name:<35} {val*100:5.0f}/100  (peso {weight*100:.0f}%)")

    print(f"\n  {'SCORE FINAL':<35} {final_score*100:5.0f}/100")
    print(f"  {'':36}{bar(final_score)}")

    if final_score < 0.20:
        verdict = "🔴 BAJO  — MCP infrautilizado. Empieza usándolo en cada sesión."
    elif final_score < 0.45:
        verdict = "🟡 MEDIO — Uso ocasional. Añade get_project_context al inicio."
    elif final_score < 0.75:
        verdict = "🟢 BUENO — Cerebro activo y siendo consultado regularmente."
    else:
        verdict = "🏆 ÓPTIMO — Máximo aprovechamiento del sistema de memoria."

    print(f"\n  {verdict}\n")

    return result


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="AI Memory Brain — Informe de efectividad")
    parser.add_argument("--project", "-p", metavar="NAME",
                        help="Filtrar por proyecto específico")
    parser.add_argument("--json", action="store_true",
                        help="Salida en JSON puro (para scripts / CI)")
    args = parser.parse_args()

    run_report(project_filter=args.project, as_json=args.json)


if __name__ == "__main__":
    main()
