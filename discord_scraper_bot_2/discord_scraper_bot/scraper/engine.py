"""
version v4 corregida
Motor de scraping para el bot de Discord.
Versión mejorada con: sesión persistente, headers completos,
reintentos automáticos y debug detallado.
"""
import re
import time
import random
import os
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import pandas as pd

from scraper.exporter import export_data
from scraper.config import ensure_output_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("scraper")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

def _make_session(ua, proxy=None):
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1.5, status_forcelist=[429,500,502,503,504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-419,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "DNT": "1",
        "Cache-Control": "max-age=0",
    })
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
    return session

def run_scraping_async(urls, cfg):
    debug_lines = []
    def dlog(msg):
        log.info(msg)
        debug_lines.append(msg)

    try:
        output_dir = ensure_output_dir(cfg.get("output_dir", "data"))
        engine     = cfg.get("engine", "requests")
        depth      = cfg.get("depth", 1)
        delay      = cfg.get("delay_ms", 1200) / 1000
        proxy      = cfg.get("proxy")
        ua         = random.choice(USER_AGENTS)
        types      = cfg.get("extract_types", ["titles","links","prices","emails","phones","tables","text","meta"])

        dlog(f"Iniciando | Motor: {engine} | URLs: {len(urls)} | Tipos: {types}")

        all_data = []
        visited  = set()
        session  = _make_session(ua, proxy)

        for i, url in enumerate(urls, 1):
            dlog(f"[{i}/{len(urls)}] Scrapeando: {url}")
            _crawl(url, depth, 1, engine, types, delay, proxy, ua, visited, all_data, session, dlog)
            dlog(f"  Items acumulados: {len(all_data)}")

        if not all_data:
            err = (
                "No se extrajeron datos.\n\n"
                "**Posibles causas:**\n"
                "• La página bloquea bots → prueba `!config motor playwright`\n"
                "• La página usa React/Angular → necesita Playwright\n"
                "• URL incorrecta\n\n"
                "**Debug:**\n```\n" + "\n".join(debug_lines[-10:]) + "\n```"
            )
            return {"df": None, "files": [], "error": err, "debug": debug_lines}

        df = pd.DataFrame(all_data)
        df["fecha"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df = df.drop_duplicates(subset=["tipo","dato"]).reset_index(drop=True)
        dlog(f"Total registros unicos: {len(df)}")

        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        files = export_data(df, all_data, output_dir, f"scraping_{ts}", "all")
        return {"df": df, "files": files, "error": None, "debug": debug_lines}

    except Exception as e:
        log.exception("Error inesperado")
        return {"df": None, "files": [], "error": str(e), "debug": debug_lines}

def _crawl(url, max_depth, cur_depth, engine, types, delay, proxy, ua, visited, all_data, session, dlog):
    if url in visited or cur_depth > max_depth:
        return
    visited.add(url)
    html, status, err_msg = _fetch(url, engine, ua, proxy, session)
    if not html:
        dlog(f"  Sin respuesta: {err_msg}")
        return
    dlog(f"  HTTP {status} | Parseando...")
    soup  = BeautifulSoup(html, "html.parser")
    items = _extract(soup, url, types)
    all_data.extend(items)
    dlog(f"  {len(items)} items extraidos")
    time.sleep(delay + random.uniform(0.2, delay * 0.3))
    if cur_depth < max_depth:
        for link in _internal_links(soup, url)[:15]:
            _crawl(link, max_depth, cur_depth+1, engine, types, delay, proxy, ua, visited, all_data, session, dlog)

def _fetch(url, engine, ua, proxy, session):
    if engine == "playwright":
        return _fetch_playwright(url, proxy)
    return _fetch_requests(url, session)

def _fetch_requests(url, session):
    try:
        session.headers.update({"Referer": "https://www.google.com/"})
        r = session.get(url, timeout=20, allow_redirects=True)
        r.raise_for_status()
        try:
            text = r.content.decode(r.encoding or "utf-8", errors="replace") if r.encoding else r.text
        except Exception:
            text = r.text
        return text, r.status_code, None
    except requests.exceptions.HTTPError as e:
        return None, getattr(e.response, "status_code", 0), f"HTTP Error: {e}"
    except requests.exceptions.ConnectionError as e:
        return None, 0, f"Conexion fallida: {e}"
    except requests.exceptions.Timeout:
        return None, 0, "Timeout (>20s)"
    except Exception as e:
        return None, 0, str(e)

def _fetch_playwright(url, proxy=None):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            opts = {"proxy": {"server": proxy}} if proxy else {}
            browser = p.chromium.launch(headless=True, **opts)
            ctx  = browser.new_context(user_agent=random.choice(USER_AGENTS), locale="es-419")
            page = ctx.new_page()
            resp = page.goto(url, timeout=25000, wait_until="networkidle")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            time.sleep(1)
            html   = page.content()
            status = resp.status if resp else 0
            browser.close()
            return html, status, None
    except ImportError:
        return None, 0, "Playwright no instalado. Corre: pip install playwright && playwright install chromium"
    except Exception as e:
        return None, 0, f"Playwright error: {e}"

def _extract(soup, url, types):
    domain = urlparse(url).netloc
    items  = []

    def add(tipo, dato, atributo=""):
        dato = str(dato).strip()
        if dato and len(dato) > 1:
            items.append({"tipo": tipo, "fuente": domain, "url_pagina": url,
                          "dato": dato[:500], "atributo": str(atributo)[:100]})

    if "titles" in types:
        for tag in soup.find_all(["h1","h2","h3","h4","h5"]):
            add("titulo", tag.get_text(separator=" ", strip=True), tag.name)

    if "text" in types:
        for p in soup.find_all("p"):
            t = p.get_text(separator=" ", strip=True)
            if len(t) > 40:
                add("texto", t[:500])

    if "links" in types:
        seen = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            if href.startswith("http") and href not in seen:
                seen.add(href)
                add("link", href, a.get_text(strip=True)[:60])

    if "images" in types:
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if src:
                add("imagen", urljoin(url, src), img.get("alt",""))

    if "emails" in types:
        for e in set(re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", soup.get_text())):
            if not e.endswith((".png",".jpg",".gif",".svg")):
                add("email", e)

    if "phones" in types:
        seen_ph = set()
        for ph in re.findall(r"(?:\+?[\d\s\-\(\)\.]{7,18})", soup.get_text()):
            digits = re.sub(r"\D","",ph)
            if 7 <= len(digits) <= 15 and digits not in seen_ph:
                seen_ph.add(digits)
                add("telefono", ph.strip())

    if "prices" in types:
        # Amazon fix: une precio partido (37. + 99 en elementos separados)
        wholes = soup.find_all(class_=re.compile(r"a-price-whole"))
        fracs  = soup.find_all(class_=re.compile(r"a-price-fraction"))
        seen_amazon = set()
        for i, whole in enumerate(wholes):
            w = re.sub(r"\D", "", whole.get_text(strip=True))
            f = re.sub(r"\D", "", fracs[i].get_text(strip=True)) if i < len(fracs) else "00"
            if w and w not in seen_amazon:
                seen_amazon.add(w)
                add("precio", f"${w}.{f}", "amazon-price")
        # Precios normales por clase CSS
        for el in soup.find_all(class_=re.compile(r"(?<!whole)(?<!fraction)(?<!symbol)price|precio|cost|amount|valor|monto", re.I)):
            t = el.get_text(strip=True)
            if re.search(r"\d", t):
                match = re.search(r"[\$€£¥]\s?[\d,]+\.?\d{0,2}", t)
                if match:
                    add("precio", match.group().strip(), (el.get("class") or [""])[0])
        # Patrón en texto
        for m in re.compile(r"[\$€£¥₩]\s?\d[\d.,]*|\d[\d.,]*\s?(?:USD|EUR|COP|MXN)").finditer(soup.get_text()):
            add("precio_raw", m.group().strip())

    if "tables" in types:
        for i, table in enumerate(soup.find_all("table")):
            rows = [" | ".join(td.get_text(separator=" ", strip=True) for td in tr.find_all(["td","th"]))
                    for tr in table.find_all("tr")]
            rows = [r for r in rows if r.strip()]
            if rows:
                add("tabla", "\n".join(rows[:25]), f"tabla_{i+1}")

    if "meta" in types:
        for meta in soup.find_all("meta"):
            name = meta.get("name") or meta.get("property","")
            content = meta.get("content","")
            if name and content and len(content) > 3:
                add("meta", content[:200], name)

    return items

def _internal_links(soup, base_url):
    domain = urlparse(base_url).netloc
    links  = []
    skip   = (".pdf",".jpg",".png",".zip",".mp4",".svg",".gif")
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        p    = urlparse(href)
        if p.netloc == domain and href not in links and p.scheme in ("http","https") and not href.endswith(skip):
            links.append(href)
    return links
        
