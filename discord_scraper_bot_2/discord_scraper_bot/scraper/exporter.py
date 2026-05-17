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

    productos_df = _build_productos(df)
    if not productos_df.empty:
        productos_df.to_excel(writer, sheet_name="Productos", index=False)

    _summary(df, productos_df).to_excel(writer, sheet_name="Resumen", index=False)
    df.to_excel(writer, sheet_name="Todos", index=False)

    for tipo in df["tipo"].unique():
        sub = df[df["tipo"] == tipo].reset_index(drop=True)
        sub.to_excel(writer, sheet_name=tipo[:31], index=False)

    writer.close()
    _style(path, tiene_productos=not productos_df.empty)
    return path


def _parse_precio(texto):
    """Convierte texto de precio a float. Retorna None si no es un precio válido."""
    t = texto.strip()

    # Debe tener símbolo de moneda o texto de moneda
    tiene_simbolo = any(s in t for s in ["$","€","£","¥","USD","EUR","COP","MXN"])
    if not tiene_simbolo:
        return None

    # Extraer solo dígitos, puntos y comas
    solo_nums = re.sub(r"[^\d.,]", "", t)
    if not solo_nums:
        return None

    # Limpiar formato:
    # $1,299.99 → 1299.99
    # $1.299,99 → 1299.99
    # $1299     → 1299.0
    try:
        # Detectar si usa coma como decimal (europeo) o punto
        if re.search(r",\d{2}$", solo_nums):
            # formato europeo: 1.299,99
            solo_nums = solo_nums.replace(".", "").replace(",", ".")
        elif re.search(r"\.\d{2}$", solo_nums):
            # formato americano: 1,299.99
            solo_nums = solo_nums.replace(",", "")
        else:
            solo_nums = solo_nums.replace(",", "").replace(".", "")

        val = float(solo_nums)

        # Filtrar precios irreales (muy altos o muy bajos)
        if val <= 0 or val > 500000:
            return None

        return val
    except Exception:
        return None


def _build_productos(df):
    """Construye hoja de productos combinando títulos y precios."""
    titulos = df[df["tipo"] == "titulo"]["dato"].tolist()
    
    # Solo usar precios con símbolo, no precio_raw basura
    precios_df = df[df["tipo"] == "precio"]["dato"].tolist()
    
    # Parsear precios válidos
    precios_limpios = []
    for p in precios_df:
        val = _parse_precio(p)
        if val is not None:
            precios_limpios.append({"precio_texto": p.strip(), "precio_num": val})

    links = df[df["tipo"] == "link"]["dato"].tolist()
    # Filtrar links de productos (no navegación)
    links_productos = [l for l in links if any(x in l for x in ["/dp/", "/gp/", "/product", "item", "p=", "prod"])]
    if not links_productos:
        links_productos = links

    if not titulos and not precios_limpios:
        return pd.DataFrame()

    rows = []
    max_len = max(len(titulos), len(precios_limpios))

    for i in range(min(max_len, 200)):  # máx 200 productos
        titulo = titulos[i] if i < len(titulos) else "—"
        precio_info = precios_limpios[i] if i < len(precios_limpios) else None
        link = links_productos[i] if i < len(links_productos) else "—"

        rows.append({
            "N°":            i + 1,
            "Producto":      titulo[:120],
            "Precio":        precio_info["precio_texto"] if precio_info else "—",
            "Precio (USD)":  precio_info["precio_num"]  if precio_info else None,
            "Link":          link,
            "Fuente":        df["fuente"].iloc[0] if not df.empty else "—",
            "Fecha":         datetime.now().strftime("%Y-%m-%d"),
        })

    productos_df = pd.DataFrame(rows)

    # Ordenar por precio de menor a mayor
    productos_df = productos_df.sort_values("Precio (USD)", na_position="last")
    productos_df = productos_df.reset_index(drop=True)
    productos_df["N°"] = range(1, len(productos_df) + 1)

    return productos_df


def _summary(df, productos_df):
    rows = [
        {"Métrica": "Fecha de extracción", "Valor": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Métrica": "Total registros",     "Valor": len(df)},
        {"Métrica": "Fuente",              "Valor": df["fuente"].iloc[0] if not df.empty else "—"},
        {"Métrica": "Páginas scrapeadas",  "Valor": df["url_pagina"].nunique()},
        {"Métrica": "",                    "Valor": ""},
    ]

    if not productos_df.empty and "Precio (USD)" in productos_df.columns:
        nums = productos_df["Precio (USD)"].dropna()
        if not nums.empty:
            rows += [
                {"Métrica": "── ANÁLISIS DE PRECIOS ──", "Valor": ""},
                {"Métrica": "Precio más bajo",     "Valor": f"${nums.min():,.2f}"},
                {"Métrica": "Precio más alto",     "Valor": f"${nums.max():,.2f}"},
                {"Métrica": "Precio promedio",     "Valor": f"${nums.mean():,.2f}"},
                {"Métrica": "Precio mediana",      "Valor": f"${nums.median():,.2f}"},
                {"Métrica": "Total productos",     "Valor": len(nums)},
                {"Métrica": "",                    "Valor": ""},
                {"Métrica": "── TOP 3 MÁS BARATOS ──", "Valor": "Precio"},
            ]
            for _, row in productos_df.dropna(subset=["Precio (USD)"]).head(3).iterrows():
                rows.append({
                    "Métrica": f"  {row['Producto'][:60]}",
                    "Valor":   row["Precio"]
                })
            rows += [
                {"Métrica": "",                     "Valor": ""},
                {"Métrica": "── TOP 3 MÁS CAROS ──", "Valor": "Precio"},
            ]
            for _, row in productos_df.dropna(subset=["Precio (USD)"]).tail(3).iterrows():
                rows.append({
                    "Métrica": f"  {row['Producto'][:60]}",
                    "Valor":   row["Precio"]
                })

    rows += [
        {"Métrica": "", "Valor": ""},
        {"Métrica": "── POR TIPO ──", "Valor": "Cantidad"},
    ]
    for tipo, n in df["tipo"].value_counts().items():
        rows.append({"Métrica": f"  {tipo}", "Valor": n})

    return pd.DataFrame(rows)


def _style(path, tiene_productos=False):
    wb = load_workbook(path)

    for ws in wb.worksheets:
        is_prod    = ws.title == "Productos"
        is_resumen = ws.title == "Resumen"

        # Header
        hdr_fill = PatternFill("solid", start_color="0d6e3f" if is_prod else "1a1a2e")
        hdr_font = Font(name="Arial", bold=True,
                        color="FFFFFF" if is_prod else "00FF88", size=11)
        for cell in ws[1]:
            cell.font      = hdr_font
            cell.fill      = hdr_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Filas de datos
        alt_fill  = PatternFill("solid", start_color="E8F5E9" if is_prod else "F0FFF4")
        border    = Border(bottom=Side(style="thin", color="DDDDDD"))
        for i, row in enumerate(ws.iter_rows(min_row=2), 2):
            for cell in row:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                cell.border    = BORDER = border
                if i % 2 == 0:
                    cell.fill = alt_fill

        # Resaltar fila más barata en Productos
        if is_prod and ws.max_row > 2:
            for cell in ws[2]:
                cell.fill = PatternFill("solid", start_color="C8E6C9")
                cell.font = Font(name="Arial", bold=True, color="1B5E20")

        ws.freeze_panes = "A2"
        ws.row_dimensions[1].height = 24

        # Ancho columnas
        for col in ws.columns:
            w = max((len(str(c.value)) if c.value else 0) for c in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(w+2, 10), 60)

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
