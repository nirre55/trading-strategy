import os
import sys
import subprocess
import shutil
from datetime import datetime

def find_bot_dirs(base_dir):
    # On ne prend que les dossiers qui commencent par "bot_"
    return [
        d for d in os.listdir(base_dir)
        if d.startswith("bot_") and os.path.isdir(os.path.join(base_dir, d))
    ]

def launch_with_windows_terminal(bot_dir):
    """
    Lance le bot dans une nouvelle fenêtre ou onglet Windows Terminal (si installé).
    """
    wt = shutil.which("wt")  # Windows Terminal
    if not wt:
        return False

    # -w 0 : utilise la fenêtre existante si ouverte, sinon en crée une
    # nt : new tab ;  -d . : set working dir
    cmd = [
        wt, "-w", "0", "nt", "-d", ".", sys.executable, "-u", "main.py"
    ]
    subprocess.Popen(cmd, cwd=bot_dir, close_fds=True)
    return True

def launch_with_cmd_start(bot_dir, title):
    """
    Lance le bot dans une NOUVELLE fenêtre de console via 'start'.
    /k garde la fenêtre ouverte pour voir la sortie en direct.
    """
    # Optionnel: logs sur disque en plus d'afficher dans la fenêtre
    log_dir = os.path.join(bot_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_log = os.path.join(log_dir, f"stdout-{ts}.log")
    err_log = os.path.join(log_dir, f"stderr-{ts}.log")

    python_exe = sys.executable

    # Commande exécutée dans la fenêtre: python -u main.py >>stdout 2>>stderr
    inner = f'"{python_exe}" -u main.py >> "{out_log}" 2>> "{err_log}"'

    # start "<title>" cmd /k "<commande>"
    # shell=True pour laisser 'start' être interprété par cmd.exe
    full_cmd = f'start "{title}" cmd /k {inner}'
    subprocess.Popen(full_cmd, cwd=bot_dir, shell=True, close_fds=True)

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    bot_dirs = find_bot_dirs(base_dir)

    if not bot_dirs:
        print("Aucun dossier 'bot_*' trouvé.")
        return

    print("Ouverture d'une console par bot (Windows)...")
    for d in bot_dirs:
        bot_path = os.path.join(base_dir, d)
        main_py = os.path.join(bot_path, "main.py")
        if not os.path.isfile(main_py):
            print(f" - {d}: aucun main.py, ignoré.")
            continue

        # Essaye Windows Terminal, sinon 'start'
        if launch_with_windows_terminal(bot_path):
            print(f" - {d}: lancé dans Windows Terminal.")
        else:
            launch_with_cmd_start(bot_path, title=d)
            print(f" - {d}: lancé dans une nouvelle fenêtre cmd (logs dans {d}\\logs).")

    print("Tout est lancé. Tu peux fermer ce script, les fenêtres des bots restent ouvertes.")

if __name__ == "__main__":
    if os.name != "nt":
        print("Ce script est prévu pour Windows.")
    main()
