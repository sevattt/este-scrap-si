"""
Todos los comandos del bot de Discord.

Comandos disponibles:
  !scrape <url> [url2] ...     → scrapea una o varias URLs
  !texto <texto con URLs>      → extrae URLs del texto y las scrapea
  !config motor/delay/tipos    → cambia configuración
  !historial                   → muestra los últimos trabajos
  !estado                      → info del bot
  !ayuda                       → este menú
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

# ── Colores embed ─────────────────────────────────────────────────────────────
COLOR_OK    = 0x00ff88
COLOR_WARN  = 0xf59e0b
COLOR_ERR   = 0xef4444
COLOR_INFO  = 0x6366f1
COLOR_DATA  = 0x00ccff

# ── Helper embeds ─────────────────────────────────────────────────────────────
def embed_ok(title, desc=""):
    return discord.Embed(title=f"✅ {title}", description=desc, color=COLOR_OK)

def embed_err(title, desc=""):
    return discord.Embed(title=f"❌ {title}", description=desc, color=COLOR_ERR)

def embed_info(title, desc=""):
    return discord.Embed(title=f"🕷️ {title}", description=desc, color=COLOR_INFO)

def embed_warn(title, desc=""):
    return discord.Embed(title=f"⚠️ {title}", description=desc, color=COLOR_WARN)

def extract_urls(text):
    """Extrae todas las URLs de un texto."""
    pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(pattern, text)
    # También detectar dominios sin http
    bare = re.findall(r'\b(?:www\.)[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?\b', text)
    urls += ["https://" + b for b in bare]
    return list(dict.fromkeys(urls))  # deduplicar preservando orden

# ── Registro de comandos ──────────────────────────────────────────────────────
def register_commands(bot):

    # ── !ayuda ──────────────────────────────────────────────────────────────
    @bot.command(name="ayuda", aliases=["help", "h"])
    async def ayuda(ctx):
        e = discord.Embed(
            title="🕷️ AutoScraper Bot — Comandos",
            description="Bot de scraping automático. Pásame URLs o texto y extraigo todo.",
            color=COLOR_INFO
        )
        e.add_field(name="📌 Scraping", value="""
`!scrape <url>` — Scrapea una URL
`!scrape <url1> <url2> ...` — Múltiples URLs a la vez
`!texto <texto>` — Extrae URLs del texto y las scrapea
""", inline=False)

        e.add_field(name="⚙️ Configuración", value="""
`!config` — Ver configuración actual
`!config motor requests` — Cambiar motor (requests/playwright)
`!config delay 2000` — Delay entre requests en ms
`!config tipos titles,prices,links` — Qué extraer
`!config profundidad 2` — Niveles de crawling
""", inline=False)

        e.add_field(name="📂 Historial", value="""
`!historial` — Últimos 10 trabajos
`!estado` — Info del bot
""", inline=False)

        e.add_field(name="🔧 Tipos disponibles", value=
            "`titles` `prices` `links` `images` `emails` `phones` `tables` `text` `meta`",
            inline=False)

        e.add_field(name="💡 Ejemplos", value="""
```
!scrape https://books.toscrape.com
!scrape https://site1.com https://site2.com https://site3.com
!texto Revisa estas páginas: site1.com y también https://site2.com/productos
!config tipos titles,prices,emails
```""", inline=False)

        e.set_footer(text="AutoScraper Bot v1.0 | Resultados en Excel, CSV y JSON")
        await ctx.send(embed=e)

    # ── !scrape ──────────────────────────────────────────────────────────────
    @bot.command(name="scrape", aliases=["s", "scrapear"])
    async def scrape(ctx, *args):
        if not args:
            await ctx.send(embed=embed_warn(
                "Falta la URL",
                "Uso: `!scrape <url>` o `!scrape <url1> <url2> ...`\n\nEjemplo:\n```!scrape https://books.toscrape.com```"
            ))
            return

        urls = []
        for arg in args:
            url = arg.strip()
            if not url.startswith("http"):
                url = "https://" + url
            urls.append(url)

        await ejecutar_scraping(ctx, urls)

    # ── !texto ───────────────────────────────────────────────────────────────
    @bot.command(name="texto", aliases=["t", "analizar"])
    async def texto(ctx, *, contenido: str):
        urls = extract_urls(contenido)

        if not urls:
            await ctx.send(embed=embed_warn(
                "No encontré URLs en el texto",
                f"El texto que enviaste:\n```{contenido[:200]}```\n\nAsegúrate de incluir URLs con `https://` o `www.`"
            ))
            return

        e = embed_info(
            f"URLs detectadas: {len(urls)}",
            "\n".join(f"• `{u}`" for u in urls[:10]) + ("\n..." if len(urls) > 10 else "")
        )
        await ctx.send(embed=e)
        await ejecutar_scraping(ctx, urls)

    # ── !config ──────────────────────────────────────────────────────────────
    @bot.command(name="config", aliases=["cfg", "configurar"])
    async def config(ctx, clave: str = None, *, valor: str = None):
        cfg = load_config()

        if not clave:
            # Mostrar config actual
            e = discord.Embed(title="⚙️ Configuración actual", color=COLOR_INFO)
            e.add_field(name="Motor",       value=f"`{cfg['engine']}`",                      inline=True)
            e.add_field(name="Delay",       value=f"`{cfg['delay_ms']}ms`",                  inline=True)
            e.add_field(name="Profundidad", value=f"`{cfg['depth']}`",                       inline=True)
            e.add_field(name="Tipos",       value=f"`{', '.join(cfg['extract_types'])}`",    inline=False)
            e.add_field(name="Carpeta",     value=f"`{cfg['output_dir']}`",                  inline=True)
            e.set_footer(text="Usa !config <clave> <valor> para cambiar")
            await ctx.send(embed=e)
            return

        # Cambiar config
        changes = {
            "motor":       ("engine",        lambda v: v if v in ("requests","playwright","scrapy") else None),
            "delay":       ("delay_ms",      lambda v: int(v) if v.isdigit() else None),
            "profundidad": ("depth",         lambda v: int(v) if v.isdigit() else None),
            "tipos":       ("extract_types", lambda v: [t.strip() for t in v.split(",")]),
            "carpeta":     ("output_dir",    lambda v: v),
        }

        if clave.lower() not in changes:
            await ctx.send(embed=embed_warn(
                "Clave inválida",
                f"Claves válidas: `{', '.join(changes.keys())}`"
            ))
            return

        cfg_key, converter = changes[clave.lower()]
        new_val = converter(valor) if valor else None

        if new_val is None:
            await ctx.send(embed=embed_err("Valor inválido", f"El valor `{valor}` no es válido para `{clave}`."))
            return

        cfg[cfg_key] = new_val
        save_config(cfg)
        await ctx.send(embed=embed_ok(
            "Configuración actualizada",
            f"`{clave}` → `{new_val}`"
        ))

    # ── !historial ───────────────────────────────────────────────────────────
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
            name  = os.path.basename(f)
            e.add_field(name=name, value=f"`{size:.1f} KB` — {mtime}", inline=False)

        await ctx.send(embed=e)

    # ── !estado ──────────────────────────────────────────────────────────────
    @bot.command(name="estado", aliases=["status", "info"])
    async def estado(ctx):
        import platform
        cfg = load_config()
        e = discord.Embed(title="🤖 Estado del Bot", color=COLOR_OK)
        e.add_field(name="Bot",       value=f"`{bot.user}`",                          inline=True)
        e.add_field(name="Ping",      value=f"`{round(bot.latency*1000)}ms`",         inline=True)
        e.add_field(name="Servidores",value=f"`{len(bot.guilds)}`",                   inline=True)
        e.add_field(name="Motor",     value=f"`{cfg['engine']}`",                     inline=True)
        e.add_field(name="Python",    value=f"`{platform.python_version()}`",         inline=True)
        e.add_field(name="Plataforma",value=f"`{platform.system()}`",                 inline=True)
        e.set_footer(text="AutoScraper Bot v1.0")
        await ctx.send(embed=e)
      
           # ── !ml ──────────────────────────────────────────────────────────────
    @bot.command(name="ml", aliases=["mercadolibre", "meli"])
    async def mercadolibre(ctx, *, busqueda: str):

        import aiohttp
        import pandas as pd
        from scraper.exporter import export_data
        from urllib.parse import quote

        pais = "MCO"

        msg = await ctx.send(embed=discord.Embed(
            title=f"🛒 Buscando en MercadoLibre: {busqueda}",
            color=0xFFE600
        ))

        try:
            query = quote(busqueda)

            url = f"https://api.mercadolibre.com/sites/{pais}/search?q={query}&limit=50"

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
                "Origin": "https://www.mercadolibre.com.co",
                "Referer": "https://www.mercadolibre.com.co/",
                "Connection": "keep-alive"
            }

            timeout = aiohttp.ClientTimeout(total=20)

            async with aiohttp.ClientSession(
                headers=headers,
                timeout=timeout
            ) as session:

                async with session.get(url, ssl=False) as r: 

    print("STATUS:", r.status)

    text = await r.text()
    print(text[:500])

                    if r.status != 200:
                        text = await r.text()

                        await msg.edit(embed=discord.Embed(
                            title="❌ Error API MercadoLibre",
                            description=f"Status: `{r.status}`\n```{text[:500]}```",
                            color=0xef4444
                        ))
                        return

                    data = await r.json()

            items = data.get("results", [])

            if not items:
                await msg.edit(embed=discord.Embed(
                    description="No se encontraron resultados.",
                    color=0xef4444
                ))
                return

            rows = [{
                "Producto": i.get("title", "")[:100],
                "Precio": f"${i.get('price', 0):,.0f}",
                "Precio_num": i.get("price", 0),
                "Condición": i.get("condition", ""),
                "Link": i.get("permalink", ""),
                "Vendedor": i.get("seller", {}).get("nickname", ""),
                "Envío gratis": "✅" if i.get("shipping", {}).get("free_shipping") else "❌",
            } for i in items]

            df = pd.DataFrame(rows)

            precio_min = df["Precio_num"].min()
            precio_max = df["Precio_num"].max()
            precio_avg = df["Precio_num"].mean()

            e = discord.Embed(
                title=f"✅ MercadoLibre — {busqueda}",
                color=0xFFE600
            )

            e.add_field(name="Resultados", value=f"`{len(items)}`", inline=True)
            e.add_field(name="Precio más bajo", value=f"`${precio_min:,.0f}`", inline=True)
            e.add_field(name="Precio más alto", value=f"`${precio_max:,.0f}`", inline=True)
            e.add_field(name="Precio promedio", value=f"`${precio_avg:,.0f}`", inline=True)

            top3 = df.nsmallest(3, "Precio_num")[["Producto", "Precio"]]

            preview = "\n".join(
                f"• {r['Producto'][:50]} — **{r['Precio']}**"
                for _, r in top3.iterrows()
            )

            e.add_field(
                name="🏆 Top 3 más baratos",
                value=preview,
                inline=False
            )

            await msg.edit(embed=e)

        except Exception as ex:

            await msg.edit(embed=discord.Embed(
                title="❌ Error MercadoLibre",
                description=f"```{str(ex)[:800]}```",
                color=0xef4444
            ))

            print(ex)
