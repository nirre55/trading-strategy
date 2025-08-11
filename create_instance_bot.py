import sys
import os
import shutil
import argparse

def copy_once(src_path, dst_path, force=False):
    if os.path.abspath(src_path) == os.path.abspath(dst_path):
        print(f"⚠️  Ignoré : destination identique à la source -> {dst_path}")
        return False

    if os.path.exists(dst_path):
        if force:
            try:
                shutil.rmtree(dst_path)
            except Exception as e:
                print(f"❌ Impossible de supprimer l'ancien dossier '{dst_path}': {e}")
                return False
        else:
            print(f"❌ Le dossier destination '{os.path.basename(dst_path)}' existe déjà. (utilise --force pour écraser)")
            return False

    try:
        shutil.copytree(src_path, dst_path)
        print(f"✅ Copié vers '{os.path.basename(dst_path)}'")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la copie vers '{os.path.basename(dst_path)}': {e}")
        return False

def build_destinations(base_dir, src, dest_args, n=None, start=1):
    # Si --n est utilisé, on doit avoir exactement 1 nom de base
    if n is not None:
        if len(dest_args) != 1:
            raise ValueError("--n nécessite un seul nom de destination (modèle).")
        base = dest_args[0]
        # Si le nom contient {i}, on l’utilise comme placeholder
        if "{i}" in base:
            names = [base.replace("{i}", str(i)) for i in range(start, start + n)]
        else:
            # Sinon on suffixe _1, _2, ...
            names = [f"{base}_{i}" for i in range(start, start + n)]
    else:
        # Mode normal : 1 ou plusieurs noms explicitement fournis
        names = dest_args

    # Construit les chemins complets
    src_path = os.path.join(base_dir, src)
    dst_paths = [os.path.join(base_dir, name) for name in names]
    return src_path, dst_paths

def main():
    parser = argparse.ArgumentParser(
        description="Copie un dossier (dans le même répertoire que le script) vers un ou plusieurs nouveaux dossiers."
    )
    parser.add_argument("source", help="Dossier source (ex: bot)")
    parser.add_argument("destinations", nargs="+", help="Un ou plusieurs noms de dossier destination")
    parser.add_argument("--force", action="store_true", help="Écraser les destinations si elles existent déjà")
    parser.add_argument("--n", type=int, default=None, help="Créer N copies à partir d'un seul nom (ou modèle avec {i})")
    parser.add_argument("--start", type=int, default=1, help="Indice de départ pour --n (défaut: 1)")

    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))

    source_path, destination_paths = build_destinations(
        base_dir, args.source, args.destinations, n=args.n, start=args.start
    )

    if not os.path.isdir(source_path):
        print(f"❌ Le dossier source '{args.source}' n'existe pas à côté du script.")
        sys.exit(1)

    ok = 0
    for dst_path in destination_paths:
        # Évite de copier la source vers un sous-dossier d'elle-même
        if os.path.abspath(dst_path).startswith(os.path.abspath(source_path) + os.sep):
            print(f"⚠️  Ignoré : la destination est à l'intérieur de la source -> {dst_path}")
            continue
        if copy_once(source_path, dst_path, force=args.force):
            ok += 1

    total = len(destination_paths)
    print(f"\nRésumé : {ok}/{total} copie(s) réussie(s).")

if __name__ == "__main__":
    main()
