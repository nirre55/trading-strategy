import sys
import os
import shutil

def main():
    if len(sys.argv) != 3:
        print("Usage: python copy_folder.py <dossier_source> <dossier_destination>")
        sys.exit(1)

    source = sys.argv[1]
    destination = sys.argv[2]

    # Répertoire où se trouve le script
    base_dir = os.path.dirname(os.path.abspath(__file__))

    source_path = os.path.join(base_dir, source)
    destination_path = os.path.join(base_dir, destination)

    if not os.path.exists(source_path):
        print(f"Erreur : le dossier source '{source}' n'existe pas.")
        sys.exit(1)

    if os.path.exists(destination_path):
        print(f"Erreur : le dossier destination '{destination}' existe déjà.")
        sys.exit(1)

    try:
        shutil.copytree(source_path, destination_path)
        print(f"Dossier '{source}' copié vers '{destination}'.")
    except Exception as e:
        print(f"Erreur lors de la copie : {e}")

if __name__ == "__main__":
    main()
