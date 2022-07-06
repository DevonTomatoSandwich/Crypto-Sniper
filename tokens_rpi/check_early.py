import datetime
import traceback

from common import get_now_utc_naive, get_now_local_naive, clear_log_file
from token_early import TokenEarly
import sql_manager


def main():
    """
    check_early.py
    Looks for tokens in db with
      - Null early_status
      - recorded_date after 10mins ago sorted ascending
    Run every 5 mins at specific minutes 5,10,15... on rpi
    Inserts
        - early_status          :   ok or bad
        - early_status_cause    :   a000 -> a022
        - early_monitor_time    :   at updated time in utc
    """
    clear_log_file("check_early")
    local, utc = get_now_local_naive(), get_now_utc_naive()
    print(f"check: main @ local:{local} utc:{utc}")

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
    print(f"finished monitoring token @ local:{local} utc:{utc}\n")


def get_recent_tokens():
    """
    Looks for tokens in db with
      - Null early_status
      - recorded_date after 10mins ago sorted ascending
    Returns
        tokens (list)   :   list of TokenEarly, each yet to be monitored for ok/bad
    """
    now = get_now_utc_naive()
    dt_hour_ago = now - datetime.timedelta(minutes=10)
    start_str = dt_hour_ago.strftime("%Y-%m-%d %H:%M:%S")
    stmt = (
        "SELECT main_token, pair FROM tokens "
        f"WHERE recorder_time > '{start_str}' "
        "AND early_status IS NULL "
        "ORDER BY recorder_time ASC "
        # "LIMIT 50"
        ";"
    )
    rows = sql_manager.Select(stmt, error="no get_recent_tokens")
    tokens = []
    if rows is not None:
        for main_token, pair in rows:
            tokens.append(TokenEarly(main_token, pair))
    return tokens


main()
