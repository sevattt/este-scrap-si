# 🕷️ AutoScraper Discord Bot

Bot de Discord que scrapea URLs automáticamente y te manda los resultados con Excel adjunto.

---

## 🔧 Instalación paso a paso

### 1. Instala dependencias
```bash
pip install -r requirements.txt
```

### 2. Crea el bot en Discord

1. Ve a https://discord.com/developers/applications
2. Clic en **"New Application"** → ponle nombre → **Create**
3. Ve a la sección **"Bot"** (menú izquierdo)
4. Clic en **"Add Bot"** → **"Yes, do it!"**
5. En **"Token"** → clic en **"Reset Token"** → **copia el token**
6. Activa estos **Privileged Gateway Intents**:
   - ✅ MESSAGE CONTENT INTENT
   - ✅ SERVER MEMBERS INTENT
7. Ve a **"OAuth2" → "URL Generator"**
   - Scope: ✅ `bot`
   - Bot Permissions: ✅ `Send Messages`, `Attach Files`, `Read Message History`, `View Channels`
8. Copia la URL generada y ábrela para **invitar el bot a tu servidor**

### 3. Configura el token
```bash
# Copia el archivo de ejemplo
cp .env.example .env

# Abre .env y pega tu token:
# DISCORD_TOKEN=tu_token_aquí
```

### 4. Corre el bot
```bash
python bot.py
```

Verás en consola:
```
✅ Bot conectado como: TuBot#1234
```

---

## 💬 Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| `!scrape <url>` | Scrapea una URL |
| `!scrape <url1> <url2> ...` | Múltiples URLs a la vez |
| `!texto <texto con URLs>` | Detecta URLs en el texto y las scrapea |
| `!config` | Ver configuración actual |
| `!config motor playwright` | Cambiar motor de scraping |
| `!config delay 2000` | Cambiar delay entre requests (ms) |
| `!config tipos titles,prices,emails` | Qué tipos extraer |
| `!config profundidad 2` | Niveles de crawling |
| `!historial` | Ver últimos archivos generados |
| `!estado` | Info del bot (ping, versión) |
| `!ayuda` | Ver todos los comandos |

---

## 📋 Ejemplos de uso en Discord

```
# Scrapear un e-commerce
!scrape https://books.toscrape.com

# Scrapear varias páginas
!scrape https://site1.com https://site2.com/productos https://site3.com

# Pegar texto con URLs mezcladas
!texto Revisa estas páginas: https://example.com/productos
       y también www.otra-tienda.com/ofertas que tienen buenos precios

# Solo extraer precios y títulos
!config tipos titles,prices
!scrape https://tienda.com

# Para páginas con JavaScript (React/Angular)
!config motor playwright
!scrape https://spa-app.com
```

---

## 📦 Qué extrae

| Tipo | Descripción |
|------|-------------|
| `titles` | H1, H2, H3, H4 |
| `prices` | Precios con $, €, £ |
| `links` | Todos los `<a href>` |
| `images` | URLs de imágenes |
| `emails` | Emails encontrados en el HTML |
| `phones` | Teléfonos |
| `tables` | Tablas HTML completas |
| `text` | Párrafos de texto |
| `meta` | Meta tags SEO |

---

## 📁 Archivos generados

Cada scraping genera 3 archivos en `/data/`:
- `scraping_FECHA.xlsx` — Excel con múltiples hojas + resumen
- `scraping_FECHA.csv` — CSV plano
- `scraping_FECHA.json` — JSON estructurado

El bot los adjunta automáticamente en Discord.

---

## 🗂️ Estructura del proyecto

```
discord_scraper_bot/
├── bot.py               ← punto de entrada, corre esto
├── .env.example         → cópialo a .env con tu token
├── requirements.txt
├── config.json          ← se crea automáticamente
├── data/                ← archivos generados
├── bot/
│   ├── client.py        ← configura el cliente Discord
│   └── commands.py      ← todos los comandos (!scrape, !texto, etc.)
└── scraper/
    ├── engine.py        ← motor requests + BeautifulSoup + Playwright
    ├── exporter.py      ← genera Excel/CSV/JSON
    └── config.py        ← gestión de configuración
```

---

## ❓ Solución de problemas

**Error: `DISCORD_TOKEN` no encontrado**
→ Asegúrate de haber creado el archivo `.env` con tu token.

**El bot no responde**
→ Verifica que activaste el **MESSAGE CONTENT INTENT** en el portal de Discord.

**Quiero scrapear páginas con React/Angular**
→ Instala Playwright: `pip install playwright && playwright install chromium`
→ Luego en Discord: `!config motor playwright`

**Los archivos son muy grandes para Discord (>8MB)**
→ El bot los guarda en `/data/` de todas formas. Usa `!historial` para verlos.
