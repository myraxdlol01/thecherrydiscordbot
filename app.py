from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
import os
from dotenv import load_dotenv
import sqlite3
from datetime import datetime
import json

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Discord OAuth2 Config
app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")
app.config["DISCORD_BOT_TOKEN"] = os.getenv("DISCORD_TOKEN")

# Required OAuth2 Scopes
OAUTH2_SCOPES = [
    "identify",           # Get user info
    "guilds",            # Get user's guilds
    "guilds.members.read",# Read guild members
    "email",             # Get user's email
]

discord = DiscordOAuth2Session(app)

def get_db():
    db = sqlite3.connect('dashboard.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

@app.route("/")
def index():
    if not discord.authorized:
        return render_template(
            "login.html",
            client_id=app.config["DISCORD_CLIENT_ID"],
            redirect_uri=app.config["DISCORD_REDIRECT_URI"]
        )
    
    try:
        user = discord.fetch_user()
        guilds = discord.fetch_guilds()
        
        # Filter guilds where user has manage server permission
        managed_guilds = [g for g in guilds if (g.permissions & 0x20) == 0x20]
        
        return render_template(
            "dashboard_home.html",
            user=user,
            guilds=managed_guilds
        )
    except Exception as e:
        app.logger.error(f"Failed to fetch user data: {str(e)}")
        discord.revoke()
        return redirect(url_for("login"))

@app.route("/login")
def login():
    return discord.create_session(scope=OAUTH2_SCOPES)

@app.route("/callback")
def callback():
    try:
        discord.callback()
        user = discord.fetch_user()
        
        # Store user in database
        db = get_db()
        db.execute(
            'INSERT OR REPLACE INTO users (id, username, email, avatar) VALUES (?, ?, ?, ?)',
            (user.id, user.name, user.email, user.avatar_url)
        )
        db.commit()
        
        return redirect(url_for("index"))
    except Exception as e:
        app.logger.error(f"OAuth callback error: {str(e)}")
        return redirect(url_for("login"))

@app.route("/logout")
def logout():
    discord.revoke()
    return redirect(url_for("index"))

@app.route("/guild/<int:guild_id>")
@requires_authorization
def guild_dashboard(guild_id):
    user = discord.fetch_user()
    guild = discord.fetch_guild(guild_id)
    
    if not guild:
        return "Guild not found", 404
    
    # Get guild settings from database
    db = get_db()
    settings = db.execute(
        'SELECT * FROM guild_settings WHERE guild_id = ?',
        (guild_id,)
    ).fetchone()
    
    if not settings:
        # Initialize default settings
        db.execute(
            'INSERT INTO guild_settings (guild_id, welcome_channel, welcome_message, leveling_enabled, xp_rate) VALUES (?, NULL, ?, 1, 1)',
            (guild_id, "Welcome {user} to {server}!")
        )
        db.commit()
        settings = db.execute(
            'SELECT * FROM guild_settings WHERE guild_id = ?',
            (guild_id,)
        ).fetchone()
    
    return render_template(
        "guild_dashboard.html",
        user=user,
        guild=guild,
        settings=settings
    )

@app.route("/api/guild/<int:guild_id>/settings", methods=["GET", "POST"])
@requires_authorization
def guild_settings(guild_id):
    if request.method == "GET":
        db = get_db()
        settings = db.execute(
            'SELECT * FROM guild_settings WHERE guild_id = ?',
            (guild_id,)
        ).fetchone()
        return jsonify(dict(settings))
    
    elif request.method == "POST":
        data = request.json
        db = get_db()
        db.execute(
            '''UPDATE guild_settings 
               SET welcome_channel = ?,
                   welcome_message = ?,
                   leveling_enabled = ?,
                   xp_rate = ?,
                   music_volume = ?,
                   music_dj_role = ?,
                   music_channel = ?,
                   raid_protection_enabled = ?,
                   raid_join_threshold = ?,
                   raid_join_window = ?,
                   nuke_protection_enabled = ?,
                   nuke_action_threshold = ?,
                   nuke_action_window = ?,
                   audit_log_channel = ?,
                   role_xp_multipliers = ?,
                   custom_prefix = ?,
                   automod_rules = ?
               WHERE guild_id = ?''',
            (
                data.get('welcome_channel'),
                data.get('welcome_message'),
                data.get('leveling_enabled', 1),
                data.get('xp_rate', 1.0),
                data.get('music_volume', 100),
                data.get('music_dj_role'),
                data.get('music_channel'),
                data.get('raid_protection_enabled', 1),
                data.get('raid_join_threshold', 6),
                data.get('raid_join_window', 10),
                data.get('nuke_protection_enabled', 1),
                data.get('nuke_action_threshold', 3),
                data.get('nuke_action_window', 30),
                data.get('audit_log_channel'),
                json.dumps(data.get('role_xp_multipliers', {})),
                data.get('custom_prefix', '!'),
                json.dumps(data.get('automod_rules', [])),
                guild_id
            )
        )
        db.commit()
        return jsonify({"status": "success"})

@app.route("/api/guild/<int:guild_id>/level-roles", methods=["GET", "POST", "DELETE"])
@requires_authorization
def level_roles(guild_id):
    db = get_db()
    
    if request.method == "GET":
        roles = db.execute(
            'SELECT * FROM level_roles WHERE guild_id = ?',
            (guild_id,)
        ).fetchall()
        return jsonify([dict(r) for r in roles])
    
    elif request.method == "POST":
        data = request.json
        db.execute(
            'INSERT OR REPLACE INTO level_roles (guild_id, role_id, level_requirement) VALUES (?, ?, ?)',
            (guild_id, data['role_id'], data['level_requirement'])
        )
        db.commit()
        return jsonify({"status": "success"})
    
    elif request.method == "DELETE":
        data = request.json
        db.execute(
            'DELETE FROM level_roles WHERE guild_id = ? AND role_id = ?',
            (guild_id, data['role_id'])
        )
        db.commit()
        return jsonify({"status": "success"})

@app.route("/api/guild/<int:guild_id>/automod", methods=["GET", "POST"])
@requires_authorization
def automod_rules(guild_id):
    db = get_db()
    
    if request.method == "GET":
        settings = db.execute(
            'SELECT automod_rules FROM guild_settings WHERE guild_id = ?',
            (guild_id,)
        ).fetchone()
        return jsonify(json.loads(settings['automod_rules']))
    
    elif request.method == "POST":
        data = request.json
        db.execute(
            'UPDATE guild_settings SET automod_rules = ? WHERE guild_id = ?',
            (json.dumps(data['rules']), guild_id)
        )
        db.commit()
        return jsonify({"status": "success"})

@app.route("/api/guild/<int:guild_id>/stats")
@requires_authorization
def guild_stats(guild_id):
    guild = discord.fetch_guild(guild_id)
    if not guild:
        return jsonify({"error": "Guild not found"}), 404
    
    # Get member count
    members = discord.fetch_guild_members(guild_id)
    member_count = len(members) if members else 0
    
    # Get channel count from Discord API
    channels = discord.fetch_guild_channels(guild_id)
    channel_count = len(channels) if channels else 0
    
    # Get role count
    roles = discord.fetch_guild_roles(guild_id)
    role_count = len(roles) if roles else 0
    
    # Get command usage from database
    db = get_db()
    cmd_count = db.execute(
        'SELECT COUNT(*) as count FROM command_logs WHERE guild_id = ?',
        (guild_id,)
    ).fetchone()['count']
    
    return jsonify({
        "members": member_count,
        "channels": channel_count,
        "roles": role_count,
        "commands_used": cmd_count
    })

@app.errorhandler(Unauthorized)
def handle_unauthorized(e):
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True) 