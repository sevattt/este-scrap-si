"""
Exporta resultados a Excel (.xlsx), CSV y JSON.
Excel mejorado con hoja de Productos limpia ordenada por precio.
"""
import os
import re
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

    # ── Hoja Productos (la más importante para clientes) ──
    productos_df = _build_productos(df)
    if not productos_df.empty:
        productos_df.to_excel(writer, sheet_name="🛍️ Productos", index=False)

    # ── Hoja Resumen ──
    _summary(df, productos_df).to_excel(writer, sheet_name="📊 Resumen", index=False)

    # ── Hoja Todos los datos ──
    df.to_excel(writer, sheet_name="📋 Todos", index=False)

    # ── Una hoja por tipo ──
    for tipo in df["tipo"].unique():
        sub = df[df["tipo"] == tipo].reset_index(drop=True)
        sub.to_excel(writer, sheet_name=tipo[:31], index=False)

    writer.close()
    _style(path, tiene_productos=not productos_df.empty)
    return path


def _build_productos(df):
    """Construye hoja de productos combinando títulos y precios."""
    titulos  = df[df["tipo"] == "titulo"]["dato"].tolist()
    precios  = df[df["tipo"].isin(["precio","precio_raw"])]["dato"].tolist()
    links    = df[df["tipo"] == "link"]["dato"].tolist()

    if not titulos and not precios:
        return pd.DataFrame()

    # Limpiar y convertir precios a número
    precios_limpios = []
    for p in precios:
        num = re.sub(r"[^\d.,]", "", p)
        num = num.replace(",", ".")
        try:
            # Manejar formato 1.299.99 → tomar último segmento
            partes = num.split(".")
            if len(partes) > 2:
                num = "".join(partes[:-1]) + "." + partes[-1]
            val = float(num)
            if val > 0:
                precios_limpios.append({"precio_texto": p.strip(), "precio_num": val})
        except Exception:
            pass

    # Armar filas
    rows = []
    max_len = max(len(titulos), len(precios_limpios))
    for i in range(max_len):
        titulo = titulos[i] if i < len(titulos) else "—"
        precio_info = precios_limpios[i] if i < len(precios_limpios) else None
        link = links[i] if i < len(links) else "—"
        rows.append({
            "Producto":      titulo[:120],
            "Precio":        precio_info["precio_texto"] if precio_info else "—",
            "Precio (num)":  precio_info["precio_num"]  if precio_info else None,
            "Link":          link,
            "Fuente":        df["fuente"].iloc[0] if not df.empty else "—",
            "Fecha":         datetime.now().strftime("%Y-%m-%d"),
        })

    productos_df = pd.DataFrame(rows)

    # Ordenar por precio de menor a mayor
    if "Precio (num)" in productos_df.columns:
        productos_df = productos_df.sort_values("Precio (num)", na_position="last")
        productos_df = productos_df.reset_index(drop=True)

    return productos_df


def _summary(df, productos_df):
    rows = [
        {"Métrica": "Fecha de extracción", "Valor": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Métrica": "Total registros",     "Valor": len(df)},
        {"Métrica": "Fuente",              "Valor": df["fuente"].iloc[0] if not df.empty else "—"},
        {"Métrica": "Páginas scrapeadas",  "Valor": df["url_pagina"].nunique()},
        {"Métrica": "",                    "Valor": ""},
    ]

    # Estadísticas de precios
    if not productos_df.empty and "Precio (num)" in productos_df.columns:
        nums = productos_df["Precio (num)"].dropna()
        if not nums.empty:
            rows += [
                {"Métrica": "── PRECIOS ──",      "Valor": ""},
                {"Métrica": "Precio más bajo",     "Valor": f"${nums.min():,.2f}"},
                {"Métrica": "Precio más alto",     "Valor": f"${nums.max():,.2f}"},
                {"Métrica": "Precio promedio",     "Valor": f"${nums.mean():,.2f}"},
                {"Métrica": "Total productos",     "Valor": len(nums)},
                {"Métrica": "",                    "Valor": ""},
            ]
            # Top 3 más baratos
            rows.append({"Métrica": "── TOP 3 MÁS BARATOS ──", "Valor": "Precio"})
            for _, row in productos_df.dropna(subset=["Precio (num)"]).head(3).iterrows():
                rows.append({"Métrica": f"  {row['Producto'][:50]}", "Valor": row["Precio"]})

    rows += [
        {"Métrica": "", "Valor": ""},
        {"Métrica": "── POR TIPO ──", "Valor": "Cantidad"},
    ]
    for tipo, n in df["tipo"].value_counts().items():
        rows.append({"Métrica": f"  {tipo}", "Valor": n})

    return pd.DataFrame(rows)


def _style(path, tiene_productos=False):
    wb = load_workbook(path)

    HDR_FILL  = PatternFill("solid", start_color="1a1a2e")
    HDR_FONT  = Font(name="Arial", bold=True, color="00FF88", size=11)
    ALT_FILL  = PatternFill("solid", start_color="F0FFF4")
    PROD_FILL = PatternFill("solid", start_color="E8F5E9")  # verde claro productos
    BORDER    = Border(bottom=Side(style="thin", color="DDDDDD"))
    CENTER    = Alignment(horizontal="center", vertical="center", wrap_text=True)
    LEFT      = Alignment(horizontal="left",   vertical="center", wrap_text=True)

    # Color especial para hoja de productos
    PROD_HDR  = PatternFill("solid", start_color="0d6e3f")
    PROD_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=12)

    for ws in wb.worksheets:
        is_prod = ws.title == "🛍️ Productos"

        for cell in ws[1]:
            cell.font      = PROD_FONT if is_prod else HDR_FONT
            cell.fill      = PROD_HDR  if is_prod else HDR_FILL
            cell.alignment = CENTER

        for i, row in enumerate(ws.iter_rows(min_row=2), 2):
            for cell in row:
                cell.alignment = LEFT
                cell.border    = BORDER
                if i % 2 == 0:
                    cell.fill = PROD_FILL if is_prod else ALT_FILL

        ws.freeze_panes = "A2"

        for col in ws.columns:
            w = max((len(str(c.value)) if c.value else 0) for c in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(w+2, 12), 60)

        ws.row_dimensions[1].height = 24

        # Resaltar fila más barata en hoja productos
        if is_prod and ws.max_row > 2:
            for cell in ws[2]:
                cell.fill = PatternFill("solid", start_color="C8E6C9")
                cell.font = Font(name="Arial", bold=True, color="1B5E20")

    wb.save(path)


def _csv(df, output_dir, base_name):
    path = os.path.join(output_dir, f"{base_name}.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _json(df, output_dir, base_name):
    path = os.path.join(output_dir, f"{base_name}.json")
    out  = {
        "meta": {
            "generated_at":  datetime.now().isoformat(),
            "total_records": len(df),
            "fuentes":       df["fuente"].unique().tolist(),
        },
        "por_tipo": {
            tipo: df[df["tipo"] == tipo][["fuente","url_pagina","dato","atributo"]].to_dict("records")
            for tipo in df["tipo"].unique()
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return path
