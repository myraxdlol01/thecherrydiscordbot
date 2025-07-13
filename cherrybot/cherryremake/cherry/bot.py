from __future__ import annotations
import asyncio
import os
import random
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
start_time = datetime.utcnow()

user_timezones: dict[int, str] = {}
user_balances: dict[int, int] = {}
user_job_streak: dict[int, int] = {}

STATUS_MESSAGES = [
    lambda: f"watching over {len(bot.guilds)} :3",
    lambda: "listening to /help :D",
    lambda: "playing with batz :o",
]
status_index = 0

def get_balance(user_id: int) -> int:
    return user_balances.get(user_id, 0)

async def update_status():
    global status_index
    while True:
        msg = STATUS_MESSAGES[status_index % len(STATUS_MESSAGES)]()
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=msg))
        status_index += 1
        await asyncio.sleep(5)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(update_status())
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Sync failed: {e}")

@app_commands.command(description="set or view your timezone")
@app_commands.describe(zone="timezone name e.g. Europe/London")
async def timezone(interaction: discord.Interaction, zone: str | None = None):
    if zone:
        try:
            ZoneInfo(zone)
        except Exception:
            await interaction.response.send_message("invalid timezone", ephemeral=True)
            return
        user_timezones[interaction.user.id] = zone
        await interaction.response.send_message(f"timezone set to {zone}", ephemeral=True)
    else:
        zone = user_timezones.get(interaction.user.id)
        if not zone:
            await interaction.response.send_message("no timezone set", ephemeral=True)
            return
        now = datetime.now(ZoneInfo(zone))
        await interaction.response.send_message(now.strftime("%H:%M (%I:%M %p)"), ephemeral=True)

bot.tree.add_command(timezone)

vc_category_name = "auto vc"
join_channel_name = "join to create"

async def ensure_join_channel(guild: discord.Guild):
    category = discord.utils.get(guild.categories, name=vc_category_name)
    if category is None:
        category = await guild.create_category(vc_category_name)
    join = discord.utils.get(category.voice_channels, name=join_channel_name)
    if join is None:
        await category.create_voice_channel(join_channel_name)

@bot.event
async def on_guild_join(guild: discord.Guild):
    await ensure_join_channel(guild)

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if after.channel and after.channel.name == join_channel_name:
        category = after.channel.category or await ensure_join_channel(member.guild)
        new_vc = await category.create_voice_channel(f"{member.name}'s vc")
        await member.move_to(new_vc)

@app_commands.guild_only()
class VCGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="vc", description="manage your temporary voice channel")

    @app_commands.command(description="rename your voice channel")
    async def rename(self, interaction: discord.Interaction, *, name: str):
        if interaction.user.voice and interaction.user.voice.channel:
            await interaction.user.voice.channel.edit(name=name)
            await interaction.response.send_message("renamed", ephemeral=True)
        else:
            await interaction.response.send_message("join a vc first", ephemeral=True)

    @app_commands.command(description="lock/unlock your voice channel")
    async def lock(self, interaction: discord.Interaction, lock: bool):
        if interaction.user.voice and interaction.user.voice.channel:
            overwrites = interaction.user.voice.channel.overwrites_for(interaction.guild.default_role)
            overwrites.connect = not lock
            await interaction.user.voice.channel.set_permissions(interaction.guild.default_role, overwrite=overwrites)
            await interaction.response.send_message("locked" if lock else "unlocked", ephemeral=True)
        else:
            await interaction.response.send_message("join a vc first", ephemeral=True)

bot.tree.add_command(VCGroup())

class EcoGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="eco", description="economy commands")

    @app_commands.command(description="check your balance")
    async def balance(self, interaction: discord.Interaction):
        bal = get_balance(interaction.user.id)
        await interaction.response.send_message(f"you have {bal} cherry-coin(s)", ephemeral=True)

    @app_commands.command(description="work once a day for coins")
    async def work(self, interaction: discord.Interaction):
        bal = get_balance(interaction.user.id)
        bal += random.randint(10, 50)
        user_balances[interaction.user.id] = bal
        await interaction.response.send_message(f"you worked and earned some coins. you now have {bal}", ephemeral=True)

    @app_commands.command(description="gamble your coins")
    async def gamble(self, interaction: discord.Interaction, amount: int):
        bal = get_balance(interaction.user.id)
        if amount <= 0 or amount > bal:
            await interaction.response.send_message("invalid amount", ephemeral=True)
            return
        if random.random() < 0.5:
            bal += amount
            result = "won"
        else:
            bal -= amount
            result = "lost"
        user_balances[interaction.user.id] = bal
        await interaction.response.send_message(f"you {result}! balance: {bal}", ephemeral=True)

bot.tree.add_command(EcoGroup())

@app_commands.command(description="make ascii text")
async def asciify(interaction: discord.Interaction, *, text: str):
    try:
        import pyfiglet
    except ImportError:
        await interaction.response.send_message("pyfiglet not installed", ephemeral=True)
        return
    output = pyfiglet.figlet_format(text)
    await interaction.response.send_message(f"```{output}```", ephemeral=True)

bot.tree.add_command(asciify)

@app_commands.command(description="echo text as the bot")
async def echo(interaction: discord.Interaction, *, text: str):
    await interaction.response.send_message(text)

bot.tree.add_command(echo)

@app_commands.command(description="show bot uptime")
async def uptime(interaction: discord.Interaction):
    delta = datetime.utcnow() - start_time
    minutes, seconds = divmod(int(delta.total_seconds()), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    await interaction.response.send_message(f"up {days}d {hours}h {minutes}m {seconds}s", ephemeral=True)

bot.tree.add_command(uptime)

@bot.command()
async def helptext(ctx: commands.Context):
    lines = [f"/{cmd.name} - {cmd.description}" for cmd in bot.tree.get_commands()]
    await ctx.send("commands:\n" + "\n".join(lines))

extra = app_commands.Group(name="extra", description="extra placeholder commands")
for i in range(1, 81):
    @extra.command(name=f"cmd{i}")
    async def _placeholder(interaction: discord.Interaction, i=i):
        await interaction.response.send_message(f"placeholder command {i}", ephemeral=True)

bot.tree.add_command(extra)

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN not set")
    bot.run(TOKEN)
