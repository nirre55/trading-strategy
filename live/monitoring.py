# monitoring.py
"""
Système de surveillance et notifications pour le trading live
"""
import logging
import smtplib
import requests
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Gestionnaire de notifications Telegram"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
        
        if self.enabled:
            self._test_connection()
    
    def _test_connection(self):
        """Teste la connexion Telegram"""
        try:
            response = self.send_message("🤖 Bot de trading connecté !")
            if response:
                logger.info("✅ Telegram connecté")
            else:
                logger.error("❌ Erreur connexion Telegram")
                self.enabled = False
        except Exception as e:
            logger.error(f"❌ Erreur test Telegram: {e}")
            self.enabled = False
    
    def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """Envoie un message Telegram"""
        if not self.enabled:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi Telegram: {e}")
            return False

class DiscordNotifier:
    """Gestionnaire de notifications Discord"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)
    
    def send_message(self, message: str, username: str = "Trading Bot") -> bool:
        """Envoie un message Discord"""
        if not self.enabled:
            return False
        
        try:
            payload = {
                "content": message,
                "username": username
            }
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi Discord: {e}")
            return False

class EmailNotifier:
    """Gestionnaire de notifications Email"""
    
    def __init__(self, smtp_server: str, port: int, username: str, 
                 password: str, recipient: str):
        self.smtp_server = smtp_server
        self.port = port
        self.username = username
        self.password = password
        self.recipient = recipient
        self.enabled = bool(all([smtp_server, username, password, recipient]))
    
    def send_email(self, subject: str, message: str) -> bool:
        """Envoie un email"""
        if not self.enabled:
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = self.recipient
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, self.port)
            server.starttls()
            server.login(self.username, self.password)
            
            text = msg.as_string()
            server.sendmail(self.username, self.recipient, text)
            server.quit()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi email: {e}")
            return False

class LiveMonitoring:
    """Système de surveillance principal"""
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Notificateurs
        self.telegram = None
        self.discord = None
        self.email = None
        
        self._init_notifiers()
        
        # Surveillance
        self.monitoring_active = False
        self.monitor_thread = None
        self.check_interval = 30  # secondes
        
        # Métriques
        self.alerts_sent = 0
        self.last_heartbeat = None
        self.system_health = {}
        
        # Callbacks de surveillance
        self.health_callbacks = []
        
        # Historique des alertes
        self.alert_history = []
        
    def _init_notifiers(self):
        """Initialise les systèmes de notification"""
        # Telegram
        if self.config.get('telegram_enabled', False):
            self.telegram = TelegramNotifier(
                self.config.get('telegram_bot_token', ''),
                self.config.get('telegram_chat_id', '')
            )
        
        # Discord
        if self.config.get('discord_enabled', False):
            self.discord = DiscordNotifier(
                self.config.get('discord_webhook', '')
            )
        
        # Email
        if self.config.get('email_enabled', False):
            self.email = EmailNotifier(
                self.config.get('email_smtp', ''),
                self.config.get('email_port', 587),
                self.config.get('email_user', ''),
                self.config.get('email_password', ''),
                self.config.get('email_to', '')
            )
    
    def send_notification(self, message: str, level: str = "INFO"):
        """Envoie une notification sur tous les canaux actifs"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # Ajout de l'emoji selon le niveau
        if level == "CRITICAL":
            formatted_message = f"🚨 {formatted_message}"
        elif level == "WARNING":
            formatted_message = f"⚠️ {formatted_message}"
        elif level == "SUCCESS":
            formatted_message = f"✅ {formatted_message}"
        else:
            formatted_message = f"ℹ️ {formatted_message}"
        
        success_count = 0
        
        # Telegram
        if self.telegram and self.telegram.send_message(formatted_message):
            success_count += 1
        
        # Discord
        if self.discord and self.discord.send_message(formatted_message):
            success_count += 1
        
        # Email (seulement pour les alertes importantes)
        if self.email and level in ["CRITICAL", "WARNING"]:
            subject = f"Trading Bot Alert - {level}"
            if self.email.send_email(subject, formatted_message):
                success_count += 1
        
        # Logging
        if level == "CRITICAL":
            logger.critical(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)
        
        # Historique
        self.alert_history.append({
            'timestamp': datetime.now(),
            'level': level,
            'message': message,
            'sent_to_channels': success_count
        })
        
        self.alerts_sent += 1
        
        return success_count > 0
    
    def notify_signal_detected(self, signal):
        """Notification de détection de signal"""
        from signal_detector import format_signal_message
        
        message = f"""
🎯 SIGNAL DÉTECTÉ
{format_signal_message(signal)}
        """.strip()
        
        self.send_notification(message, "INFO")
    
    def notify_trade_opened(self, trade):
        """Notification d'ouverture de trade"""
        message = f"""
🚀 TRADE OUVERT
Direction: {trade.direction}
Entry: {trade.entry_price:.1f} USDT
SL: {trade.stop_loss:.1f} USDT
TP: {trade.take_profit:.1f} USDT
Quantité: {trade.quantity}
        """.strip()
        
        self.send_notification(message, "SUCCESS")
    
    def notify_trade_closed(self, trade):
        """Notification de fermeture de trade"""
        result_emoji = "✅" if trade.pnl > 0 else "❌"
        
        message = f"""
{result_emoji} TRADE FERMÉ
Direction: {trade.direction}
Entry: {trade.entry_price:.1f} USDT
Exit: {trade.exit_price:.1f} USDT
PnL: {trade.pnl:+.2f} USDT
Raison: {trade.exit_reason}
        """.strip()
        
        level = "SUCCESS" if trade.pnl > 0 else "WARNING"
        self.send_notification(message, level)
    
    def notify_emergency_stop(self, reason: str):
        """Notification d'arrêt d'urgence"""
        message = f"""
🚨 ARRÊT D'URGENCE ACTIVÉ
Raison: {reason}
Heure: {datetime.now().strftime('%H:%M:%S')}
Toutes les positions seront fermées.
        """.strip()
        
        self.send_notification(message, "CRITICAL")
    
    def notify_system_status(self, status: Dict):
        """Notification de statut système"""
        message = f"""
📊 STATUT SYSTÈME
Balance: {status.get('balance', 0):.2f} USDT
Trades actifs: {status.get('active_trades', 0)}
PnL jour: {status.get('daily_pnl', 0):+.2f} USDT
Connexion: {"✅" if status.get('connected', False) else "❌"}
        """.strip()
        
        self.send_notification(message, "INFO")
    
    def start_monitoring(self):
        """Démarre la surveillance système"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        logger.info("🔍 Surveillance système démarrée")
        self.send_notification("🤖 Surveillance système démarrée", "SUCCESS")
    
    def stop_monitoring(self):
        """Arrête la surveillance"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        
        logger.info("🔍 Surveillance système arrêtée")
        self.send_notification("🛑 Surveillance système arrêtée", "WARNING")
    
    def _monitor_loop(self):
        """Boucle principale de surveillance"""
        while self.monitoring_active:
            try:
                # Mise à jour du heartbeat
                self.last_heartbeat = datetime.now()
                
                # Exécution des vérifications de santé
                for callback in self.health_callbacks:
                    try:
                        health_data = callback()
                        self._process_health_data(health_data)
                    except Exception as e:
                        logger.error(f"❌ Erreur callback santé: {e}")
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"❌ Erreur boucle surveillance: {e}")
                time.sleep(self.check_interval)
    
    def _process_health_data(self, health_data: Dict):
        """Traite les données de santé du système"""
        self.system_health.update(health_data)
        
        # Vérifications critiques
        if not health_data.get('api_connected', True):
            self.send_notification("❌ Perte de connexion API Binance", "CRITICAL")
        
        if not health_data.get('websocket_connected', True):
            self.send_notification("❌ Perte de connexion WebSocket", "WARNING")
        
        latency = health_data.get('api_latency_ms', 0)
        if latency > 2000:
            self.send_notification(f"⚠️ Latence API élevée: {latency}ms", "WARNING")
        
        balance = health_data.get('balance', 0)
        if balance < 100:  # Seuil d'alerte balance faible
            self.send_notification(f"⚠️ Balance faible: {balance:.2f} USDT", "WARNING")
    
    def add_health_callback(self, callback):
        """Ajoute un callback de vérification de santé"""
        self.health_callbacks.append(callback)
    
    def send_daily_report(self, stats: Dict):
        """Envoie le rapport journalier"""
        message = f"""
📈 RAPPORT JOURNALIER
Date: {datetime.now().strftime('%d/%m/%Y')}

💰 Performance:
• PnL: {stats.get('daily_pnl', 0):+.2f} USDT
• Trades: {stats.get('daily_trades', 0)}
• Winrate: {stats.get('winrate', 0):.1f}%

📊 Métriques:
• Balance: {stats.get('balance', 0):.2f} USDT
• Drawdown max: {stats.get('max_drawdown', 0):.2f} USDT
• Pertes consécutives: {stats.get('consecutive_losses', 0)}

🔧 Système:
• Alertes envoyées: {self.alerts_sent}
• Uptime: {stats.get('uptime', 'N/A')}
• Dernière connexion: {self.last_heartbeat}
        """.strip()
        
        self.send_notification(message, "INFO")
    
    def send_weekly_summary(self, stats: Dict):
        """Envoie le résumé hebdomadaire"""
        message = f"""
📅 RÉSUMÉ HEBDOMADAIRE
Semaine du {stats.get('week_start', 'N/A')}

🎯 Performance globale:
• PnL total: {stats.get('weekly_pnl', 0):+.2f} USDT
• Total trades: {stats.get('weekly_trades', 0)}
• Winrate moyen: {stats.get('avg_winrate', 0):.1f}%
• Meilleur jour: {stats.get('best_day', 0):+.2f} USDT
• Pire jour: {stats.get('worst_day', 0):+.2f} USDT

📈 Stratégie:
• Signaux détectés: {stats.get('signals_detected', 0)}
• Signaux tradés: {stats.get('signals_traded', 0)}
• Taux d'exécution: {stats.get('execution_rate', 0):.1f}%

🔧 Stabilité:
• Erreurs API: {stats.get('api_errors', 0)}
• Reconnexions: {stats.get('reconnections', 0)}
• Disponibilité: {stats.get('uptime_percentage', 0):.1f}%
        """.strip()
        
        self.send_notification(message, "INFO")
    
    def get_monitoring_stats(self) -> Dict:
        """Retourne les statistiques de surveillance"""
        return {
            'monitoring_active': self.monitoring_active,
            'alerts_sent': self.alerts_sent,
            'last_heartbeat': self.last_heartbeat,
            'system_health': self.system_health,
            'notifiers_status': {
                'telegram': self.telegram.enabled if self.telegram else False,
                'discord': self.discord.enabled if self.discord else False,
                'email': self.email.enabled if self.email else False
            },
            'recent_alerts': self.alert_history[-10:] if self.alert_history else []
        }
    
    def test_all_notifications(self):
        """Teste tous les systèmes de notification"""
        test_message = f"🧪 Test notifications - {datetime.now().strftime('%H:%M:%S')}"
        
        results = {
            'telegram': False,
            'discord': False,
            'email': False
        }
        
        if self.telegram:
            results['telegram'] = self.telegram.send_message(test_message)
        
        if self.discord:
            results['discord'] = self.discord.send_message(test_message)
        
        if self.email:
            results['email'] = self.email.send_email("Test Trading Bot", test_message)
        
        # Résumé
        working = [k for k, v in results.items() if v]
        failing = [k for k, v in results.items() if not v and getattr(self, k, None)]
        
        summary = f"✅ Fonctionnels: {', '.join(working) if working else 'Aucun'}"
        if failing:
            summary += f"\n❌ En échec: {', '.join(failing)}"
        
        logger.info(f"Test notifications: {summary}")
        return results

class PerformanceTracker:
    """Tracker de performance et métriques"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.trades_history = []
        self.api_calls = 0
        self.errors_count = 0
        self.reconnections = 0
        
    def record_trade(self, trade_data: Dict):
        """Enregistre un trade pour les statistiques"""
        self.trades_history.append({
            **trade_data,
            'timestamp': datetime.now()
        })
    
    def record_api_call(self):
        """Enregistre un appel API"""
        self.api_calls += 1
    
    def record_error(self):
        """Enregistre une erreur"""
        self.errors_count += 1
    
    def record_reconnection(self):
        """Enregistre une reconnexion"""
        self.reconnections += 1
    
    def get_daily_stats(self) -> Dict:
        """Retourne les statistiques du jour"""
        today = datetime.now().date()
        today_trades = [t for t in self.trades_history 
                       if t['timestamp'].date() == today]
        
        if not today_trades:
            return {
                'daily_trades': 0,
                'daily_pnl': 0,
                'winrate': 0,
                'avg_trade_duration': 0
            }
        
        wins = [t for t in today_trades if t.get('pnl', 0) > 0]
        total_pnl = sum(t.get('pnl', 0) for t in today_trades)
        winrate = (len(wins) / len(today_trades)) * 100
        
        return {
            'daily_trades': len(today_trades),
            'daily_pnl': round(total_pnl, 2),
            'winrate': round(winrate, 1),
            'wins': len(wins),
            'losses': len(today_trades) - len(wins)
        }
    
    def get_weekly_stats(self) -> Dict:
        """Retourne les statistiques de la semaine"""
        week_ago = datetime.now() - timedelta(days=7)
        week_trades = [t for t in self.trades_history 
                      if t['timestamp'] >= week_ago]
        
        if not week_trades:
            return {'weekly_trades': 0, 'weekly_pnl': 0}
        
        total_pnl = sum(t.get('pnl', 0) for t in week_trades)
        wins = [t for t in week_trades if t.get('pnl', 0) > 0]
        
        # Stats par jour
        daily_pnls = {}
        for trade in week_trades:
            day = trade['timestamp'].date()
            daily_pnls[day] = daily_pnls.get(day, 0) + trade.get('pnl', 0)
        
        return {
            'weekly_trades': len(week_trades),
            'weekly_pnl': round(total_pnl, 2),
            'avg_winrate': round((len(wins) / len(week_trades)) * 100, 1),
            'best_day': round(max(daily_pnls.values()) if daily_pnls else 0, 2),
            'worst_day': round(min(daily_pnls.values()) if daily_pnls else 0, 2),
            'trading_days': len(daily_pnls)
        }
    
    def get_system_stats(self) -> Dict:
        """Retourne les statistiques système"""
        uptime = datetime.now() - self.start_time
        
        return {
            'uptime': str(uptime).split('.')[0],  # Format HH:MM:SS
            'uptime_hours': round(uptime.total_seconds() / 3600, 1),
            'api_calls': self.api_calls,
            'errors_count': self.errors_count,
            'reconnections': self.reconnections,
            'error_rate': round((self.errors_count / max(self.api_calls, 1)) * 100, 2)
        }