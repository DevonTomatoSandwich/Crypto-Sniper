import sql_manager

from connect import web3
from common import (
    addr_wbnb,
    wrap_data_for_sql,
    get_abi_from_addr,
    get_now_local_naive,
    get_now_utc_naive,
)


def main():
    """
    Looks for tokens in db with
        - good mature_status
        - most recent
    Run every 5 mins at specific minutes 4,9,14... on rpi
    Sets mature status bad for
        pairs with less than 3wbnb in liquidity
    """
    local, utc = get_now_local_naive(), get_now_utc_naive()
    print(f"check: main @ local:{local} utc:{utc}")
    tokens_rows = get_goods()
    for i, (token_name, main_token, pair) in enumerate(tokens_rows):
        res = ensure_liquidity(pair, main_token)
        if res == False:
            # failed to check liquidity for some reason
            # the coin is already marked as bad
            continue
        if res < 3:
            print(i, token_name, res)
            set_bad("a998 post rugpull from check_liquidity.py", pair)


def set_bad(cause, pair):
    """
    Updates the mature status to bad with related cause in db
    Args
        cause (str) :   cause of the bad mature status
        pair  (str) :   address of the liquidity pair contract
    """
    pair = wrap_data_for_sql(pair)
    stmt = (
        f"UPDATE tokens SET mature_status='bad', mature_status_cause='{cause}' "
        f"WHERE pair={pair}"
    )
    sql_manager.Update(stmt, error="token not UPDATEd bad")


def ensure_liquidity(pair, main_token):
    """
    Gets liquidity or sets bad status trying
    Args
        pair        (str)   :   address of the liquidity pair contract
        main_token  (str)   :   address of the main token contract
    Return
        liquidity (float)   :   wbnb in the liquidity pool
    """
    abi_pair = get_abi_from_addr(pair)
    if abi_pair == False:  # must be falsy
        set_bad("a030 liquidity error retrieving abi", pair)
        return False
    if "source code not verified" in abi_pair:
        set_bad("a031 liquidity contract not verified / available", pair)
        return False
    try:
        contract_liquidity = web3.eth.contract(address=pair, abi=abi_pair)
    except:
        set_bad("a032 liquidity contract web3 error", pair)
        return False
    try:
        liquidity = get_liquidity(contract_liquidity, main_token)
    except:
        set_bad("a033 liquidity error me in get_liquidity", pair)
        return False
    return liquidity


def get_liquidity(contract_liquidity, main_token):
    """
    Gets liquidity in wbnb
    Args
        contract_liquidity (web3.eth.contract)  :   liquidity pair contract
        main_token  (str)                       :   address of the main token contract
    Return
        liquidity (float)                       :   wbnb in the liquidity pool
    """
    addr_tkn = web3.toChecksumAddress(main_token)
    res = contract_liquidity.functions.getReserves().call()
    # two liquidites in res array are ordered in alphanumeric token address
    if addr_wbnb.lower() < addr_tkn.lower():
        return web3.fromWei(res[0], "ether")
    else:
        return web3.fromWei(res[1], "ether")


def get_goods():
    """
    Looks for tokens in db with
        - good mature_status
        - most recent
    Return
        rows (list)   :   list of good token properties (token_name, main_token, pair)
    """
    stmt = (
        "SELECT token_name, main_token, pair "
        "FROM tokens "
        "WHERE mature_status='good' "
        "ORDER BY recorder_time desc "
        ";"
    )
    rows = sql_manager.Select(stmt, error="no goods")
    return rows


main()
