import os, sys
import matplotlib.pyplot as plt

root_folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(1, f"{root_folder}/client")

import sql_manager


def main():
    """
    python3 extras/lock_block_plot.py
    plots the number of times a lock is found for a certain block
    xaxis has each block 0->100 from a token's first recorded block
    """
    blocks = get_blocks()
    print(len(blocks))
    # histogram
    x = [n for n in range(0, 101)]
    y = [0 for _ in range(0, 101)]
    for block in blocks:
        y[block] += 1
    plt.plot(x, y)
    plt.show()


def get_blocks():
    stmt = "SELECT lock_block FROM tokens WHERE lock_block is not Null;"
    sql_rows = sql_manager.Select(stmt, error="no plot :(")
    blocks = []
    for (block,) in sql_rows:
        blocks.append(block)
    return blocks


main()
