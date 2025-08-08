"""
Module de logging pour les activités de trading
"""
import os
import logging
from datetime import datetime
import config

class TradingLogger:
    def __init__(self):
        """Initialise le système de logging"""
        # Créer dossier logs s'il n'existe pas
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Nom du fichier de log avec date
        today = datetime.now().strftime("%Y%m%d")
        log_filename = f"trading_{today}.log"
        log_path = os.path.join(log_dir, log_filename)
        
        # Configuration du logger principal
        self.logger = logging.getLogger('TradingBot')
        self.logger.setLevel(logging.INFO)
        
        # Éviter les doublons si déjà configuré
        if not self.logger.handlers:
            # Handler pour fichier
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            
            # Handler pour console (optionnel)
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # Format des messages
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            # Ajouter les handlers
            self.logger.addHandler(file_handler)
            if config.SAFETY_CONFIG.get('LOG_TO_CONSOLE', True):
                self.logger.addHandler(console_handler)
        
        # Logger spécifique pour les trades
        self.trade_logger = logging.getLogger('TradeExecutions')
        self.trade_logger.setLevel(logging.INFO)
        
        if not self.trade_logger.handlers:
            # Fichier séparé pour les trades
            trade_log_filename = f"trades_{today}.log"
            trade_log_path = os.path.join(log_dir, trade_log_filename)
            
            trade_handler = logging.FileHandler(trade_log_path, encoding='utf-8')
            trade_handler.setLevel(logging.INFO)
            
            trade_formatter = logging.Formatter(
                '%(asctime)s | TRADE | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            trade_handler.setFormatter(trade_formatter)
            self.trade_logger.addHandler(trade_handler)
        
        self.info("TradingLogger initialisé")
        print(f"📝 Logs sauvegardés dans: {log_dir}")
    
    def info(self, message):
        """Log message d'information"""
        self.logger.info(message)
    
    def warning(self, message):
        """Log message d'avertissement"""
        self.logger.warning(message)
    
    def error(self, message):
        """Log message d'erreur"""
        self.logger.error(message)
    
    def signal_detected(self, signal_data, rsi_data, ha_data):
        """Log détection de signal"""
        message = (
            f"SIGNAL {signal_data['type']} DÉTECTÉ | "
            f"RSI: {rsi_data} | "
            f"HA: {ha_data['ha_source']} {ha_data['candle_color'].upper()} | "
            f"Prix: {ha_data['ha_close']}"
        )
        self.info(message)
    
    def signal_pending(self, signal_type, reason):
        """Log signal en attente"""
        message = f"SIGNAL {signal_type} EN ATTENTE | {reason}"
        self.info(message)
    
    def trade_conditions_check(self, validation_result):
        """Log vérification conditions de trade"""
        status = "VALIDÉE" if validation_result['status'] else "ÉCHOUÉE"
        message = f"VALIDATION TRADE {status} | {validation_result['message']}"
        if validation_result['status']:
            self.info(message)
        else:
            self.warning(message)
    
    def trade_opened(self, trade_result, signal_data):
        """Log ouverture de trade"""
        trade_message = (
            f"OUVERTURE TRADE {trade_result['side']} | "
            f"ID: {trade_result['trade_id']} | "
            f"Entrée: {trade_result['entry_price']} | "
            f"Quantité: {trade_result['quantity']} | "
            f"SL: {trade_result['stop_loss_price']} | "
            f"TP: {trade_result['take_profit_price']} | "
            f"Risque: {trade_result['risk_amount']:.2f} | "
            f"Profit potentiel: {trade_result['potential_profit']:.2f}"
        )
        
        # Log dans les deux fichiers
        self.info(trade_message)
        self.trade_logger.info(trade_message)
        
        # Log détails du signal
        signal_message = (
            f"SIGNAL SOURCE | "
            f"Type: {signal_data['type']} | "
            f"Source HA: {signal_data.get('source', 'HA1')} | "
            f"Long valid: {signal_data['long']['valid']} | "
            f"Short valid: {signal_data['short']['valid']}"
        )
        self.trade_logger.info(signal_message)
    
    def trade_failed(self, error_message, signal_data=None):
        """Log échec de trade"""
        message = f"ÉCHEC TRADE | {error_message}"
        if signal_data:
            message += f" | Signal: {signal_data['type']}"
        
        self.error(message)
        self.trade_logger.error(message)
    
    def order_executed(self, order_type, order_details):
        """Log exécution d'ordre"""
        is_fallback = order_details.get('is_fallback', False)
        fallback_info = " (FALLBACK)" if is_fallback else ""
        
        message = (
            f"ORDRE {order_type}{fallback_info} EXÉCUTÉ | "
            f"ID: {order_details.get('order_id', 'N/A')} | "
            f"Prix: {order_details.get('executed_price', 'N/A')} | "
            f"Quantité: {order_details.get('executed_quantity', 'N/A')}"
        )
        
        if is_fallback:
            original_type = order_details.get('original_type', 'UNKNOWN')
            message += f" | Original: {original_type}"
        
        self.info(message)
        self.trade_logger.info(message)
    
    def fallback_executed(self, fallback_type, original_type, slippage=None):
        """Log exécution de fallback"""
        message = f"FALLBACK {fallback_type} EXÉCUTÉ | Original: {original_type}"
        if slippage is not None:
            message += f" | Slippage: {slippage:.3f}%"
        
        self.warning(message)  # Warning car fallback = situation non idéale
        self.trade_logger.warning(message)
    
    def fallback_failed(self, fallback_type, original_type, reason):
        """Log échec de fallback"""
        message = f"FALLBACK {fallback_type} ÉCHOUÉ | Original: {original_type} | Raison: {reason}"
        self.error(message)
        self.trade_logger.error(message)
    
    def timeout_order(self, order_id, order_type, timeout_duration):
        """Log timeout d'ordre"""
        message = f"TIMEOUT ORDRE {order_type} | ID: {order_id} | Durée: {timeout_duration}s"
        self.warning(message)
        self.trade_logger.warning(message)
    
    def trade_closed(self, trade_id, close_reason, close_details=None):
        """Log fermeture de trade"""
        message = f"FERMETURE TRADE | ID: {trade_id} | Raison: {close_reason}"
        if close_details:
            message += f" | Détails: {close_details}"
        
        self.info(message)
        self.trade_logger.info(message)
    
    def stop_loss_hit(self, trade_id, sl_price):
        """Log déclenchement stop loss"""
        message = f"STOP LOSS DÉCLENCHÉ | Trade: {trade_id} | Prix SL: {sl_price}"
        self.warning(message)
        self.trade_logger.warning(message)
    
    def take_profit_hit(self, trade_id, tp_price):
        """Log atteinte take profit"""
        message = f"TAKE PROFIT ATTEINT | Trade: {trade_id} | Prix TP: {tp_price}"
        self.info(message)
        self.trade_logger.info(message)
    
    def balance_update(self, asset, balance):
        """Log mise à jour balance"""
        message = f"BALANCE {asset}: {balance}"
        self.info(message)
    
    def position_update(self, positions):
        """Log mise à jour positions"""
        if positions:
            for pos in positions:
                message = (
                    f"POSITION {pos['side']} | "
                    f"Taille: {pos['size']} | "
                    f"Prix entrée: {pos['entry_price']} | "
                    f"PnL: {pos['pnl']}"
                )
                self.info(message)
        else:
            self.info("AUCUNE POSITION ACTIVE")
    
    def system_status(self, status_message):
        """Log statut système"""
        self.info(f"SYSTÈME | {status_message}")
    
    def error_occurred(self, error_type, error_message, context=None):
        """Log erreur générale"""
        message = f"ERREUR {error_type} | {error_message}"
        if context:
            message += f" | Contexte: {context}"
        self.error(message)
    
    def daily_summary(self, trades_count, profit_loss=None):
        """Log résumé quotidien"""
        message = f"RÉSUMÉ QUOTIDIEN | Trades: {trades_count}"
        if profit_loss is not None:
            message += f" | P&L: {profit_loss:.2f}"
        
        self.info(message)
        self.trade_logger.info(message)
    
    def get_log_path(self):
        """Retourne le chemin du dossier de logs"""
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

# Instance globale pour utilisation dans les autres modules
trading_logger = TradingLogger()