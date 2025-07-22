# stats.py
"""
Module de calcul et affichage des statistiques de backtest
"""
import pandas as pd
import numpy as np

class BacktestStats:
    """
    Classe pour calculer et afficher les statistiques de backtest
    """
    
    def __init__(self, trades, logs, max_drawdown=None):
        self.trades = trades
        self.logs = logs
        self.max_drawdown = max_drawdown
        self.df_logs = pd.DataFrame(logs) if logs else pd.DataFrame()
    
    def calculate_basic_stats(self):
        """Calcule les statistiques de base"""
        total = len(self.trades)
        wins = sum(1 for t in self.trades if t == 'win')
        losses = total - wins
        winrate = (wins / total * 100) if total > 0 else 0
        
        return {
            'total_trades': total,
            'wins': wins,
            'losses': losses,
            'winrate': winrate
        }
    
    def calculate_streaks(self):
        """Calcule les séries de gains/pertes"""
        if not self.trades:
            return {'max_win_streak': 0, 'max_loss_streak': 0}
        
        max_win_streak = 0
        max_loss_streak = 0
        current_win_streak = 0
        current_loss_streak = 0
        
        for result in self.trades:
            if result == 'win':
                current_win_streak += 1
                current_loss_streak = 0
            else:
                current_loss_streak += 1
                current_win_streak = 0
            
            max_win_streak = max(max_win_streak, current_win_streak)
            max_loss_streak = max(max_loss_streak, current_loss_streak)
        
        return {
            'max_win_streak': max_win_streak,
            'max_loss_streak': max_loss_streak
        }
    
    def calculate_pnl_stats(self):
        """Calcule les statistiques de P&L"""
        if self.df_logs.empty or 'pnl' not in self.df_logs.columns:
            return {}
        
        total_pnl = self.df_logs['pnl'].sum()
        avg_win = self.df_logs[self.df_logs['result'] == 'win']['pnl'].mean() if len(self.df_logs[self.df_logs['result'] == 'win']) > 0 else 0
        avg_loss = self.df_logs[self.df_logs['result'] == 'loss']['pnl'].mean() if len(self.df_logs[self.df_logs['result'] == 'loss']) > 0 else 0
        
        return {
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        }
    
    def calculate_risk_metrics(self):
        """Calcule les métriques de risque"""
        if self.df_logs.empty or 'capital' not in self.df_logs.columns:
            return {}
        
        capital_series = self.df_logs['capital']
        returns = capital_series.pct_change().dropna()
        
        # Sharpe ratio approximatif (sans taux sans risque)
        sharpe = returns.mean() / returns.std() if returns.std() != 0 else 0
        
        # Calmar ratio (rendement annualisé / max drawdown)
        if len(capital_series) > 1:
            total_return = (capital_series.iloc[-1] / capital_series.iloc[0]) - 1
            calmar = total_return / (self.max_drawdown / capital_series.iloc[0]) if self.max_drawdown > 0 else 0
        else:
            calmar = 0
        
        return {
            'sharpe_ratio': sharpe,
            'calmar_ratio': calmar,
            'volatility': returns.std()
        }
    
    def get_all_stats(self):
        """Retourne toutes les statistiques"""
        stats = {}
        stats.update(self.calculate_basic_stats())
        stats.update(self.calculate_streaks())
        stats.update(self.calculate_pnl_stats())
        stats.update(self.calculate_risk_metrics())
        
        if self.max_drawdown is not None:
            stats['max_drawdown'] = self.max_drawdown
        
        return stats
    
    def print_stats(self):
        """Affiche les statistiques formatées"""
        stats = self.get_all_stats()
        
        print(f"📊 Total Trades: {stats['total_trades']}")
        print(f"✅ Wins: {stats['wins']}")
        print(f"❌ Losses: {stats['losses']}")
        print(f"📈 Winrate: {stats['winrate']:.2f}%")
        print(f"🔥 Max Win Streak: {stats['max_win_streak']}")
        print(f"💥 Max Loss Streak: {stats['max_loss_streak']}")
        
        if 'max_drawdown' in stats:
            print(f"🔻 Max Drawdown: ${stats['max_drawdown']:.2f}")
        
        if 'total_pnl' in stats:
            print(f"💰 Total P&L: ${stats['total_pnl']:.2f}")
            print(f"📊 Avg Win: ${stats['avg_win']:.2f}")
            print(f"📉 Avg Loss: ${stats['avg_loss']:.2f}")
            print(f"⚡ Profit Factor: {stats['profit_factor']:.2f}")
        
        if 'sharpe_ratio' in stats:
            print(f"📈 Sharpe Ratio: {stats['sharpe_ratio']:.3f}")
            print(f"📊 Calmar Ratio: {stats['calmar_ratio']:.3f}")
            print(f"📊 Volatility: {stats['volatility']:.3f}")

def print_stats(trades, max_drawdown=None, logs=None):
    """
    Fonction utilitaire pour afficher les statistiques
    Compatible avec l'ancienne interface
    """
    stats_calculator = BacktestStats(trades, logs or [], max_drawdown)
    stats_calculator.print_stats()

def export_trades_to_csv(logs, filename="trades_result.csv"):
    """
    Exporte les trades vers un fichier CSV
    """
    if not logs:
        print("Aucun trade à exporter")
        return
    
    df = pd.DataFrame(logs)
    df.to_csv(filename, index=False)
    print(f"\n✅ Fichier exporté : {filename}")

def create_performance_report(trades, logs, max_drawdown, filename="performance_report.txt"):
    """
    Crée un rapport de performance détaillé
    """
    stats_calculator = BacktestStats(trades, logs, max_drawdown)
    all_stats = stats_calculator.get_all_stats()
    
    report = []
    report.append("=" * 50)
    report.append("RAPPORT DE PERFORMANCE BACKTEST")
    report.append("=" * 50)
    report.append("")
    
    # Statistiques générales
    report.append("📊 STATISTIQUES GÉNÉRALES")
    report.append("-" * 30)
    report.append(f"Total Trades: {all_stats['total_trades']}")
    report.append(f"Wins: {all_stats['wins']}")
    report.append(f"Losses: {all_stats['losses']}")
    report.append(f"Winrate: {all_stats['winrate']:.2f}%")
    report.append("")
    
    # Séries
    report.append("🔥 SÉRIES DE GAINS/PERTES")
    report.append("-" * 30)
    report.append(f"Max Win Streak: {all_stats['max_win_streak']}")
    report.append(f"Max Loss Streak: {all_stats['max_loss_streak']}")
    report.append("")
    
    # P&L
    if 'total_pnl' in all_stats:
        report.append("💰 PROFIT & LOSS")
        report.append("-" * 30)
        report.append(f"Total P&L: ${all_stats['total_pnl']:.2f}")
        report.append(f"Avg Win: ${all_stats['avg_win']:.2f}")
        report.append(f"Avg Loss: ${all_stats['avg_loss']:.2f}")
        report.append(f"Profit Factor: {all_stats['profit_factor']:.2f}")
        report.append("")
    
    # Risque
    if 'max_drawdown' in all_stats:
        report.append("⚠️ MÉTRIQUES DE RISQUE")
        report.append("-" * 30)
        report.append(f"Max Drawdown: ${all_stats['max_drawdown']:.2f}")
        if 'sharpe_ratio' in all_stats:
            report.append(f"Sharpe Ratio: {all_stats['sharpe_ratio']:.3f}")
            report.append(f"Calmar Ratio: {all_stats['calmar_ratio']:.3f}")
            report.append(f"Volatility: {all_stats['volatility']:.3f}")
        report.append("")
    
    # Analyse par direction
    if logs:
        df_logs = pd.DataFrame(logs)
        if 'direction' in df_logs.columns:
            report.append("📈 ANALYSE PAR DIRECTION")
            report.append("-" * 30)
            
            for direction in ['LONG', 'SHORT']:
                dir_trades = df_logs[df_logs['direction'] == direction]
                if len(dir_trades) > 0:
                    dir_wins = len(dir_trades[dir_trades['result'] == 'win'])
                    dir_winrate = (dir_wins / len(dir_trades)) * 100
                    report.append(f"{direction}: {len(dir_trades)} trades, {dir_winrate:.1f}% winrate")
            report.append("")
    
    # Sauvegarde du rapport
    report_text = "\n".join(report)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print(f"\n📊 Rapport de performance sauvegardé : {filename}")
    return report_text