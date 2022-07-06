import os, sys
import time, datetime
import requests
import json
import dotenv

from connect import web3

dotenv.load_dotenv()
addr_wbnb = web3.toChecksumAddress("0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c")


def wrap_data_for_sql(data):
    """
    Prepares data for sql statement by
        converting to str and
        wrapping quotes around data
    Args
        data (str or datetime)  :   pre formatted data
    Returns
        (str)                   :   formatted str
    """
    if data == "Null" or data is None:
        return "Null"
    if isinstance(data, str):
        return f'"{data}"'
    elif isinstance(data, datetime.date):
        return f"'{data.strftime('%Y-%m-%d %H:%M:%S')}'"
    else:
        print(
            f"ERROR. data type {type(data)} in wrap_data_for_sql "
            "is not accounted for"
        )


def get_now_utc_naive():
    return datetime.datetime.utcnow()


def get_now_local_naive():
    return datetime.datetime.now()


def get_abi_from_addr(addr):
    """
    gets the abi from a contract address using bscscan
    Args
        addr (str)      :   pair's contract address
    Return
        (str or bool)   :   abi string or False if bscscan exception
    """
    url = (
        "https://api.bscscan.com/api?module=contract&action=getabi"
        f"&address={addr}&apikey={os.getenv('bscscan_api')}"
    )
    response = None
    try:
        response = requests.get(url)
        return json.loads(response.text)["result"]
    except:
        return False
    finally:
        time.sleep(0.21)  # ensure less than 5 calls per second


def clear_log_file(file_name):
    """
    removes contents of the .log file of same name
    Args
        file_name (str)     :   file_name of log file with no extention
                                must refer to .log in the same directory
    """
    # takes a log file of file_name with no extention that
    # exists in the same directory

    file_path = os.path.join(sys.path[0], f"{file_name}.log")
    if os.path.exists(file_path):
        f = open(file_path, "r+")
        f.truncate(0)
