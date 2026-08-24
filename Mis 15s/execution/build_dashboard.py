#!/usr/bin/env python3
"""
build_dashboard.py

Lee el CSV mas reciente exportado desde Meta Ads Manager (carpeta Informes-de-Meta-Ads/),
lo valida, lo enriquece con la etapa de funnel (config/campaign-stage-map.json) y escribe
site/data.json, que es lo unico que el dashboard (site/index.html) consume en el navegador.

No hace ningun preagregado por campana/conjunto/anuncio: escribe una fila "plana" por cada
fila valida del CSV (nivel anuncio x dia), y toda la agregacion (por rango de fechas, por
campana, etc.) la hace el dashboard en el navegador con JS. Esto evita tener que decidir de
antemano que agrupaciones necesita el usuario, y hace que el filtro de fechas sea instantaneo.

Uso:
    python3 build_dashboard.py [--csv-dir DIR] [--out site/data.json] [--config config/campaign-stage-map.json]

Por defecto toma el CSV mas reciente (por fecha de modificacion) dentro de --csv-dir.
"""

import argparse
import csv as csv_module
import json
import math
import os
import re
import sys
from datetime import datetime, date

MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

EXPECTED_COLUMNS = [
    "Nombre de la campaña", "Nombre del conjunto de anuncios", "Nombre del anuncio",
    "Día", "Estado de la entrega", "Nivel de la entrega", "Tipo de resultado",
    "Resultados", "Costo por resultado", "Tasa de Conversión a WhatsApp",
    "Conversaciones con mensajes iniciadas", "Nuevos contactos de mensajes",
    "Visitas al perfil de Instagram", "Importe gastado (COP)", "Alcance", "Impresiones",
    "Frecuencia", "Clics en el enlace", "CTR único (todos)",
    "CPC (costo por clic en el enlace)", "CPM (costo por mil impresiones)",
    "CTR (todos)", "Seguimientos de Instagram", "Interacciones",
    "Costo por conversación con mensajes iniciada", "Inicio del informe",
    "Fin del informe", "Resultados (iniciales)",
]

# columnas de texto (agrupadores / metadatos) -> nombre interno
TEXT_COLS = {
    "Nombre de la campaña": "campaign",
    "Nombre del conjunto de anuncios": "adset",
    "Nombre del anuncio": "ad",
    "Estado de la entrega": "delivery_status",
    "Nivel de la entrega": "delivery_level",
    "Tipo de resultado": "result_type",
}

# columnas numericas -> nombre interno
NUMERIC_COLS = {
    "Resultados": "results",
    "Costo por resultado": "cost_per_result_raw",
    "Tasa de Conversión a WhatsApp": "whatsapp_conv_rate_raw",
    "Conversaciones con mensajes iniciadas": "conversations",
    "Nuevos contactos de mensajes": "new_contacts",
    "Visitas al perfil de Instagram": "profile_visits",
    "Importe gastado (COP)": "spend",
    "Alcance": "reach",
    "Impresiones": "impressions",
    "Frecuencia": "frequency_raw",
    "Clics en el enlace": "link_clicks",
    "CTR único (todos)": "ctr_unique_raw",
    "CPC (costo por clic en el enlace)": "cpc_raw",
    "CPM (costo por mil impresiones)": "cpm_raw",
    "CTR (todos)": "ctr_all_raw",
    "Seguimientos de Instagram": "ig_follows",
    "Interacciones": "interactions",
    "Costo por conversación con mensajes iniciada": "cost_per_conversation_raw",
    "Resultados (iniciales)": "initial_results_raw",
}

SUM_FIELDS = [
    "results", "conversations", "new_contacts", "profile_visits", "spend",
    "reach", "impressions", "link_clicks", "ig_follows", "interactions",
]


def fecha_es(d: date) -> str:
    return f"{d.day} de {MESES_ES[d.month - 1]}"


def find_latest_csv(csv_dir: str) -> str:
    candidates = []
    for root, _dirs, files in os.walk(csv_dir):
        for f in files:
            if f.lower().endswith(".csv"):
                full = os.path.join(root, f)
                candidates.append((os.path.getmtime(full), full))
    if not candidates:
        raise FileNotFoundError(f"No se encontro ningun .csv dentro de {csv_dir}")
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]


def load_stage_map(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_stage(campaign_name: str, stage_map: dict, unmapped_seen: set, warnings: list):
    for rule in stage_map.get("rules", []):
        if rule["contains"].lower() in campaign_name.lower():
            return rule["stage"], True
    default = stage_map.get("default", {"stage": "Conversion", "confirmed": False})
    if campaign_name not in unmapped_seen:
        unmapped_seen.add(campaign_name)
        msg = default.get("warningTemplate", "Campaña \"{campaign}\" sin etapa confirmada.").format(campaign=campaign_name)
        warnings.append({"type": "stage_unconfirmed", "severity": "warn", "message": msg, "scope": {"campaign": campaign_name}})
    return default.get("stage", "Conversion"), False


def parse_number(raw: str):
    """Devuelve (valor_o_None, es_vacio_normal, es_roto)."""
    if raw is None:
        return None, True, False
    s = raw.strip()
    if s == "":
        return None, True, False
    # Meta a veces usa separador de miles con punto y decimales con coma en export regional;
    # en este export confirmado usa punto decimal simple, pero toleramos coma decimal por si acaso.
    s_norm = s.replace(",", "") if s.count(",") == 1 and s.count(".") <= 1 and "." in s else s
    try:
        val = float(s_norm)
    except ValueError:
        return None, False, True
    if not math.isfinite(val):
        return None, False, True
    return val, False, False


def parse_date(raw: str):
    s = (raw or "").strip()
    if s == "":
        return None, True
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            d = datetime.strptime(s, fmt).date()
            if d.year < 2015 or d.year > date.today().year + 1:
                return None, False
            return d, True
        except ValueError:
            continue
    return None, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv-dir", default=os.path.join(os.path.dirname(__file__), "..", "Informes-de-Meta-Ads"))
    ap.add_argument("--csv-file", default=None, help="Forzar un archivo CSV especifico en vez de detectar el mas reciente")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "site", "data.json"))
    ap.add_argument("--config", default=os.path.join(os.path.dirname(__file__), "..", "config", "campaign-stage-map.json"))
    args = ap.parse_args()

    warnings = []
    unmapped_seen = set()

    try:
        csv_path = args.csv_file or find_latest_csv(os.path.abspath(args.csv_dir))
    except FileNotFoundError as e:
        out = {
            "meta": {"generated_at": datetime.now().isoformat(), "source_file": None, "parse_failed": True},
            "warnings": [{"type": "no_file", "severity": "error", "message": str(e), "scope": {}}],
            "stage_map": {}, "rows": [],
        }
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    stage_map = load_stage_map(args.config)

    try:
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv_module.Sniffer().sniff(sample, delimiters=",;")
            except csv_module.Error:
                dialect = csv_module.excel
            reader = csv_module.reader(f, dialect)
            rows_raw = list(reader)
    except Exception as e:
        out = {
            "meta": {"generated_at": datetime.now().isoformat(), "source_file": os.path.basename(csv_path), "parse_failed": True},
            "warnings": [{"type": "parse_failed", "severity": "error", "message": f"El archivo {os.path.basename(csv_path)} no se pudo leer/parsear: {e}", "scope": {}}],
            "stage_map": stage_map, "rows": [],
        }
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if not rows_raw:
        print("ERROR: CSV vacio", file=sys.stderr)
        sys.exit(1)

    header = [h.strip() for h in rows_raw[0]]
    missing_cols = [c for c in EXPECTED_COLUMNS if c not in header]
    for c in missing_cols:
        warnings.append({
            "type": "missing_column", "severity": "error",
            "message": f"La columna esperada \"{c}\" no aparece en el CSV subido — la estructura del export cambió.",
            "scope": {"column": c},
        })

    col_idx = {name: header.index(name) for name in header if name in EXPECTED_COLUMNS}

    def get(row, col_name):
        idx = col_idx.get(col_name)
        if idx is None or idx >= len(row):
            return ""
        return row[idx]

    data_rows = rows_raw[1:]

    # --- fila de resumen (fila 2 del archivo = primera fila de datos, sin nombre de campana) ---
    cross_check_raw = None
    body_rows = []
    for r in data_rows:
        if len(r) < len(header) - 3:  # tolera filas cortas al final
            continue
        campaign_val = get(r, "Nombre de la campaña").strip()
        if campaign_val == "" and cross_check_raw is None:
            cross_check_raw = r
            continue
        body_rows.append(r)

    out_rows = []
    for r in body_rows:
        campaign = get(r, "Nombre de la campaña").strip()
        adset = get(r, "Nombre del conjunto de anuncios").strip()
        ad = get(r, "Nombre del anuncio").strip()

        if not campaign or not adset or not ad:
            warnings.append({
                "type": "missing_grouping", "severity": "warn",
                "message": f"Fila con agrupador vacío (campaña/conjunto/anuncio) — se excluyó del cálculo.",
                "scope": {"campaign": campaign, "adset": adset, "ad": ad},
            })
            continue

        d, date_ok = parse_date(get(r, "Día"))
        if not date_ok:
            warnings.append({
                "type": "invalid_date", "severity": "error",
                "message": f"Fecha inválida o fuera de rango lógico en \"{ad}\" ({campaign}).",
                "scope": {"campaign": campaign, "adset": adset, "ad": ad},
            })
            continue

        stage, confirmed = resolve_stage(campaign, stage_map, unmapped_seen, warnings)

        row_out = {
            "date": d.isoformat(),
            "campaign": campaign,
            "adset": adset,
            "ad": ad,
            "delivery_status": get(r, "Estado de la entrega").strip() or None,
            "result_type": get(r, "Tipo de resultado").strip() or None,
            "stage": stage,
            "stage_confirmed": confirmed,
        }

        for col_name, key in NUMERIC_COLS.items():
            raw = get(r, col_name)
            val, is_empty, is_broken = parse_number(raw)
            row_out[key] = val
            if is_broken:
                fecha_txt = fecha_es(d)
                warnings.append({
                    "type": "invalid_number", "severity": "error",
                    "message": f"\"{col_name}\" sin datos válidos en {ad} del {fecha_txt}.",
                    "scope": {"campaign": campaign, "adset": adset, "ad": ad, "date": d.isoformat(), "column": col_name},
                })

        out_rows.append(row_out)

    # --- cross-check opcional contra la fila resumen del CSV ---
    cross_check = None
    if cross_check_raw is not None:
        computed = {f: 0.0 for f in SUM_FIELDS}
        for row in out_rows:
            for f in SUM_FIELDS:
                v = row.get(f)
                if v is not None:
                    computed[f] += v
        reported = {}
        for col_name, key in NUMERIC_COLS.items():
            if key.replace("_raw", "") in SUM_FIELDS or key in SUM_FIELDS:
                base_key = key.replace("_raw", "")
                if base_key in SUM_FIELDS:
                    val, _, _ = parse_number(get(cross_check_raw, col_name))
                    reported[base_key] = val
        cross_check = {"reported_by_meta": reported, "computed_from_rows": computed}

    if not out_rows:
        warnings.append({
            "type": "no_usable_rows", "severity": "error",
            "message": "No quedó ninguna fila utilizable después de validar el CSV.",
            "scope": {},
        })

    dates = [row["date"] for row in out_rows]
    meta = {
        "generated_at": datetime.now().isoformat(),
        "source_file": os.path.basename(csv_path),
        "parse_failed": False,
        "date_range": {"min": min(dates) if dates else None, "max": max(dates) if dates else None},
        "row_count": len(out_rows),
    }

    out = {
        "meta": meta,
        "warnings": warnings,
        "stage_map": stage_map,
        "cross_check": cross_check,
        "rows": out_rows,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    n_err = sum(1 for w in warnings if w["severity"] == "error")
    n_warn = sum(1 for w in warnings if w["severity"] == "warn")
    print(f"OK: {len(out_rows)} filas válidas escritas en {args.out}")
    print(f"    {n_err} errores, {n_warn} advertencias")
    if cross_check:
        for f in SUM_FIELDS:
            rep = cross_check["reported_by_meta"].get(f)
            comp = cross_check["computed_from_rows"].get(f)
            if rep is not None and comp is not None:
                diff_pct = abs(rep - comp) / rep * 100 if rep else 0
                flag = "OK" if diff_pct < 1 else "DIFF"
                print(f"    cross-check {f}: reportado={rep:.2f} calculado={comp:.2f} ({flag}, {diff_pct:.2f}%)")


if __name__ == "__main__":
    main()
