import datetime
import traceback
from gpiozero import CPUTemperature as deg

from common import get_now_utc_naive, get_now_local_naive, clear_log_file
from token_mature import TokenMature
import sql_manager


def main():
    """
    check_mature.py
    Looks for tokens in db with
      - ok early_status
      - recorder_time before 10mins ago
      - 10 oldest tokens
    Run every 5 mins at specific minutes 1,6,11... on rpi
    Inserts
        - mature_status          :   ok or bad
        - mature_status_cause    :   a000 -> a052
        - mature_monitor_time    :   at finish insert utc
        - and other stats like: liquidity, lock_expiry & lock_block
    """
    clear_log_file("check_mature")
    local, utc = get_now_local_naive(), get_now_utc_naive()
    print(f"check: main @ local:{local} utc:{utc} deg={deg().temperature}")

    tokens = get_recent_tokens()

    for i, token in enumerate(tokens):
        print(f"start monitoring token {i+1} of {len(tokens)} pair:{token.pair}")
        try:
            token.monitor()
        except:
            print(
                "exception found in monitor. Script will continue monitoring. "
                "The error is:"
            )
            traceback.print_exc()
    local, utc = get_now_local_naive(), get_now_utc_naive()
    print(
        f"finished monitoring token @ local:{local} utc:{utc} deg={deg().temperature}\n"
    )


def get_recent_tokens():
    """
    Looks for tokens in db with
      - ok early_status
      - recorder_time before 10mins ago
      - 10 oldest tokens
    Return
        tokens (list)   :   list of TokenMature, each yet to be monitored for good/bad
    """
    now = get_now_utc_naive()
    tenminsago = (now - datetime.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    stmt = (
        "SELECT main_token, pair, recorder_time, block_number FROM tokens "
        "WHERE early_status='ok' AND mature_status is Null AND "
        f"recorder_time < '{tenminsago}' "
        "ORDER BY recorder_time ASC "
        "LIMIT 10"
        ";"
    )
    rows = sql_manager.Select(stmt, error="no monitoring :(")
    tokens = []
    if rows is not None:
        for main_token, pair, recorder_time, block_number in rows:
            tokens.append(
                TokenMature(
                    main_token,
                    pair,
                    recorder_time,
                    block_number,
                    debug=True,
                )
            )
    return tokens


main()
