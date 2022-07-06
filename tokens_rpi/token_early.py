import os
import requests
import json
import time
import dotenv

import sql_manager
from connect import web3
from common import wrap_data_for_sql, get_now_utc_naive

dotenv.load_dotenv()


class TokenEarly:
    def __init__(self, main_token, pair, debug=False):
        self.main_token = main_token
        self.pair = pair
        self.debug = debug

    def monitor(self):
        """
        Filters a token for
            is_verified
            is_not_proxy
            honeypot
            is_ownership_renounced
        If all filters pass, token early status set to ok.
        If a filter fails, token status set to bad and cause is set.
        """
        start_timer = time.time()
        # ensures is verified and is not proxy
        if not self.ensure_contract():
            print(f"bad duration {format(time.time() - start_timer, '.3f')}")
            return
        print(" passed contract")
        # ensures not honeypot
        if not self.ensure_honeypot():
            print(f"bad duration {format(time.time() - start_timer, '.3f')}")
            return
        print(" passed honeypot")
        # ensures ownership renounced
        if not self.ensure_renounced():
            print(f"bad duration {format(time.time() - start_timer, '.3f')}")
            return
        print(" passed renounced")
        # token must be ok
        self.set_ok()
        print(f"ok duration {format(time.time() - start_timer, '.3f')}")

    def ensure_contract(self):
        """
        Ensures contract is verified and not a proxy
        Sets source_code and abi
        Return
            (bool)  :   True if verified and not proxy. Else False
        """
        url = (
            "https://api.bscscan.com/api?module=contract&action=getsourcecode"
            f"&address={self.main_token}&apikey={os.getenv('bscscan_api')}"
        )
        try:
            data = json.loads(requests.get(url).text)
        except Exception as e:
            print(f"Error caught requesting contract from bscscan: {e}")
            self.set_bad("a001 contract request")
            return False
        if not (data["message"] == "OK" and data["status"] == "1"):
            print(f"Error in message/status of contract from bscscan: {e}")
            self.set_bad("a002 contract message/status")
            return False
        # assume there is one contract object in the results
        contract = data["result"][0]
        if "source code not verified" in contract["ABI"]:
            self.set_bad("a003 contract unverified")
            return False
        if contract["Proxy"] == "1":
            self.set_bad("a004 contract proxy")
            return False
        self.source_code = contract["SourceCode"]
        self.abi = contract["ABI"]
        time.sleep(0.21)  # ensure less than 5 calls per second
        return True

    def ensure_honeypot(self):
        """
        Ensures contract is not a honeypot
        Return
            (bool)  :   True if type="OK" else False. all types are:
            0, "UNKNOWN": "The status of this token is unknown. This is usually a system error but could also be a bad sign for the token. Be careful."
            1, "OK": "Honeypot tests passed. Our program was able to buy and sell it succesfully. This however does not guarantee that it is not a honeypot."
            0, "NO_PAIRS": "Could not find any trading pair for this token on the default router and could thus not test it."
            0, "SEVERE_FEE": "severely high trading fee (over 50%) was detected when selling or buying this token."
            0, "HIGH_FEE": "A high trading fee (Between 20% and 50%) was detected when selling or buying this token. Our system was however able to sell the token again."
            0, "MEDIUM_FEE": "A trading fee of over 10% but less then 20% was detected when selling or buying this token. Our system was however able to sell the token again."
            0, "APPROVE_FAILED": "Failed to approve the token. This is very likely a honeypot"
            0, "SWAP_FAILED": "Failed to sell the token. This is very likely a honeypot"
        """
        url = (
            "https://honeypot.api.rugdoc.io/api/honeypotStatus.js?"
            f"address={self.main_token}&chain=bsc"
        )
        try:
            response = requests.get(url)
        except Exception as e:
            print(f"Error requesting honeypotStatus {e}")
            self.set_bad("a010 failed honeypot request")
            return False
        data = json.loads(response.text)
        if (
            "error" in data
            and "data" in data["error"]
            and data["error"]["data"] is None
        ):
            self.set_bad("a011 honeypot likely unsellable")
            return False
        if "status" not in data:
            self.set_bad("a012 no honeypot status key")
            return False
        if data["status"] != "OK":
            self.set_bad(f"a012 honeypot status: {data['status']}")
            return False
        return True

    def ensure_renounced(self):
        """
        Ensures contract ownership is renounced
        Return
            (bool)  :   True if contract ownership is renounced. Else False
        """
        if "modifier" not in self.source_code:
            # you don't have to check for ownership if there are no modifiers
            return True
        # a modifier exists, get the msg_sender (a var or function)
        msg_sender = None
        is_check_line = False
        lines = self.source_code.split("\n")
        for line in lines:
            if is_check_line:
                if "}" in line:
                    is_check_line = False
                    continue
                msg_sender = self.get_msg_sender(line)
                if msg_sender is not None:
                    break
            if "modifier " in line and "{" in line:
                # this modifier line is most likely a function check the lines beneath
                is_check_line = True
        if msg_sender is None:
            # no modifier specific to owner
            return True
        # msg_sender exists !
        # get contract
        try:
            contract_token = web3.eth.contract(address=self.main_token, abi=self.abi)
        except:
            self.set_bad("a023 not renounced contract_token creation fail")
            return False
        # msg_sender is either a var or function
        print("msg_sender", msg_sender)
        if msg_sender[-1:] == ")":
            # msg_sender is a function ending in "*(*)"
            owner_method_name = msg_sender.split("(")[0].strip()
            # owner_addr = get_owner_from_method_name(owner_method_name)
            try:
                owner_addr = contract_token.get_function_by_name(
                    owner_method_name
                )().call()
            except:
                # the method is internal, it may have a getter-getter
                # a contract with a getter for a getter is shit code and
                # should be banished lol
                self.set_bad(
                    "a024 not renounced the owner getter is internal, code banished"
                )
                return False
        else:
            # msg_sender is a variable
            # try to see if the variable is external
            try:
                owner_addr = contract_token.get_function_by_name(msg_sender)().call()
            except:
                # the variable is internal, try to find its getter
                owner_method_name = ""
                try:
                    is_getter_found = False
                    for i, line in enumerate(lines):
                        # find the return of the getter
                        if f"return {msg_sender}" in line:
                            getter_line = lines[i - 1].strip()
                            owner_method_name = getter_line.split(" ")[1][:-2]
                            print("owner_method_name", owner_method_name)
                            owner_addr = contract_token.get_function_by_name(
                                owner_method_name
                            )().call()
                            is_getter_found = True
                            break
                    if not is_getter_found:
                        # there is no way to access this variable
                        self.set_bad("a023 not renounced no public getter for owner")
                        return False
                except:
                    print(
                        "failed to get getter with owner_method_name =",
                        owner_method_name,
                    )
                    self.set_bad("a021 not renounced error retrieving getter")
                    return False
        # owner_addr exists
        print("owner_addr", owner_addr)
        if owner_addr[:-4] != "0x000000000000000000000000000000000000":
            # wallet (not burnt or dead)
            self.set_bad("a022 not renounced owner is wallet")
            return False
        return True

    def get_msg_sender(self, line):
        """
        Checks the modifier line to see if it is an owner modifier
        and if so returns the owner name or method
        Args
            line (str)  :   the line of a contract's source code within a modifier
        Return
            (str)       :   The owner name or method. Or None if not an owner modifier
        """
        if "msg.sender" in line:
            if "msg.sender ==" in line:
                right_of_eq = line.split("==")[1]
                count_till_closed = 1  # ')' needed till stop
                for i, char in enumerate(right_of_eq):
                    if char == ",":
                        break
                    if char == ")":
                        if count_till_closed == 1:
                            break
                        if count_till_closed > 1:
                            count_till_closed -= 1
                    if char == "(":
                        count_till_closed += 1
                return right_of_eq[:i].strip()
            if "== msg.sender" in line:
                left_of_eq = line.split("==")[0].strip()
                count_till_closed = 1  # '(' needed till stop
                size = len(left_of_eq)  # 7
                # print('size', size)
                for i in range(size - 1, -1, -1):  # 6, 5, ...1
                    char = left_of_eq[i]
                    # print("  ", i, 'char=', char)
                    if char == "(":
                        if count_till_closed == 1:
                            break
                        if count_till_closed > 1:
                            count_till_closed -= 1
                    if char == ")":
                        count_till_closed += 1
                return left_of_eq[i + 1 :].strip()
            return None  # no "==" found
        return None  # no "msg.sender" found

    def set_bad(self, cause):
        """
        Updates the early status to bad with related cause in db
        Args
            cause (str) :   cause of the bad early status
        """
        if self.debug:
            print(f"set_bad: {cause}")
        pair = wrap_data_for_sql(self.pair)
        early_monitor_time = wrap_data_for_sql(get_now_utc_naive())
        stmt = (
            f"UPDATE tokens SET early_status = 'bad', early_status_cause='{cause}', "
            f"early_monitor_time={early_monitor_time} WHERE pair={pair}"
        )
        sql_manager.Update(stmt, error="token not UPDATEd bad")

    def set_ok(self):
        """
        Updates the early status to ok
        """
        pair = wrap_data_for_sql(self.pair)
        early_monitor_time = wrap_data_for_sql(get_now_utc_naive())
        stmt = (
            "UPDATE tokens SET early_status='ok', early_status_cause=Null, "
            f"early_monitor_time={early_monitor_time} WHERE pair={pair}"
        )
        sql_manager.Update(stmt, error="token not UPDATEd ok")
