"""
Exporta resultados a Excel (.xlsx), CSV y JSON.
"""
import os
import json
from datetime import datetime

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def export_data(df, raw_data, output_dir, base_name, fmt):
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    if fmt in ("excel", "all"):
        paths.append(_excel(df, output_dir, base_name))
    if fmt in ("csv", "all"):
        paths.append(_csv(df, output_dir, base_name))
    if fmt in ("json", "all"):
        paths.append(_json(df, output_dir, base_name))
    return paths


def _excel(df, output_dir, base_name):
    path   = os.path.join(output_dir, f"{base_name}.xlsx")
    writer = pd.ExcelWriter(path, engine="openpyxl")

    # Resumen
    _summary(df).to_excel(writer, sheet_name="Resumen", index=False)

    # Todos los datos
    df.to_excel(writer, sheet_name="Todos", index=False)

    # Una hoja por tipo
    for tipo in df["tipo"].unique():
        sub = df[df["tipo"] == tipo].reset_index(drop=True)
        sub.to_excel(writer, sheet_name=tipo[:31], index=False)

    writer.close()
    _style(path)
    return path


def _summary(df):
    rows = [
        {"Métrica": "Fecha", "Valor": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Métrica": "Total registros", "Valor": len(df)},
        {"Métrica": "Fuentes", "Valor": df["fuente"].nunique()},
        {"Métrica": "Páginas scrapeadas", "Valor": df["url_pagina"].nunique()},
        {"Métrica": "", "Valor": ""},
        {"Métrica": "── POR TIPO ──", "Valor": "Cantidad"},
    ]
    for tipo, n in df["tipo"].value_counts().items():
        rows.append({"Métrica": f"  {tipo}", "Valor": n})
    rows.append({"Métrica": "", "Valor": ""})
    rows.append({"Métrica": "── POR FUENTE ──", "Valor": "Registros"})
    for fuente, n in df["fuente"].value_counts().items():
        rows.append({"Métrica": f"  {fuente}", "Valor": n})
    return pd.DataFrame(rows)


def _style(path):
    wb = load_workbook(path)
    HDR_FILL = PatternFill("solid", start_color="1a1a2e")
    HDR_FONT = Font(name="Arial", bold=True, color="00FF88", size=11)
    ALT_FILL = PatternFill("solid", start_color="F0FFF4")
    BORDER   = Border(bottom=Side(style="thin", color="DDDDDD"))
    CENTER   = Alignment(horizontal="center", vertical="center", wrap_text=True)
    LEFT     = Alignment(horizontal="left",   vertical="center", wrap_text=True)

    for ws in wb.worksheets:
        for cell in ws[1]:
            cell.font      = HDR_FONT
            cell.fill      = HDR_FILL
            cell.alignment = CENTER
        for i, row in enumerate(ws.iter_rows(min_row=2), 2):
            for cell in row:
                cell.alignment = LEFT
                cell.border    = BORDER
                if i % 2 == 0:
                    cell.fill = ALT_FILL
        ws.freeze_panes = "A2"
        for col in ws.columns:
            w = max((len(str(c.value)) if c.value else 0) for c in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(w+2, 12), 55)
        ws.row_dimensions[1].height = 22

    wb.save(path)


def _csv(df, output_dir, base_name):
    path = os.path.join(output_dir, f"{base_name}.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _json(df, output_dir, base_name):
    path = os.path.join(output_dir, f"{base_name}.json")
    out  = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "total_records": len(df),
            "fuentes": df["fuente"].unique().tolist(),
        },
        "por_tipo": {
            tipo: df[df["tipo"] == tipo][["fuente","url_pagina","dato","atributo"]].to_dict("records")
            for tipo in df["tipo"].unique()
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return path
