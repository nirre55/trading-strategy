# test_usdc_balance.py
from binance_client import BinanceFuturesClient

def test_usdc_balance():
    # Vos clés API
    api_key = "0Ln7SbE79ve6E46KZWsLM61Axgx1Aoazm1uMYMOWaXFfxme7x39HoDzo3mJNK2NG"
    api_secret = "E8PnpZfY5xbNDULJKPp6ASLS1Oq91x4bvigqkQ904AUVGDD5drscmppyTGF1C0aK"
    
    client = BinanceFuturesClient(api_key, api_secret, testnet=False)
    
    # Test balance USDC
    balance_usdc, error_usdc = client.get_account_balance("USDC")
    print(f"Balance USDC: {balance_usdc if not error_usdc else f'ERREUR: {error_usdc}'}")
    
    # Test balance USDT
    balance_usdt, error_usdt = client.get_account_balance("USDT")
    print(f"Balance USDT: {balance_usdt if not error_usdt else f'ERREUR: {error_usdt}'}")
    
    # Test prix BTCUSDC
    price, error_price = client.get_current_price("BTCUSDC")
    print(f"Prix BTCUSDC: {price if not error_price else f'ERREUR: {error_price}'}")

if __name__ == "__main__":
    test_usdc_balance()