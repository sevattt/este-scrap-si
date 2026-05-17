"""
Configura el cliente de Discord con todos los comandos.
"""
import discord
from discord.ext import commands

def create_bot():
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(
        command_prefix="!",
        intents=intents,
        help_command=None,  # usamos el nuestro
    )

    @bot.event
    async def on_ready():
        print(f"✅ Bot conectado como: {bot.user} (ID: {bot.user.id})")
        print(f"   Servidores: {len(bot.guilds)}")
        print(f"   Prefijo: !")
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="!ayuda | AutoScraper 🕷️"
            )
        )

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(embed=discord.Embed(
                description=f"❓ Comando no encontrado. Usa `!ayuda` para ver todos los comandos.",
                color=0xf59e0b
            ))
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=discord.Embed(
                description=f"⚠️ Falta un argumento. Usa `!ayuda` para ver el uso correcto.",
                color=0xf59e0b
            ))
        else:
            await ctx.send(embed=discord.Embed(
                description=f"❌ Error: `{error}`",
                color=0xef4444
            ))

    # Registrar comandos
    from bot.commands import register_commands
    register_commands(bot)

    return bot
