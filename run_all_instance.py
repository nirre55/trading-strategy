import os
import sys
import time
import argparse
import subprocess
from datetime import datetime

def find_bot_dirs(base_dir, only=None):
    dirs = [d for d in os.listdir(base_dir)
            if d.startswith("bot_") and os.path.isdir(os.path.join(base_dir, d))]
    dirs.sort()
    if only:
        wanted = set(only)
        dirs = [d for d in dirs if d in wanted]
    return dirs

def pick_python(bot_dir):
    # Utilise le venv local si présent, sinon l'interpréteur courant
    for v in (".venv", "venv", "env"):
        exe = os.path.join(bot_dir, v, "Scripts", "python.exe")
        if os.path.isfile(exe):
            return exe
    return sys.executable

def make_console_bat(bot_dir, python_exe):
    """Crée un .bat qui lance main.py, montre la sortie et reste ouvert."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bat_path = os.path.join(bot_dir, f"_run_main_{ts}.bat")
    content = f"""@echo off
setlocal
cd /d "%~dp0"
title {os.path.basename(bot_dir)}
echo [INFO] Dossier: %CD%
echo [INFO] Python: {python_exe}
echo [INFO] Lancement: "{python_exe}" -u main.py
echo.
"{python_exe}" -u main.py
echo.
echo [TERMINE] %DATE% %TIME%
pause
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(content)
    return bat_path

def launch_console(bot_dir):
    """Lance le .bat dans une nouvelle fenêtre via 'start' (fiable)."""
    python_exe = pick_python(bot_dir)
    bat = make_console_bat(bot_dir, python_exe)
    title = os.path.basename(bot_dir)

    # 'start' est une commande interne de cmd → shell=True requis
    # Le premier argument entre guillemets après start est le titre
    cmd = f'start "{title}" "{bat}"'
    subprocess.Popen(cmd, cwd=bot_dir, shell=True, close_fds=True)

def launch_background(bot_dir):
    """Option arrière-plan (sans fenêtre), avec logs."""
    python_exe = pick_python(bot_dir)
    log_dir = os.path.join(bot_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_log = os.path.join(log_dir, f"stdout-{ts}.log")
    err_log = os.path.join(log_dir, f"stderr-{ts}.log")
    stdout_f = open(out_log, "ab", buffering=0)
    stderr_f = open(err_log, "ab", buffering=0)

    subprocess.Popen(
        [python_exe, "-u", "main.py"],
        cwd=bot_dir,
        stdin=subprocess.DEVNULL,
        stdout=stdout_f,
        stderr=stderr_f,
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )

def main():
    parser = argparse.ArgumentParser(description="Lancer tous les bot_*/main.py (Windows).")
    parser.add_argument("--mode", choices=["console", "background"], default="console",
                        help="console = fenêtre par bot (live), background = sans fenêtre (logs).")
    parser.add_argument("--delay", type=float, default=0.4,
                        help="Pause entre lancements (éviter collisions).")
    parser.add_argument("--only", nargs="*", default=None,
                        help="Ne lancer que certains dossiers (ex: --only bot_final bot_abc).")
    args = parser.parse_args()

    if os.name != "nt":
        print("Ce script est prévu pour Windows.")
        sys.exit(1)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    bot_dirs = find_bot_dirs(base_dir, only=args.only)

    if not bot_dirs:
        print("Aucun dossier 'bot_*' trouvé.")
        return

    print("Bots détectés:", bot_dirs)

    for d in bot_dirs:
        bot_path = os.path.join(base_dir, d)
        if not os.path.isfile(os.path.join(bot_path, "main.py")):
            print(f" - {d}: aucun main.py, ignoré.")
            continue

        try:
            if args.mode == "console":
                launch_console(bot_path)
                print(f" - {d}: fenêtre ouverte (live).")
            else:
                launch_background(bot_path)
                print(f" - {d}: lancé en arrière-plan (logs dans {d}\\logs).")
            time.sleep(args.delay)
        except Exception as e:
            print(f" - {d}: échec du lancement → {e}")

    print("Terminé.")

if __name__ == "__main__":
    main()
