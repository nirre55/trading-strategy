import os


def load_api_credentials_from_env(key_name, filename=".env"):
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"Fichier .env non trouvé à l'emplacement : {env_path}")
    
    with open(env_path, "r") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if f"{key_name}=" in line:
                return line.split("=", 1)[1].strip()
    
    raise ValueError(f"Clé '{key_name}' manquante dans le fichier .env")

