# data_loader.py
"""
Module de chargement et préparation des données
"""
import pandas as pd
import os
from indicators import add_all_indicators

class DataLoader:
    """
    Classe pour charger et préparer les données de trading
    """
    
    def __init__(self, config):
        self.config = config
    
    def load_csv(self, filepath):
        """
        Charge un fichier CSV avec les données OHLCV
        
        Args:
            filepath: Chemin vers le fichier CSV
        
        Returns:
            DataFrame: Données chargées avec timestamp en index
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Le fichier {filepath} n'existe pas")
        
        try:
            df = pd.read_csv(filepath, parse_dates=["timestamp"])
            df.set_index("timestamp", inplace=True)
            
            # Vérification des colonnes requises
            required_columns = ['open', 'high', 'low', 'close']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise ValueError(f"Colonnes manquantes: {missing_columns}")
            
            print(f"✅ Données chargées: {len(df)} lignes de {df.index[0]} à {df.index[-1]}")
            return df
            
        except Exception as e:
            raise Exception(f"Erreur lors du chargement du fichier: {str(e)}")
    
    def prepare_data(self, df):
        """
        Prépare les données en ajoutant tous les indicateurs
        
        Args:
            df: DataFrame avec données OHLCV
        
        Returns:
            DataFrame: Données avec tous les indicateurs
        """
        print("📊 Calcul des indicateurs...")
        
        # Ajout de tous les indicateurs
        df = add_all_indicators(df, self.config)
        
        # Suppression des valeurs NaN
        initial_length = len(df)
        df.dropna(inplace=True)
        final_length = len(df)
        
        if initial_length != final_length:
            print(f"⚠️ {initial_length - final_length} lignes supprimées (valeurs NaN)")
        
        print(f"✅ Données préparées: {len(df)} lignes utilisables")
        return df
    
    def load_and_prepare(self, filepath):
        """
        Charge et prépare les données en une seule étape
        
        Args:
            filepath: Chemin vers le fichier CSV
        
        Returns:
            DataFrame: Données prêtes pour le backtest
        """
        df = self.load_csv(filepath)
        df = self.prepare_data(df)
        return df
    
    def validate_data(self, df):
        """
        Valide la qualité des données
        
        Args:
            df: DataFrame à valider
        
        Returns:
            dict: Rapport de validation
        """
        validation_report = {
            'total_rows': len(df),
            'date_range': (df.index.min(), df.index.max()),
            'missing_values': df.isnull().sum().to_dict(),
            'data_quality_issues': []
        }
        
        # Vérification des prix cohérents
        if (df['high'] < df['low']).any():
            validation_report['data_quality_issues'].append("High < Low détecté")
        
        if (df['high'] < df['open']).any() or (df['high'] < df['close']).any():
            validation_report['data_quality_issues'].append("High < Open/Close détecté")
        
        if (df['low'] > df['open']).any() or (df['low'] > df['close']).any():
            validation_report['data_quality_issues'].append("Low > Open/Close détecté")
        
        # Vérification des prix <= 0
        if (df[['open', 'high', 'low', 'close']] <= 0).any().any():
            validation_report['data_quality_issues'].append("Prix <= 0 détecté")
        
        # Vérification des gaps excessifs
        price_changes = df['close'].pct_change().abs()
        extreme_changes = price_changes > 0.5  # Changements > 50%
        if extreme_changes.any():
            validation_report['data_quality_issues'].append(f"{extreme_changes.sum()} changements de prix extrêmes (>50%)")
        
        return validation_report
    
    def print_validation_report(self, validation_report):
        """Affiche le rapport de validation"""
        print("\n📋 RAPPORT DE VALIDATION DES DONNÉES")
        print("-" * 40)
        print(f"Nombre de lignes: {validation_report['total_rows']}")
        print(f"Période: {validation_report['date_range'][0]} à {validation_report['date_range'][1]}")
        
        # Valeurs manquantes
        missing = validation_report['missing_values']
        if any(missing.values()):
            print(f"Valeurs manquantes: {missing}")
        else:
            print("✅ Aucune valeur manquante")
        
        # Problèmes de qualité
        issues = validation_report['data_quality_issues']
        if issues:
            print("⚠️ Problèmes détectés:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("✅ Aucun problème de qualité détecté")

def load_data(filepath, config):
    """
    Fonction utilitaire pour charger et préparer les données
    
    Args:
        filepath: Chemin vers le fichier CSV
        config: Configuration
    
    Returns:
        DataFrame: Données prêtes pour le backtest
    """
    loader = DataLoader(config)
    return loader.load_and_prepare(filepath)