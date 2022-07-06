import os

"""
generate the .env files
python3 generate_dotenvs.py
"""

root_folder = os.path.dirname(os.path.abspath(__file__))

with open(f"{root_folder}/client/.env", "w") as outfile:
    outfile.write(
        """# remember to reboot server after editing

# if is_dev_buy is true (case insensitive), the purchase 
# will not go through and will return a fake reciept
# set as false for prod environment
is_dev_buy = true

# A secret key is only needed in this app to securely send flash
# messages to a user. Since transaction reciepts are sent in flash,
# the key may need to be somewhat secret
secret_key = "TODO_REPLACE"

personal_bnb_addr = "TODO_REPLACE"
private = "TODO_REPLACE WITH METAMASK PASSWORD"
pytz_local_tz = "TODO_REPLACE options: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"

sql_host = "TODO_REPLACE"
sql_user = "piuser"
sql_pass = "TODO_REPLACE"
sql_db = "crypto"

backup_folder = "TODO_REPLACE"    
"""
    )


with open(f"{root_folder}/tokens_rpi/.env", "w") as outfile:
    outfile.write(
        """# bscscan
bscscan_api = "TODO_REPLACE"
bscscan_userid = "TODO_REPLACE"
bscscan_pwd = "TODO_REPLACE"
 
# sql
sql_host = "localhost"
sql_user = "piuser"
sql_pass = "TODO_REPLACE"
sql_db = "crypto"

# google
google_api_key = "TODO_REPLACE"
google_engine_id = "TODO_REPLACE"
"""
    )
