"""
Todos los comandos del bot de Discord.
"""
import discord
from discord.ext import commands
import asyncio
import re
import os
from datetime import datetime

from scraper.engine import run_scraping_async
from scraper.config import load_config, save_config

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

COLOR_OK   = 0x00ff88
COLOR_WARN = 0xf59e0b
COLOR_ERR  = 0xef4444
COLOR_INFO = 0x6366f1
COLOR_DATA = 0x00ccff
COLOR_ML   = 0xFFE600

def embed_ok(title, desc=""):
    return discord.Embed(title=f"✅ {title}", description=desc, color=COLOR_OK)

def embed_err(title, desc=""):
    return discord.Embed(title=f"❌ {title}", description=desc, color=COLOR_ERR)

def embed_info(title, desc=""):
    return discord.Embed(title=f"🕷️ {title}", description=desc, color=COLOR_INFO)

def embed_warn(title, desc=""):
    return discord.Embed(title=f"⚠️ {title}", description=desc, color=COLOR_WARN)

def extract_urls(text):
    pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(pattern, text)
    bare = re.findall(r'\b(?:www\.)[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?\b', text)
    urls += ["https://" + b for b in bare]
    return list(dict.fromkeys(urls))


def register_commands(bot):

    @bot.command(name="ayuda", aliases=["help", "h"])
    async def ayuda(ctx):
        e = discord.Embed(
            title="🕷️ AutoScraper Bot — Comandos",
            description="Bot de scraping automático. Pásame URLs o texto y extraigo todo.",
            color=COLOR_INFO
        )
        e.add_field(name="📌 Scraping", value="`!scrape <url>` — Scrapea una URL\n`!scrape <url1> <url2>` — Múltiples URLs\n`!texto <texto>` — Extrae URLs del texto", inline=False)
        e.add_field(name="🛒 MercadoLibre", value="`!ml <busqueda>` — Busca en MercadoLibre Colombia\nEjemplo: `!ml laptops`, `!ml pesas de gym`", inline=False)
        e.add_field(name="⚙️ Config", value="`!config` — Ver config\n`!config motor requests` — Cambiar motor\n`!config delay 2000` — Delay\n`!config tipos titles,prices,links`", inline=False)
        e.add_field(name="📂 Otros", value="`!historial` — Últimos archivos\n`!estado` — Info del bot", inline=False)
        e.add_field(name="🔧 Tipos", value="`titles` `prices` `links` `images` `emails` `phones` `tables` `text` `meta`", inline=False)
        e.set_footer(text="AutoScraper Bot v1.0")
        await ctx.send(embed=e)

    @bot.command(name="scrape", aliases=["s", "scrapear"])
    async def scrape(ctx, *args):
        if not args:
            await ctx.send(embed=embed_warn("Falta la URL", "Uso: `!scrape <url>`\n\nEjemplo:\n```!scrape https://books.toscrape.com```"))
            return
        urls = []
        for arg in args:
            url = arg.strip()
            if not url.startswith("http"):
                url = "https://" + url
            urls.append(url)
        await ejecutar_scraping(ctx, urls)

    @bot.command(name="texto", aliases=["t", "analizar"])
    async def texto(ctx, *, contenido: str):
        urls = extract_urls(contenido)
        if not urls:
            await ctx.send(embed=embed_warn("No encontré URLs", f"```{contenido[:200]}```\nIncluye URLs con `https://` o `www.`"))
            return
        await ctx.send(embed=embed_info(f"URLs detectadas: {len(urls)}", "\n".join(f"• `{u}`" for u in urls[:10])))
        await ejecutar_scraping(ctx, urls)

    @bot.command(name="ml", aliases=["mercadolibre", "meli"])
    async def mercadolibre(ctx, *, busqueda: str):
        import aiohttp
        import pandas as pd
        from scraper.exporter import export_data

        msg = await ctx.send(embed=discord.Embed(
            title=f"🛒 Buscando en MercadoLibre: {busqueda}",
            description="⏳ Un momento...",
            color=COLOR_ML
        ))
        try:
            url = f"https://api.mercadolibre.com/sites/MCO/search?q={busqueda}&limit=50"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as r:
                    data = await r.json()

            items = data.get("results", [])
            if not items:
                await msg.edit(embed=discord.Embed(description="No se encontraron resultados.", color=COLOR_ERR))
                return

            rows = [{
                "Producto":     i.get("title", "")[:100],
                "Precio":       f"${i.get('price', 0):,.0f}",
                "Precio_num":   i.get("price", 0),
                "Condicion":    i.get("condition", ""),
                "Link":         i.get("permalink", ""),
                "Vendedor":     i.get("seller", {}).get("nickname", ""),
                "Envio_gratis": "Si" if i.get("shipping", {}).get("free_shipping") else "No",
            } for i in items]

            df = pd.DataFrame(rows)
            df_sorted = df.sort_values("Precio_num").reset_index(drop=True)

            df_export = df_sorted.copy()
            df_export["tipo"]       = "producto"
            df_export["fuente"]     = "mercadolibre.com.co"
            df_export["url_pagina"] = url
            df_export["dato"]       = df_export["Producto"]
            df_export["atributo"]   = df_export["Precio"]
            df_export["fecha"]      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
            files = export_data(df_export, [], DATA_DIR, f"meli_{ts}", "all")

            precio_min = df["Precio_num"].min()
            precio_max = df["Precio_num"].max()
            precio_avg = df["Precio_num"].mean()

            e = discord.Embed(title=f"✅ MercadoLibre — {busqueda}", color=COLOR_ML)
            e.add_field(name="Resultados",      value=f"`{len(items)}`",       inline=True)
            e.add_field(name="Precio más bajo", value=f"`${precio_min:,.0f}`", inline=True)
            e.add_field(name="Precio más alto", value=f"`${precio_max:,.0f}`", inline=True)
            e.add_field(name="Precio promedio", value=f"`${precio_avg:,.0f}`", inline=True)

            top3 = df_sorted.head(3)
            preview = "\n".join(
                f"• {r['Producto'][:50]} — **{r['Precio']}** {'✅' if r['Envio_gratis']=='Si' else ''}"
                for _, r in top3.iterrows()
            )
            e.add_field(name="🏆 Top 3 más baratos", value=preview, inline=False)
            e.set_footer(text="Ordenado de menor a mayor precio")
            await msg.edit(embed=e)

            discord_files = [discord.File(f) for f in files if os.path.exists(f) and os.path.getsize(f) < 8*1024*1024]
            if discord_files:
                await ctx.send(content=f"📎 **Archivos generados ({len(discord_files)}):**", files=discord_files)

        except Exception as ex:
            await msg.edit(embed=discord.Embed(description=f"❌ Error: `{ex}`", color=COLOR_ERR))

    @bot.command(name="buscar", aliases=["b", "octo"])
    async def buscar(ctx, *, consulta: str):
        from groq import Groq as GroqClient
        import json

        client = GroqClient(api_key=os.environ.get("GROQ_API_KEY"))
        msg = await ctx.send(embed=discord.Embed(
            title="🐙 Octo pensando...",
            description=f"*{consulta}*",
            color=0x7c3aed
        ))
        try:
            response = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{
                    "role": "system",
                    "content": """Eres Octo, asistente de scraping. Analiza la consulta y responde SOLO con JSON asi:
{"accion": "amazon" o "mercadolibre" o "scrape" o "desconocido", "query": "termino limpio", "explicacion": "que vas a hacer"}"""
                }, {
                    "role": "user",
                    "content": consulta
                }],
                max_tokens=200
            )

            raw = response.choices[0].message.content.strip()
            import re as re3
            match = re3.search(r'\{.*\}', raw, re3.DOTALL)
            data = json.loads(match.group()) if match else {}

            accion      = data.get("accion", "desconocido")
            query       = data.get("query", consulta)
            explicacion = data.get("explicacion", "Procesando...")

            await msg.edit(embed=discord.Embed(
                title=f"🐙 Octo — {explicacion}",
                description=f"Buscando: `{query}`",
                color=0x7c3aed
            ))

            if accion == "amazon":
                await amazon(ctx, busqueda=query)
            elif accion == "mercadolibre":
                await mercadolibre(ctx, busqueda=query)
            elif accion == "scrape":
                urls = extract_urls(consulta)
                if urls:
                    await ejecutar_scraping(ctx, urls)
                else:
                    await ctx.send(embed=embed_warn("No encontre URLs", "Incluye una URL en tu consulta."))
            else:
                await msg.edit(embed=discord.Embed(
                    description="No entendi. Prueba:\n`!buscar laptops en amazon`\n`!buscar pesas en mercadolibre`",
                    color=COLOR_WARN
                ))

        except Exception as ex:
            await msg.edit(embed=discord.Embed(description=f"Error: `{ex}`", color=COLOR_ERR))


    @bot.command(name="config", aliases=["cfg", "configurar"])
    async def config(ctx, clave: str = None, *, valor: str = None):
        cfg = load_config()
        if not clave:
            e = discord.Embed(title="⚙️ Configuración actual", color=COLOR_INFO)
            e.add_field(name="Motor",       value=f"`{cfg['engine']}`",                   inline=True)
            e.add_field(name="Delay",       value=f"`{cfg['delay_ms']}ms`",               inline=True)
            e.add_field(name="Profundidad", value=f"`{cfg['depth']}`",                    inline=True)
            e.add_field(name="Tipos",       value=f"`{', '.join(cfg['extract_types'])}`", inline=False)
            e.add_field(name="Carpeta",     value=f"`{cfg['output_dir']}`",               inline=True)
            e.set_footer(text="Usa !config <clave> <valor> para cambiar")
            await ctx.send(embed=e)
            return

        changes = {
            "motor":       ("engine",        lambda v: v if v in ("requests","playwright","scrapy") else None),
            "delay":       ("delay_ms",      lambda v: int(v) if v.isdigit() else None),
            "profundidad": ("depth",         lambda v: int(v) if v.isdigit() else None),
            "tipos":       ("extract_types", lambda v: [t.strip() for t in v.split(",")]),
            "carpeta":     ("output_dir",    lambda v: v),
        }
        if clave.lower() not in changes:
            await ctx.send(embed=embed_warn("Clave inválida", f"Claves válidas: `{', '.join(changes.keys())}`"))
            return

        cfg_key, converter = changes[clave.lower()]
        new_val = converter(valor) if valor else None
        if new_val is None:
            await ctx.send(embed=embed_err("Valor inválido", f"`{valor}` no es válido para `{clave}`."))
            return

        cfg[cfg_key] = new_val
        save_config(cfg)
        await ctx.send(embed=embed_ok("Configuración actualizada", f"`{clave}` → `{new_val}`"))

    @bot.command(name="historial", aliases=["history", "jobs"])
    async def historial(ctx):
        import glob
        files = sorted(glob.glob(os.path.join(DATA_DIR, "*.xlsx")), key=os.path.getmtime, reverse=True)[:10]
        if not files:
            await ctx.send(embed=embed_warn("Sin historial", "Aún no se han generado archivos."))
            return
        e = discord.Embed(title="📂 Últimos trabajos", color=COLOR_DATA)
        for f in files:
            size  = os.path.getsize(f) / 1024
            mtime = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
            e.add_field(name=os.path.basename(f), value=f"`{size:.1f} KB` — {mtime}", inline=False)
        await ctx.send(embed=e)

    @bot.command(name="estado", aliases=["status", "info"])
    async def estado(ctx):
        import platform
        cfg = load_config()
        e = discord.Embed(title="🤖 Estado del Bot", color=COLOR_OK)
        e.add_field(name="Bot",        value=f"`{bot.user}`",                  inline=True)
        e.add_field(name="Ping",       value=f"`{round(bot.latency*1000)}ms`", inline=True)
        e.add_field(name="Servidores", value=f"`{len(bot.guilds)}`",            inline=True)
        e.add_field(name="Motor",      value=f"`{cfg['engine']}`",              inline=True)
        e.add_field(name="Python",     value=f"`{platform.python_version()}`",  inline=True)
        e.add_field(name="Plataforma", value=f"`{platform.system()}`",          inline=True)
        e.set_footer(text="AutoScraper Bot v1.0")
        await ctx.send(embed=e)

    @bot.command(name="amazon", aliases=["amz"])
    async def amazon(ctx, *, busqueda: str):
        import aiohttp
        import pandas as pd
        import re as re2
        from scraper.exporter import export_data

        api_key = os.environ.get("SCRAPERAPI_KEY", "")
        msg = await ctx.send(embed=discord.Embed(
            title=f"🛒 Buscando en Amazon: {busqueda}",
            description="⏳ Un momento...",
            color=0xFF9900
        ))
        try:
            url = f"https://api.scraperapi.com/structured/amazon/search?api_key={api_key}&query={busqueda}&country=us"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as r:
                    data = await r.json()

            items = data.get("results", data.get("organic_results", []))
            if not items:
                await msg.edit(embed=discord.Embed(description="No se encontraron resultados.", color=COLOR_ERR))
                return

            rows = []
            for i in items:
                precio_txt = i.get("price", i.get("price_string", "—"))
                precio_num = 0
                try:
                    nums = re2.sub(r"[^\d.]", "", str(precio_txt))
                    precio_num = float(nums) if nums else 0
                except Exception:
                    pass
                rows.append({
                    "Producto":   i.get("name", i.get("title", ""))[:100],
                    "Precio":     precio_txt,
                    "Precio_num": precio_num,
                    "Rating":     i.get("stars", i.get("rating", "—")),
                    "Reviews":    i.get("total_reviews", i.get("reviews", "—")),
                    "Link":       i.get("url", i.get("link", "—")),
                    "ASIN":       i.get("asin", "—"),
                })

            df = pd.DataFrame(rows)
            df_sorted = df[df["Precio_num"] > 0].sort_values("Precio_num").reset_index(drop=True)
            if df_sorted.empty:
                df_sorted = df

            df_export = df_sorted.copy()
            df_export["tipo"]       = "producto"
            df_export["fuente"]     = "amazon.com"
            df_export["url_pagina"] = url
            df_export["dato"]       = df_export["Producto"]
            df_export["atributo"]   = df_export["Precio"]
            df_export["fecha"]      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
            files = export_data(df_export, [], DATA_DIR, f"amazon_{ts}", "all")

            nums_validos = df_sorted[df_sorted["Precio_num"] > 0]["Precio_num"]
            e = discord.Embed(title=f"✅ Amazon — {busqueda}", color=0xFF9900)
            e.add_field(name="Resultados",      value=f"`{len(items)}`", inline=True)
            e.add_field(name="Precio mas bajo", value=f"`${nums_validos.min():,.2f}`" if not nums_validos.empty else "`—`", inline=True)
            e.add_field(name="Precio mas alto", value=f"`${nums_validos.max():,.2f}`" if not nums_validos.empty else "`—`", inline=True)
            e.add_field(name="Precio promedio", value=f"`${nums_validos.mean():,.2f}`" if not nums_validos.empty else "`—`", inline=True)

            top3 = df_sorted.head(3)
            preview = "\n".join(
                f"• {r['Producto'][:50]} — **{r['Precio']}** ⭐{r['Rating']}"
                for _, r in top3.iterrows()
            )
            e.add_field(name="Top 3 mas baratos", value=preview or "—", inline=False)
            e.set_footer(text="Datos via ScraperAPI | Ordenado de menor a mayor precio")
            await msg.edit(embed=e)

            discord_files = [discord.File(f) for f in files if os.path.exists(f) and os.path.getsize(f) < 8*1024*1024]
            if discord_files:
                await ctx.send(content=f"📎 **Archivos generados ({len(discord_files)}):**", files=discord_files)

        except Exception as ex:
            await msg.edit(embed=discord.Embed(description=f"❌ Error: `{ex}`", color=COLOR_ERR))


    @bot.command(name="basico", aliases=["basic"])
    async def basico(ctx, *args):
        if not args:
            await ctx.send(embed=embed_warn("Falta la URL", "Uso: `!basico <url>`\nPlan básico: 1 sitio, títulos + precios + links."))
            return
        cfg = load_config()
        cfg["extract_types"] = ["titles", "prices", "links"]
        cfg["depth"] = 1
        url = args[0] if args[0].startswith("http") else "https://" + args[0]
        await ctx.send(embed=discord.Embed(description="📦 **Plan Básico** — títulos, precios y links", color=0x00cc66))
        await ejecutar_scraping(ctx, [url])

    @bot.command(name="pro")
    async def pro(ctx, *args):
        if not args:
            await ctx.send(embed=embed_warn("Falta la URL", "Uso: `!pro <url1> <url2>`\nPlan Pro: hasta 3 sitios, extracción completa."))
            return
        cfg = load_config()
        cfg["extract_types"] = ["titles", "prices", "links", "emails", "phones", "tables", "text"]
        cfg["depth"] = 2
        urls = [u if u.startswith("http") else "https://" + u for u in args[:3]]
        await ctx.send(embed=discord.Embed(description="⚡ **Plan Pro** — extracción completa", color=0x6366f1))
        await ejecutar_scraping(ctx, urls)

    @bot.command(name="premium")
    async def premium(ctx, *args):
        if not args:
            await ctx.send(embed=embed_warn("Falta la URL", "Uso: `!premium <url1> <url2> ...`\nPlan Premium: hasta 5 sitios, máxima profundidad."))
            return
        cfg = load_config()
        cfg["extract_types"] = ["titles", "prices", "links", "emails", "phones", "tables", "text", "images", "meta"]
        cfg["depth"] = 3
        urls = [u if u.startswith("http") else "https://" + u for u in args[:5]]
        await ctx.send(embed=discord.Embed(description="👑 **Plan Premium** — extracción total", color=0xf59e0b))
        await ejecutar_scraping(ctx, urls)



# ── Función central de scraping ───────────────────────────────────────────────
async def ejecutar_scraping(ctx, urls):
    cfg = load_config()

    e_start = discord.Embed(
        title="🕷️ Scraping iniciado",
        description="\n".join(f"• `{u}`" for u in urls[:5]) + (f"\n... y {len(urls)-5} más" if len(urls) > 5 else ""),
        color=COLOR_INFO
    )
    e_start.add_field(name="Motor",  value=f"`{cfg['engine']}`",                   inline=True)
    e_start.add_field(name="Tipos",  value=f"`{', '.join(cfg['extract_types'])}`", inline=True)
    e_start.add_field(name="Status", value="⏳ Procesando...",                      inline=False)
    e_start.set_footer(text="Te avisaré cuando termine.")
    msg = await ctx.send(embed=e_start)

    start_time = datetime.now()

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: run_scraping_async(urls=urls, cfg=cfg)
        )
        elapsed = (datetime.now() - start_time).seconds

        if result["error"]:
            await msg.edit(embed=embed_err("Error en el scraping", f"{result['error'][:800]}"))
            return

        df     = result["df"]
        files  = result["files"]
        n_rows = len(df) if df is not None else 0

        e_done = discord.Embed(title="✅ Scraping completado", color=COLOR_OK, timestamp=datetime.utcnow())
        e_done.add_field(name="📊 Registros", value=f"`{n_rows}`",    inline=True)
        e_done.add_field(name="🌐 Páginas",   value=f"`{len(urls)}`", inline=True)
        e_done.add_field(name="⏱️ Tiempo",    value=f"`{elapsed}s`",  inline=True)

        if df is not None and not df.empty and "tipo" in df.columns:
            resumen  = df["tipo"].value_counts().head(6)
            tipo_txt = "\n".join(f"`{t}`: **{c}**" for t, c in resumen.items())
            e_done.add_field(name="📋 Por tipo", value=tipo_txt, inline=False)

        if df is not None and not df.empty:
            preview = df.head(5)[["tipo", "dato"]].to_string(index=False)
            e_done.add_field(name="👀 Preview", value=f"```{preview[:800]}```", inline=False)

        e_done.set_footer(text=f"AutoScraper Bot • {', '.join([os.path.basename(f) for f in files])}")
        await msg.edit(embed=e_done)

        discord_files = [discord.File(fp) for fp in files if os.path.exists(fp) and os.path.getsize(fp) < 8*1024*1024]
        if discord_files:
            await ctx.send(content=f"📎 **Archivos generados ({len(discord_files)}):**", files=discord_files)

        await ctx.send(embed=discord.Embed(
            description=f"🎉 {ctx.author.mention} ¡Listo! **{n_rows} registros** de **{len(urls)} página(s)**.",
            color=COLOR_OK
        ))

    except Exception as ex:
        await msg.edit(embed=embed_err("Error inesperado", f"```{str(ex)[:400]}```\n\nUsa `!ayuda` para ver el uso correcto."))
        raise ex
