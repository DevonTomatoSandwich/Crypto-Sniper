from web3 import Web3
from web3.middleware import geth_poa_middleware

# Connect
binance_seed_url = "https://bsc-dataseed.binance.org/"
web3 = Web3(Web3.HTTPProvider(binance_seed_url))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)
print("Connected:", web3.isConnected())