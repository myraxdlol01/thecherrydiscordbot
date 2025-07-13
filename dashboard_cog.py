import discord
from discord.ext import commands
import sqlite3
from datetime import datetime

class DashboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'dashboard/dashboard.db'
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure required tables exist"""
        with sqlite3.connect(self.db_path) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                welcome_channel TEXT,
                welcome_message TEXT,
                leveling_enabled INTEGER DEFAULT 1,
                xp_rate INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            db.execute('''CREATE TABLE IF NOT EXISTS command_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guild_settings (guild_id)
            )''')
            db.commit()

    def get_guild_settings(self, guild_id: int):
        """Get settings for a guild"""
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            result = db.execute(
                'SELECT * FROM guild_settings WHERE guild_id = ?',
                (guild_id,)
            ).fetchone()
            
            if not result:
                # Initialize default settings
                db.execute(
                    'INSERT INTO guild_settings (guild_id, welcome_message) VALUES (?, ?)',
                    (guild_id, "Welcome {user} to {server}!")
                )
                db.commit()
                result = db.execute(
                    'SELECT * FROM guild_settings WHERE guild_id = ?',
                    (guild_id,)
                ).fetchone()
            
            return dict(result)

    def update_guild_settings(self, guild_id: int, **settings):
        """Update settings for a guild"""
        valid_keys = {'welcome_channel', 'welcome_message', 'leveling_enabled', 'xp_rate'}
        update_keys = [k for k in settings.keys() if k in valid_keys]
        
        if not update_keys:
            return False
        
        query = 'UPDATE guild_settings SET ' + ', '.join(f'{k} = ?' for k in update_keys)
        query += ' WHERE guild_id = ?'
        
        values = [settings[k] for k in update_keys] + [guild_id]
        
        with sqlite3.connect(self.db_path) as db:
            db.execute(query, values)
            db.commit()
            return True

    def log_command(self, ctx):
        """Log command usage"""
        if not ctx.guild:
            return
        
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                'INSERT INTO command_logs (guild_id, user_id, command) VALUES (?, ?, ?)',
                (ctx.guild.id, ctx.author.id, ctx.command.qualified_name)
            )
            db.commit()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle member join with welcome message"""
        if not member.guild:
            return
            
        settings = self.get_guild_settings(member.guild.id)
        if not settings.get('welcome_channel'):
            return
            
        channel = member.guild.get_channel(int(settings['welcome_channel']))
        if not channel:
            return
            
        message = settings['welcome_message'].replace('{user}', member.mention).replace('{server}', member.guild.name)
        await channel.send(message)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        """Log completed commands"""
        self.log_command(ctx)

async def setup(bot):
    await bot.add_cog(DashboardCog(bot)) 