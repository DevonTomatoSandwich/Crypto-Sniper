import os, sys
import csv
import datetime
import dotenv

root_folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(1, f"{root_folder}/client")

import sql_manager

"""
python3 extras/backup_tokens_to_csv.py
saves all rows in the tokens table to csv
the new csv file is created in os.getenv("backup_folder")
"""
dotenv.load_dotenv("../client/.env")


def main():
    print("start")
    rows = get_all_rows()
    print("all rows fetched from db")

    # encode characters
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            try:
                rows[i][j] = value.encode("ascii", "ignore")
            except:
                pass
    print("all rows encoded to ascii")

    day_str = get_now_local_naive().strftime("%Y%m%d")
    out_path = f"{os.getenv('backup_folder')}/tokens{day_str}.csv"
    with open(out_path, "w") as file:
        f = csv.writer(file)
        size = len(rows)
        for i, row in enumerate(rows):
            if i % 1000 == 0:
                print(i, "/", size, end="\r")
            f.writerow(row)
        print(size, "/", size)
    print("fin")


def get_all_rows():
    stmt = "SELECT * from tokens;"
    rows = sql_manager.Select(stmt, error="selecting all for csv backup")
    return rows


def get_now_local_naive():
    return datetime.datetime.now()


main()
