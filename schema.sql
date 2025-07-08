DROP TABLE IF EXISTS guild_settings;
DROP TABLE IF EXISTS command_logs;

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    welcome_channel TEXT,
    welcome_message TEXT,
    leveling_enabled INTEGER DEFAULT 1,
    xp_rate FLOAT DEFAULT 1.0,
    music_volume INTEGER DEFAULT 100,
    music_dj_role TEXT,
    music_channel TEXT,
    raid_protection_enabled INTEGER DEFAULT 1,
    raid_join_threshold INTEGER DEFAULT 6,
    raid_join_window INTEGER DEFAULT 10,
    nuke_protection_enabled INTEGER DEFAULT 1,
    nuke_action_threshold INTEGER DEFAULT 3,
    nuke_action_window INTEGER DEFAULT 30,
    audit_log_channel TEXT,
    role_xp_multipliers TEXT DEFAULT '{}',
    custom_prefix TEXT DEFAULT '!',
    automod_rules TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS command_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    user_id INTEGER,
    command TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS level_roles (
    guild_id INTEGER,
    role_id INTEGER,
    level_requirement INTEGER,
    PRIMARY KEY (guild_id, role_id)
); 