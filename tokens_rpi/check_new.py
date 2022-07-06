import time
from web3 import Web3

from connect import web3
from common import addr_wbnb, get_now_local_naive, get_now_utc_naive, clear_log_file
import common_abis
import sql_manager


def main():
    """
    check_new.py
    Collects new tokens off bsc and adds to db
    Run every 5 mins at specific minutes 4,9,14...  on rpi
        - all info from web3 on new pair (see record_token below)
        - saves statuses as Null (will later be ok/good/bad)
    """
    clear_log_file("check_new")
    local, utc = get_now_local_naive(), get_now_utc_naive()
    print(f"check: main @ local:{local} utc:{utc}")

    # contracts
    addr_pancake_factory = web3.toChecksumAddress(
        "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
    )
    contract_factory = web3.eth.contract(
        address=addr_pancake_factory, abi=common_abis.abi_uniswap
    )  # lists the new pairs and is for creating the initial pairing
    # block range
    current_block = web3.eth.get_block(block_identifier="latest")["number"]
    latest_pairs_block = get_latest_pairs_block()
    print("latest_pairs_block =", latest_pairs_block)
    gap_blocks = 20 * 5  # ~5mins because: 20blocks @ ~3sec/block = ~1min. x5 = ~5min
    # the gap should be no longer than gap_blocks
    fromBlock = current_block - gap_blocks  # assume 5mins ago
    if latest_pairs_block is not None:
        blocks_since_latest = current_block - latest_pairs_block
        if blocks_since_latest < gap_blocks:
            fromBlock = latest_pairs_block + 1
    # entries
    entries = None
    attempts_remaining = 5
    while attempts_remaining > 0 and entries is None:
        try:
            event_filter = contract_factory.events.PairCreated.createFilter(
                fromBlock=fromBlock, toBlock=current_block
            )
            entries = event_filter.get_all_entries()
        except:
            print("warning entries not found")
            time.sleep(2)
            attempts_remaining -= 1
    if entries is None:
        print("error: entries never found in 5 attempts !!")
        return
    if len(entries) == 0:
        print("no entries")
        return
    recorder_time = get_now_utc_naive()
    print(f"entries found at time {recorder_time}")
    for event in entries:
        processEvent(event, recorder_time)


def processEvent(event, recorder_time):
    """
    Performs pre-processing on the bsc event before recording in db
    Args
        event (web3.?)              :   event containing new token pair stats.
                                        type unknown as web3 has bad documentation
        recorder_time (datetime)    :   time pair was discovered (utc naive)
    """
    print("processing event")
    print("event =", event)
    # only save pair if wbnb is one of the tokens
    wbnb_upper = addr_wbnb.upper()
    token0 = event["args"]["token0"]
    token1 = event["args"]["token1"]
    is_token0_bnb = token0.upper() == wbnb_upper
    is_token1_bnb = token1.upper() == wbnb_upper
    if not (is_token0_bnb or is_token1_bnb):
        print(" event not a bnb pair")
        return  # neither are wbnb
    if is_token0_bnb:
        main_token = token1
    else:
        main_token = token0
    record_token(main_token, recorder_time, event)


def record_token(main_token, recorder_time, event):
    """
    Inserts pair into db given pre-processed event
    Args:
        main_token (str)            :   the non bnb token's address in the pair
        recorder_time (datetime)    :   time pair was discovered (utc naive)
        event (web3.?)              :   event containing new token pair stats.
                                        type unknown as web3 has bad documentation
    """
    # event detail
    pair = Web3.toJSON(event["args"]["pair"]).strip('"')
    transaction_hash = Web3.toJSON(event["transactionHash"]).strip('"')
    creator_address = Web3.toJSON(event["address"]).strip('"')
    block_hash = Web3.toJSON(event["blockHash"]).strip('"')
    block_number = event["blockNumber"]
    log_index = event["logIndex"]
    transactionIndex = event["transactionIndex"]
    unknown = event["args"][""]
    # web3 basics
    try:
        contract = web3.eth.contract(address=main_token, abi=common_abis.abi_name)
        token_name = contract.functions.name().call()
    except Exception as e:
        print("WARNING: token name could not be found")
        print(e)
        token_name = ""

    stmt = (
        "INSERT INTO tokens (main_token, recorder_time, token_name, "
        "pair, transaction_hash, creator_address, block_hash, block_number, "
        "log_index, transactionIndex, unknown) VALUES ("
        f'"{main_token}", '
        f'"{recorder_time.strftime("%Y-%m-%d %H:%M:%S")}", '
        f'"{token_name}", '
        f'"{pair}", '
        f'"{transaction_hash}", '
        f'"{creator_address}", '
        f'"{block_hash}", '
        f"{block_number}, "
        f"{log_index}, "
        f"{transactionIndex}, "
        f'"{unknown}"'
        ");"
    )
    sql_manager.Update(stmt, error="token not inserted")


def get_latest_pairs_block():
    """
    Gets latest pair's block number from the db
    Return
        (block_number)  :   block_number of latest pair
    """
    stmt = "SELECT block_number FROM tokens ORDER BY block_number DESC LIMIT 1;"
    rows = sql_manager.Select(stmt, error="no recording :(")
    if rows is None or len(rows) == 0:
        return None
    return rows[0][0]


main()
