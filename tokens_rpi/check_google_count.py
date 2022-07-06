import os
import json
import requests
import dotenv

from common import wrap_data_for_sql, get_now_local_naive
import sql_manager

dotenv.load_dotenv()


def main():
    """
    check_google_count.py
    Looks for oldest 1 token in db with
        - status good
        - google_results_count Null
    Run every 15 mins on the hour
    Updates the token's google_results_count
    """
    now = get_now_local_naive()
    dt_str = now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"Google Check at local: {dt_str}")

    token_rows = get_tokens()
    if token_rows is None:
        return

    main_token, pair, token_name = token_rows[0]
    print(f" found token with no count, name: {token_name}")
    count = get_google_results_count(main_token)
    print(" ", count)
    if count is not None:
        set_google_results_count(pair, count)


def get_google_results_count(search_text):
    """
    Gets the count of google search results for the search text
    Args
        search_text     :   the text used in the google search
    Return
        (int)           :   count of google search results
    """
    url = (
        f"https://www.googleapis.com/customsearch/v1?key={os.getenv('google_api_key')}"
        f"&cx={os.getenv('google_engine_id')}"
        f"&q={search_text}&alt=json&fields=queries(request(totalResults))"
    )
    response = None
    try:
        response = requests.get(url)
        data = json.loads(response.text)
        return int(data["queries"]["request"][0]["totalResults"])
    except Exception as e:
        print(f"Error in get_google_results_count. {e}")
    return 0


def set_google_results_count(pair, google_results_count):
    """
    Updates google_results_count in the db.
    Args:
        pair (str)                  :   the liquidity pair contract address
        google_results_count (int)  :   count of google search results
    """
    print("set_google_results_count", google_results_count)

    pair = wrap_data_for_sql(pair)
    stmt = (
        "UPDATE tokens SET "
        f"google_results_count={google_results_count} "
        "WHERE "
        f"pair={pair}"
        ";"
    )
    sql_manager.Update(stmt, error="set_google_results_count not UPDATEd")


def get_tokens():
    """
    Looks for oldest 1 token in db with
        - status good
        - google_results_count Null
    """
    stmt = (
        "SELECT main_token, pair, token_name "
        "FROM tokens "
        "WHERE mature_status='good' and google_results_count is Null "
        # f"and recorder_time < '{str_10min_ago}' "
        "ORDER BY recorder_time asc "
        "LIMIT 1 "
        ";"
    )
    rows = sql_manager.Select(stmt, error="no goods")
    return rows


main()
