"""Version management pour JobHunt Dashboard."""
import os
import subprocess
from datetime import datetime

VERSION_FILE = os.path.join(os.path.dirname(__file__), "VERSION")
DB_SCHEMA_VERSION = 2  # Incrémenter quand le schéma DB change


def get_version():
    """Retourne la version actuelle."""
    try:
        with open(VERSION_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except:
        pass
    return "0.0.0"


def get_git_commit():
    """Retourne le short SHA du commit actuel."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=os.path.dirname(__file__)
        )
        return result.stdout.strip()[:7]
    except:
        return "unknown"


def get_git_tag():
    """Retourne le dernier tag git."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, timeout=5,
            cwd=os.path.dirname(__file__)
        )
        return result.stdout.strip()
    except:
        return get_version()


def is_dirty():
    """Vérifie si le repo a des modifications non commitées."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
            cwd=os.path.dirname(__file__)
        )
        return bool(result.stdout.strip())
    except:
        return True


def bump_version(part="patch"):
    """Incrémente la version."""
    parts = get_version().split(".")
    if len(parts) < 3:
        parts = ["1", "0", "0"]
    
    if part == "major":
        parts[0] = str(int(parts[0]) + 1)
        parts[1] = "0"
        parts[2] = "0"
    elif part == "minor":
        parts[1] = str(int(parts[1]) + 1)
        parts[2] = "0"
    else:  # patch
        parts[2] = str(int(parts[2]) + 1)
    
    new_version = ".".join(parts)
    try:
        with open(VERSION_FILE, "w") as f:
            f.write(f"# Version: x.y.z\n")
            f.write(f"# x = majeure (redesign, gros changements)\n")
            f.write(f"# y = mineure (nouvelles features)\n")
            f.write(f"# z = patch (fix, optimisations)\n")
            f.write(f"{new_version}\n")
    except:
        pass
    return new_version


def get_db_schema_version(conn):
    """Lit la version du schéma DB."""
    try:
        row = conn.execute("SELECT value FROM app_config WHERE key = 'schema_version'").fetchone()
        return int(row[0]) if row else 0
    except:
        return 0


def set_db_schema_version(conn, version):
    """Écrit la version du schéma DB."""
    conn.execute("CREATE TABLE IF NOT EXISTS app_config (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR REPLACE INTO app_config (key, value) VALUES ('schema_version', ?)", (str(version),))
    conn.commit()
