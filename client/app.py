from flask import Flask, request, render_template, redirect, url_for, flash, Markup
import os
import json
import pytz
import dotenv

import buy as buy_module
import sql_manager

dotenv.load_dotenv()
client_folder = os.path.dirname(os.path.abspath(__file__))

##################
## To run the Flask server use cmd:
## $ python client/app.py
##################

app = Flask(__name__)

# A secret key is only needed in this app to securely send flash
# messages to a user. Since transaction reciepts are sent in flash,
# the key may need to be somewhat secret
app.secret_key = os.getenv("secret_key")


state = {
    "all_matrix": None,  # list of each sql row
    "info_row": None,  # list of data to display for the selected row
    "causes": None,  # list of all causes from markbad.json
    "initialized": False,  # True if & only if all_matrix state is initialised
}


@app.route("/", methods=["GET", "POST"])
def home():
    # refreshes the All Tokens table and renders the template
    print("home")
    refresh_all_tokens()
    return render_template("index.html", state=state)


@app.route("/token_click/<n>/<gc>/<mt>/<p>/<rt>/<ms>/<l>", methods=["GET", "POST"])
def token_click(n, gc, mt, p, rt, ms, l):
    """
    Displays more specific token data in Token Info section
    Params:
        n  (str)    : token name
        gc (str)    : google count
        mt (str)    : main token
        p  (str)    : pair
        rt (str)    : recrder time
        ms (str)    : mature status cause
        l  (str)    : liquidity
    """
    print("token_click")
    if request.method == "POST" or state["initialized"] is False:
        refresh_all_tokens()
    state["info_row"] = [n, gc, mt, p, rt, ms, l]
    return render_template("index.html", state=state)


@app.route("/markbad", methods=["POST"])
def markbad():
    """
    Updates the token in the database setting the mature status to bad
    with a cause. Removes the currently marked bad token in All Tokens table,
    removes selected token from Token Info table, removes the bad token from url,
    displays a flash message at the top indicating the action performed,
    and shows updated tokens in All Tokens table. Route is fired on confirming
    the alert to mark a token bad.
    Params
        cause (str) :   the reason why a token is manually marked as bad
    """
    print(f"markbad")
    cause = request.form["cause"]
    pair = state["info_row"][3]
    stmt = (
        f"UPDATE tokens SET mature_status='bad', mature_status_cause='{cause}' "
        f"WHERE pair='{pair}'"
    )
    sql_manager.Update(stmt, error="token not UPDATEd as a bad marker")
    name = state["info_row"][0]
    flash(f" token {name} was marked bad with reason: {cause}", "info")
    return redirect(url_for("home"))


@app.route("/quote", methods=["POST"])
def quote():
    """
    Gives data suffient for a quote to buy. Fired when buy button is clicked
    Params
        usd (str)   :   usd of token to be bought
        gas (str)   :   gas price in gwei
        hrs (str)   :   hours from now till deadline
    Return
        (str)       :   json string see buy_module.quote for all keys
    """
    print("quote")
    name = state["info_row"][0]
    addr = state["info_row"][2]
    usd = float(request.form["usd"])
    gas = float(request.form["gas"])
    hrs = float(request.form["hrs"])
    return buy_module.quote(name, addr, usd, gas, hrs)


@app.route("/buy", methods=["POST"])
def buy():
    """
    Confirms purchase and displays the receipt with a transaction hex. A link
    to the transaction on bscscan is included. Route is fired on confirming
    the quote alert to buy.
    Params
        deadline (str)  :   deadline epoch
        bnb (str)       :   bnb to spend on token (in ether)
        gas (str)       :   gas price in gwei
        gas_limit (str) :   number of gas units to use
    """
    print("buy")
    addr = state["info_row"][2]
    deadline = int(request.form["deadline"])
    bnb = float(request.form["bnb"])
    gas = float(request.form["gas"])
    gas_limit = int(request.form["gas_limit"])
    txn_hex = buy_module.buy(addr, deadline, bnb, gas, gas_limit)
    if txn_hex == "error":
        msg = "There was an unknown error with the purchase"
    else:
        msg = Markup(
            f"Transaction sent. Check success at transaction address: {txn_hex}\n"
            f'Or <a href="https://bscscan.com/tx/{txn_hex}" target="_blank"> open on bscscan here </a>'
        )
    flash(msg, "info")
    return redirect(url_for("home"))


"""
    Other non route methods
"""


def refresh_all_tokens():
    """
    Retrieves the 300 most recent tokens with good mature status for display
    in the All Tokens table. New tokens are saved in state along with
    initialisation and token count.
    """
    stmt = (
        "SELECT token_name, google_results_count, main_token, pair, recorder_time, mature_status_cause, liquidity "
        "FROM tokens "
        "WHERE mature_status='good' "
        "ORDER BY recorder_time desc "
        "LIMIT 300 "
        ";"
    )
    sql_rows = sql_manager.Select(stmt, "matrix wont be set")
    rows = []
    tz_local = pytz.timezone(os.getenv("pytz_local_tz"))
    for row in sql_rows:
        dt_utc_naive = row[4]
        dt_utc_aware = pytz.utc.localize(dt_utc_naive)
        dt_local_aware = dt_utc_aware.astimezone(tz_local)
        row = list(row)
        row[4] = dt_local_aware
        rows.append(row)
    state["all_matrix"] = rows
    state["all_matrix_count"] = len(rows)
    state["initialized"] = True


def set_causes_cause():
    # Sets the causes state to be used in Mark Bad. Causes are loaded from .json
    with open(f"{client_folder}/markbad.json", "r") as json_file:
        data = json.load(json_file)
    causes = data["causes"]
    state["causes"] = causes


if __name__ == "__main__":
    set_causes_cause()
    app.run(debug=True, host="localhost")
