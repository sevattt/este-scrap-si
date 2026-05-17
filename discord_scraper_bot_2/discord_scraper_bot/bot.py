#!/usr/bin/env python3
"""
AutoScraper Discord Bot
Uso: python bot.py
"""
import os
import sys
from dotenv import load_dotenv
import discord

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("\n❌ ERROR: No se encontró DISCORD_TOKEN en el archivo .env")
    print("   1. Copia .env.example → .env")
    print("   2. Pega tu token de Discord en DISCORD_TOKEN=\n")
    sys.exit(1)

from bot.client import create_bot

bot = create_bot()

if __name__ == "__main__":
    print("🕷️  AutoScraper Bot arrancando...")
    bot.run(TOKEN)
