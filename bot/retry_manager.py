"""
Gestion centralisée des retries pour les appels API (Binance/HTTP)
"""
import time
import functools
from typing import Callable, Any, Tuple

import config

class RetryManager:
    @staticmethod
    def _params_from_config(operation: str) -> Tuple[int, int, float]:
        """Retourne (max_retries, delay, backoff_multiplier) depuis config.RETRY_CONFIG pour une opération donnée."""
        cfg = getattr(config, 'RETRY_CONFIG', {})
        default_max = int(cfg.get('DEFAULT_MAX_RETRIES', 5))
        default_delay = int(cfg.get('DEFAULT_DELAY', 10))
        default_bo = float(cfg.get('DEFAULT_BACKOFF_MULTIPLIER', 1.2))

        mapping = {
            'VALIDATION': (
                cfg.get('VALIDATION_RETRIES', default_max),
                cfg.get('VALIDATION_DELAY', default_delay),
                default_bo,
            ),
            'PRICE': (
                cfg.get('PRICE_FETCH_RETRIES', default_max),
                default_delay,
                default_bo,
            ),
            'BALANCE': (
                cfg.get('BALANCE_FETCH_RETRIES', default_max),
                default_delay,
                default_bo,
            ),
            'POSITION': (
                cfg.get('POSITION_FETCH_RETRIES', default_max),
                default_delay,
                default_bo,
            ),
            'ORDER_PLACEMENT': (
                cfg.get('ORDER_PLACEMENT_RETRIES', default_max),
                cfg.get('ORDER_DELAY', default_delay),
                default_bo,
            ),
            'ORDER_STATUS': (
                cfg.get('ORDER_STATUS_RETRIES', default_max),
                cfg.get('STATUS_CHECK_DELAY', 2),
                default_bo,
            ),
            'ORDER_CANCELLATION': (
                cfg.get('ORDER_CANCELLATION_RETRIES', default_max),
                default_delay,
                default_bo,
            ),
            # Fallback par défaut
            'DEFAULT': (default_max, default_delay, default_bo),
        }

        if operation.upper() not in mapping:
            return mapping['DEFAULT']
        params = mapping[operation.upper()]
        # Casts sûrs
        return int(params[0]), int(params[1]), float(params[2])

    @staticmethod
    def _is_retriable_exception(exception: Exception) -> bool:
        """Détermine si une exception est retriable basé sur son type ou nom."""
        exception_name = type(exception).__name__
        module_name = type(exception).__module__
        
        # Exceptions Binance
        if module_name == 'binance.exceptions' and exception_name == 'BinanceAPIException':
            return True
        
        # Exceptions requests
        if module_name == 'requests.exceptions':
            if exception_name in ['RequestException', 'ConnectionError', 'Timeout', 'HTTPError']:
                return True
        
        # Exceptions réseau standards
        if exception_name in ['ConnectionError', 'TimeoutError', 'OSError']:
            return True
            
        # Exceptions urllib (utilisé par requests)
        if 'urllib' in module_name and exception_name in ['URLError', 'HTTPError']:
            return True
            
        return False

    @staticmethod
    def with_retry(max_retries: int = 5, delay: int = 10, backoff_multiplier: float = 1.0):
        """Décorateur générique de retry."""
        def decorator(func: Callable[..., Any]):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                last_exception: Exception | None = None
                current_delay: float = float(delay)

                for attempt in range(max_retries + 1):  # +1 = tentative initiale
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        if RetryManager._is_retriable_exception(e):
                            last_exception = e
                            if attempt < max_retries:
                                print(f"⚠️ Tentative {attempt + 1}/{max_retries + 1} échouée: {e}")
                                print(f"🔄 Retry dans {current_delay:.1f}s...")
                                time.sleep(current_delay)
                                current_delay *= backoff_multiplier
                            else:
                                print(f"❌ Toutes les tentatives échouées après {max_retries + 1} essais")
                                raise last_exception
                        else:
                            # Exception non-retriable
                            print(f"❌ Erreur non-retriable: {e}")
                            raise e

                # Sécurité (ne devrait pas arriver)
                if last_exception is not None:
                    raise last_exception
                raise RuntimeError("Erreur inattendue: aucune exception capturée")

            return wrapper
        return decorator

    @staticmethod
    def with_configured_retry(operation: str):
        """Décorateur basé sur config.RETRY_CONFIG pour l'opération donnée."""
        max_retries, delay, backoff_multiplier = RetryManager._params_from_config(operation)
        return RetryManager.with_retry(max_retries=max_retries, delay=delay, backoff_multiplier=backoff_multiplier)

    @staticmethod
    def retry_api_call(func: Callable[..., Any], *args, max_retries: int | None = None, delay: int | None = None, backoff_multiplier: float | None = None, **kwargs):
        """Retry impératif d'un appel API donné."""
        cfg_max, cfg_delay, cfg_bo = RetryManager._params_from_config('DEFAULT')
        retries = cfg_max if max_retries is None else max_retries
        wait = cfg_delay if delay is None else delay
        bo = cfg_bo if backoff_multiplier is None else backoff_multiplier

        last_exception: Exception | None = None
        current_delay: float = float(wait)

        for attempt in range(retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if RetryManager._is_retriable_exception(e):
                    last_exception = e
                    if attempt < retries:
                        print(f"⚠️ Tentative {attempt + 1}/{retries + 1} échouée: {e}")
                        print(f"🔄 Retry dans {current_delay:.1f}s...")
                        time.sleep(current_delay)
                        current_delay *= bo
                    else:
                        print("❌ Toutes les tentatives échouées")
                        raise last_exception
                else:
                    # Exception non-retriable
                    raise e

        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Erreur inattendue: aucune exception capturée")