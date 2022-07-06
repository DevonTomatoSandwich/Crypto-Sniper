import os
import datetime, time
import json
import requests
import dotenv
from selenium import webdriver  #                       Scrape
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from pyvirtualdisplay import Display
from bs4 import BeautifulSoup
from gpiozero import CPUTemperature as deg  #           Temp

from connect import web3
from common import addr_wbnb, wrap_data_for_sql, get_now_utc_naive, get_abi_from_addr
import sql_manager

dotenv.load_dotenv()


class TokenMature:
    def __init__(self, main_token, pair, recorder_time, block_number, debug=False):
        self.main_token = main_token
        self.pair = pair
        self.recorder_time = recorder_time
        self.block_number = block_number
        self.debug = debug
        # sql storage
        self.good_cause = "Null"
        self.lock_expiry = "Null"
        self.lock_block = "Null"
        self.liquidity = "Null"  # for numeric types

    def monitor(self):
        """
        Filters a token for
            liquidity >= 1 wbnb
            not a rugpull (top_locked_liq_percent >=95)
            lock expiry >= 11months
        If all filters pass, token mature status set to good.
        If a filter fails, token mature status set to bad and cause is set.
        """
        self.start_timer = time.time()
        if not self.ensure_liquidity():
            return
        if not self.ensure_rugpull():
            return
        if not self.ensure_lock():
            return
        self.set_good()

    def ensure_liquidity(self):
        """
        Ensures liquidity is somewhat sufficient (liquidity >= 1 wbnb)
        Sets liquidity and contract_liquidity
        Return
            (bool)  :   True if liquidity >= 1 wbnb. Else False
        """
        abi_pair = get_abi_from_addr(self.pair)
        if abi_pair == False:  # must be falsy
            self.set_bad("a030 liquidity error retrieving abi")
            return False
        if "source code not verified" in abi_pair:
            self.set_bad("a031 liquidity contract not verified / available")
            return False
        try:
            contract_liquidity = web3.eth.contract(address=self.pair, abi=abi_pair)
        except:
            self.set_bad("a032 liquidity contract web3 error")
            return False
        try:
            liquidity = self.get_liquidity(contract_liquidity)
        except:
            self.set_bad("a033 liquidity error me in get_liquidity")
            return False
        if liquidity < 1:
            self.set_bad("a034 liquidity < 1")
            return False
        self.liquidity = liquidity
        self.contract_liquidity = contract_liquidity
        print(f" passed liquidity  deg={deg().temperature}")
        return True

    def ensure_rugpull(self):
        """
        Ensures not a rugpull (top_locked_liq_percent >= 95)
        Sets top_holder_contract_addr
        Return
            (bool)  :   True if top_locked_liq_percent >= 95. Else False
        """
        with Display(visible=0, size=(800, 600)) as disp:
            # Get driver
            browser_driver = Service("/usr/bin/chromedriver")
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            driver = webdriver.Chrome(service=browser_driver, options=chrome_options)
            # load the domain
            driver.get("https://bscscan.com/")
            cookies = {
                "bscscan_userid": os.getenv("bscscan_userid"),
                "bscscan_pwd": os.getenv("bscscan_pwd"),
                "bscscan_cookieconsent": "True",
                "bscscan_autologin": "True",
            }
            for name, value in cookies.items():
                driver.add_cookie({"name": name, "value": value})
            # soup tokenholders
            supply = self.contract_liquidity.functions.totalSupply().call()
            url_holders = (
                "https://bscscan.com/token/generic-tokenholders2?m=normal"
                f"&a={self.pair}"
                f"&s={supply}"
                "&sid=b45d3879103aaa4653236b8005d572b3"  # b45d3879103aaa4653236b8005d572b3"
                "&p=1"
            )
            if self.debug:
                print("url_holders =", url_holders)
            driver.get(url_holders)
            squadPage = driver.page_source
            soup = BeautifulSoup(squadPage, "html.parser")
            # find top holder
            trs = soup.findAll("tr")
            # print("trs =", trs)
            if len(trs) < 2:
                self.set_bad("a040 rugpull trs no tablerows")
                return False
            row_index = 1  # skip the header row 0
            top_locked_liq_percent = 0
            self.top_holder_contract_addr = None  # assumes burnt
            while True:
                # keep searching holders until an address shows up
                tr = trs[row_index]
                tds = tr.findAll("td")
                try:
                    address = tds[1].find("a")["href"].split("=")[1].strip()
                except:
                    if len(tds) == 0:
                        self.set_bad("a041 rugpull trs no data in row")
                        return False
                    if len(tds) == 1:
                        self.set_bad("a042 rugpull trs no matching entries")
                        return False
                    if tds[2].text == "0":
                        self.set_bad("a043 rugpull trs glitch quantity=0")
                        return False
                    self.set_bad("a044 rugpull trs other-error collecting address")
                    return False
                # address exists
                address_type = self.get_address_type(address)
                if address_type == "error":
                    self.set_bad("a045 rugpull other-error in get_address_type request")
                    return False
                elif address_type == "wallet":
                    # top_locked_liq_percent is now known
                    break
                else:
                    # address_type either "burnt" or "contract"
                    if row_index == 1 and address_type == "contract":
                        # this is the top contract to be used to find a lock
                        self.top_holder_contract_addr = address
                    try:
                        percent = float(tds[3].text.strip()[:-1])
                    except:
                        self.set_bad("a046 rugpull error collecting percent")
                        return False
                    top_locked_liq_percent += percent
                    if top_locked_liq_percent >= 95:
                        break
                    row_index += 1
            # finished looping through holders
            if self.debug:
                print("top_locked_liq_percent =", top_locked_liq_percent)
            if top_locked_liq_percent < 95:
                self.set_bad("a047 rugpull top_locked_liq_percent<95")
                return False
            if self.debug:
                print("self.top_holder_contract_addr =", self.top_holder_contract_addr)
            print(f" passed rugpull deg={deg().temperature}")
            return True

    def ensure_lock(self):
        """
        Ensures lock expiry id at least 11months after pair first recorded
        Sets lock_expiry, good_cause
        Return
            (bool)  :   True if lock expiry >= 11months. Else False
        """
        if self.top_holder_contract_addr is None:
            # top holder burnt, no need to check for lock
            self.good_cause = "top holder is burn"
            return True
        # self.top_holder_contract_addr is a contract
        try:
            txn_addr = self.get_lock_txn(self.top_holder_contract_addr)
            lock_dt = self.get_lock_from_txn(txn_addr)
        except:
            self.set_bad("a050 lock error in txn from top_holder_contract_addr")
            return False
        if lock_dt is None:
            # even though no locks are found
            if self.debug:
                print("lock no transactions in 100 blocks")
            self.good_cause = "lock no transactions in 100 blocks"
            return True
        # lock_dt exists
        months11 = datetime.timedelta(weeks=47)
        if lock_dt - self.recorder_time < months11:
            self.set_bad("a051 lock duration < 11months")
            return False
        self.lock_expiry = lock_dt
        if self.debug:
            print("self.lock_expiry =", self.lock_expiry)
            print("self.lock_block =", self.lock_block)
        print(f" passed lock deg={deg().temperature}")
        return True

    def get_liquidity(self, contract_liquidity):
        """
        Gets liquidity in wbnb
        Args
            contract_liquidity (web3.eth.contract)  :   liquidity pair contract
        Return
            liquidity (float)                       :   wbnb in the liquidity pool
        """
        addr_tkn = web3.toChecksumAddress(self.main_token)
        res = contract_liquidity.functions.getReserves().call()
        # two liquidites in res array are ordered in alphanumeric token address
        if addr_wbnb.lower() < addr_tkn.lower():
            return web3.fromWei(res[0], "ether")
        else:
            return web3.fromWei(res[1], "ether")

    def get_address_type(self, addr):
        """
        gets the holder address type
        Args
            addr (str)  :   holder address
        Return
            (str)       :   holder address type, either:
                            "wallet", "burnt", "contract" or "error"
        """
        if addr[:-4] == "0x000000000000000000000000000000000000":
            return "burnt"
        # used to get token holder type in _set_not_rugpull
        url = (
            "https://api.bscscan.com/api"
            "?module=contract"
            "&action=getabi"
            f"&address={addr}"
            f"&apikey={os.getenv('bscscan_api')}"
        )
        response = None
        try:
            response = requests.get(url)
            data = json.loads(response.text)
            if data["message"] == "OK" and data["status"] == "1":
                return "contract"
            else:
                return "wallet"
        except Exception as e:
            return "error"
        finally:
            time.sleep(0.21)  # ensure less than 5 calls per second

    def get_lock_txn(self, top_holder_contract_addr):
        """
        finds the transaction where the lock resides and gets the transaction's address.
        Sets lock_expiry
        Args
            top_holder_contract_addr (str)  :   address of the lp's top holder contract
                                                which should hold the lock
        Return
            (str)                           :   the lock's transaction address
        """
        # block_limit is the block at ~5min after recording assuming 3sec per block
        block_limit = self.block_number + 100
        blocks_5min = range(self.block_number, block_limit + 1)
        for i, block_num in enumerate(blocks_5min):
            print("searching for lock", i + 1, "%", end="\r")
            # check if each block's transaction to addr = top holder contract addr
            res = web3.eth.get_block(block_identifier=block_num, full_transactions=True)
            for t in res["transactions"]:
                if t["to"] is None:
                    continue
                if t["to"].lower() == top_holder_contract_addr:
                    print("found a lock at percent", i + 1, "%    ")
                    self.lock_block = i + 1
                    return t["hash"].hex()
        print("no locks found inside ~5min")
        return None

    def get_lock_from_txn(self, txn_addr):
        """
        Args
            txn_addr (str)  :   the lock's transaction address
        Return
            (datetime)      :   the lock expiry time. Or None if unknown
        """
        if txn_addr is None:
            return None
        reciept = web3.eth.get_transaction_receipt(txn_addr)
        for log in reciept["logs"]:
            log_str = "".join(log["data"])
            data_size = len(log_str) - 2
            info_size = data_size // 64
            for i in range(info_size):
                start = 64 * i + 2
                end = start + 64
                epoch = int("0x" + log_str[start:end], 0)
                try:
                    return datetime.datetime.fromtimestamp(epoch)
                except:
                    pass
        return None

    def set_bad(self, cause):
        """
        Updates the mature status to bad with related cause and time in db
        Args
            cause (str) :   cause of the bad mature status
        """
        if self.debug:
            print(f"set_bad: {cause}")
        pair = wrap_data_for_sql(self.pair)
        mature_monitor_time = wrap_data_for_sql(get_now_utc_naive())
        stmt = (
            f"UPDATE tokens SET mature_status='bad', mature_status_cause='{cause}', "
            f"mature_monitor_time={mature_monitor_time} WHERE pair={pair}"
        )
        sql_manager.Update(stmt, error="token not UPDATEd bad")

    def set_good(self):
        """
        Updates the mature status to good and other stats:
            liquidity, lock_expiry, lock_block
        """
        pair = wrap_data_for_sql(self.pair)
        mature_status_cause = wrap_data_for_sql(self.good_cause)
        mature_monitor_time = wrap_data_for_sql(get_now_utc_naive())
        lock_expiry = wrap_data_for_sql(self.lock_expiry)
        stmt = (
            "UPDATE tokens SET "
            f"mature_status='good', "
            f"mature_status_cause={mature_status_cause}, "
            f"mature_monitor_time={mature_monitor_time}, "
            f"liquidity={self.liquidity}, "
            f"lock_expiry={lock_expiry}, "
            f"lock_block={self.lock_block} "
            "WHERE "
            f"pair = {pair}"
        )
        sql_manager.Update(stmt, error="token not UPDATEd good")
