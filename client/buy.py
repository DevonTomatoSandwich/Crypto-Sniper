import os
import requests
import json
import traceback
import datetime, time, pytz
import dotenv
from web3.exceptions import ContractLogicError

from connect import web3
import common_abis

dotenv.load_dotenv()
is_dev_buy = os.getenv("is_dev_buy").lower() == "true"

addr_wbnb = web3.toChecksumAddress("0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c")
contract_wbnb = web3.eth.contract(address=addr_wbnb, abi=common_abis.abi_wbnb)

addr_pancake_router = web3.toChecksumAddress(
    "0x10ED43C718714eb63d5aA57B78B54704E256024E"
)
contract_pancake = web3.eth.contract(
    address=addr_pancake_router, abi=common_abis.abi_pancake
)


def quote(name, addr, usd, gas, hours_wait):
    """
    Creates all data needed for a quote
    Args
        name (str)          :   token name
        addr (str)          :   contract address of token
        usd (float)         :   usd of token to be bought
        gas (float)         :   gas price in gwei
        hours_wait (float)  :   hours till deadline
    Returns
        name (str)          :   token name
        balance (float)     :   bnb balance in personal wallet
        bnb (float)         :   bnb of token to be bought (in ether units)
        gas_fee (float)     :   gas fee in wbnb
        bnb_total (float)   :   total cost in bnb (bnb + gas_fee)
        usd_total (float)   :   total cost in usd (bnb_total * usd_on_bnb)
        bnb_remain          :   remaining bnb if purchased (balance - bnb_total)
        usd_remain          :   remaining usd if purchased (bnb_remain * usd_on_bnb)
        deadline (str)      :   txn deadline in ymd hms
        price (float)       :   current price of token ($bnb / token)
        usd_on_bnb          :   price of 1 bnb in usd
        tokens (float)      :   an estimate of the tokens to recieve
        gas_limit           :   gas units for txn (hardcoded as 250000)
        deadline_epoch (int):   txn deadline in epoch
        quote_msg (str)     :   message to display in alert including all other data
    """
    usd_on_bnb = get_usd_on_bnb()
    bnb_on_usd = 1 / usd_on_bnb
    # print("usd_on_bnb =", usd_on_bnb)
    bnb_value = usd * bnb_on_usd
    # print("bnb_value =", bnb_value)
    balance_wei = web3.eth.get_balance(os.getenv("personal_bnb_addr"))
    balance = float(web3.fromWei(balance_wei, "ether"))
    # print("balance =", balance)
    addr_token = web3.toChecksumAddress(addr)
    price = get_price(addr_token)
    # print("price =", price)
    tokens = bnb_value / price
    # print("tokens =", tokens)
    deadline_epoch = int(time.time() + hours_wait * 3600)
    # print("deadline_epoch =", deadline_epoch, type(deadline_epoch))
    deadline_utc_naive = datetime.datetime.utcfromtimestamp(deadline_epoch)
    deadline_utc_aware = pytz.utc.localize(deadline_utc_naive)
    tz_local = pytz.timezone(os.getenv("pytz_local_tz"))
    deadline = deadline_utc_aware.astimezone(tz_local).strftime("%Y-%m-%d %H:%M:%S")
    gas_limit = 250000

    # make quote
    bnb = bnb_value
    gas_fee = gas_limit * gas * 1e-9
    bnb_total = bnb + gas_fee
    usd_total = bnb_total * usd_on_bnb
    bnb_remain = balance - bnb_total
    usd_remain = bnb_remain * usd_on_bnb
    data = {
        # for quote
        "name": name,
        "balance": balance,
        "bnb": bnb,
        "gas_fee": gas_fee,
        "bnb_total": bnb_total,
        "usd_total": usd_total,
        "bnb_remain": bnb_remain,
        "usd_remain": usd_remain,
        "deadline": deadline,  # readable
        "price": price,
        "usd_on_bnb": usd_on_bnb,
        "tokens": tokens,
        "gas_limit": gas_limit,
        "deadline_epoch": deadline_epoch,
    }
    fmt = ".8f"
    quote_msg = f"""About to buy:
        name: {data["name"]}

        bnb balance     : {format(data["balance"], fmt)}

        bnb for token   : {format(data["bnb"], fmt)}
        bnb gas cost    : {format(data["gas_fee"], fmt)}
        bnb total       : {format(data["bnb_total"], fmt)}
        usd total       : {format(data["usd_total"], fmt)}

        bnb remain      : {format(data["bnb_remain"], fmt)}
        usd remain      : {format(data["usd_remain"], fmt)}

        deadline utc    : {data["deadline"]}
        price token bnb : {format(data["price"], fmt)}
        price token usd : {format(data["price"] * data["usd_on_bnb"], fmt)}
        price bnb       : {format(data["usd_on_bnb"], fmt)}
        tokens          : {format(data["tokens"], fmt)}
        gas_limit       : {data["gas_limit"]}"""
    data["quote_msg"] = quote_msg
    return json.dumps(data)


def buy(addr_token, deadline_epoch, bnb_value, gas_price, gas_limit):
    """
    Purchases the token. Builds, signs and sends the transaction.
    The transaction hex is returned as a reciept
    If is_dev_buy is True (for testing) transaction will not be sent
    and fake hex will be sent back.
    Args
        addr_token (str)        :   the token's contract address
        deadline_epoch (int)    :   txn deadline in epoch
        bnb_value (float)       :   bnb of token to be bought (in ether units)
        gas_price (float)       :   gas price in gwei
        gas_limit (int)         :   gas units for txn (hardcoded as 250000)
    Return
        tx_reciept_hex (str)    :   the purchase's transaction hex
    """
    pending_tx = contract_pancake.functions.swapExactETHForTokens(
        0,  # amountOutMin
        [addr_wbnb, addr_token],  # path
        os.getenv("personal_bnb_addr"),  # to
        deadline_epoch,  # deadline
    )
    nonce = web3.eth.get_transaction_count(os.getenv("personal_bnb_addr"))
    built_tx = pending_tx.buildTransaction(
        {
            "from": os.getenv("personal_bnb_addr"),
            "value": web3.toWei(bnb_value, "ether"),  # to swap from
            "gas": gas_limit,  # 250k gas at 5gwei for bnb@350 is USD0.50
            "gasPrice": web3.toWei(gas_price, "gwei"),  # usually always 5 gwei
            "nonce": nonce,
        }
    )
    if is_dev_buy:
        return "0x01234"
    # sign
    signed_txn = web3.eth.account.sign_transaction(
        built_tx, private_key=os.getenv("private")
    )
    try:
        tx_reciept = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        tx_reciept_hex = web3.toHex(tx_reciept)
        # print("tx_reciept_hex =", tx_reciept_hex)
    except ValueError as e:
        print("Exception e =", e, type(e))
        traceback.print_exc()
        return "error"
    return tx_reciept_hex


def get_price(addr):
    """
    Gets the current price of the token in wbnb
    Args
        addr (str)  :   token's contract address
    Return
        (float)     :   price of token ($bnb / token)
    """
    contract_token = web3.eth.contract(address=addr, abi=common_abis.abi_usdc)
    decimal_factor = get_decimal_factor(contract_token)
    base_unit_factor = get_base_unit_factor(addr)
    if base_unit_factor is None:
        return None
    return decimal_factor * base_unit_factor


def get_decimal_factor(contract_token):
    """
    Gets the decimal factor used for converting price.
    tokens each have different numbers of decimals. Each different
    decimal affects the conversion by a factor of 10.
    Args
        contract_token (web3.Contract)  :   token's contract
    Return
        (float)                         :   decimal factor
    """
    digits1 = contract_wbnb.functions.decimals().call()
    digits2 = contract_token.functions.decimals().call()
    return 1 / (10 ** (digits1 - digits2))


def get_base_unit_factor(addr_token):
    """
    Gets the base unit factor used for converting price.
    base_unit_factor is the cost of 1 `token` base unit
    given in the price of 1 base unit of wbnb
    Args
        addr_token (str)            :   token's contract address
    Return
        base_unit_factor (float)    :   base unit factor
    """
    try:
        # amount_out is the value of the first token  given in the price of token 2
        amount_out = contract_pancake.functions.getAmountsOut(
            1, [addr_wbnb, addr_token]
        ).call()[1]
    except ContractLogicError as e:
        print("Error ContractLogicError in get_base_unit_factor: ", e)
        return None
    base_unit_factor = None
    if amount_out == 0:
        # edge case
        # this means token2 has a weird number of decimals eg doge has 8 decimals, meaning a doge base unit
        # is actually very expensive compared to a wbnb base unit. In this case flip the token order
        # now amount_out is the value of the wbnb  given in the price of `token`
        amount_out = contract_pancake.functions.getAmountsOut(
            1, [addr_token, addr_wbnb]
        ).call()[1]
        base_unit_factor = amount_out
    else:
        base_unit_factor = 1 / amount_out
    return base_unit_factor


def get_usd_on_bnb():
    """
    Gets the current price of 1 bnb in usd. Uses coinmarketcap api
    return
        (float) :   price of 1 bnb in usd
    """
    # used in quote
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    parameters = {
        "convert": "USD",
        "symbol": "BNB",
    }
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": "02675e0f-d28b-435f-8b06-e498dcb79d55",
    }
    response = None
    try:
        response = requests.get(url, headers=headers, params=parameters)
    except Exception as e:
        print(e)
    data = json.loads(response.text)
    return data["data"]["BNB"]["quote"]["USD"]["price"]
