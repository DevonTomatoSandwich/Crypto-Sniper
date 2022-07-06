import os
import traceback
import mariadb as MySQLdb
import dotenv

dotenv.load_dotenv()
connection = None


def Connect():
    """
    Connects to a SQL database using config variables.
    If a connection is already made, does not attempt to connect
    Returns
        (bool)  :   True if previous connection active or currently connected.
                    Or False if exception during connection
    """
    global connection
    if connection is None:
        try:
            connection = MySQLdb.connect(
                host=os.getenv("sql_host"),
                user=os.getenv("sql_user"),
                passwd=os.getenv("sql_pass"),
                db=os.getenv("sql_db"),
            )
        except Exception as e:
            print(e)
            print(os.getenv("sql_host"), os.getenv("sql_user"), os.getenv("sql_db"))
            return False
    return True


def Select(stmt, error=""):
    """
    Simulates a sql select statement and returns sql rows
    Args
        stmt (str)  :   SQL select statement string
        error (str) :   error to show if connecting fails
    Return
        (list)      :   list of lists representing sql rows
                        Or None if connecting fails
    """
    if not Connect():
        print(f"ERROR: not connected, {error}")
        return
    try:
        cur = connection.cursor()
        cur.execute(stmt)
        return cur.fetchall()
    except:
        print(stmt)
        traceback.print_exc()


def Update(stmt, error=""):
    """
    Simulates a sql update or insert statement
    Args
        stmt (str)  :   SQL statement string (any execpt select)
        error (str) :   error to show if connecting fails
    Return
        (bool)      :   True if query success
                        Or None if connecting fails or query fails
    """
    if not Connect():
        print(f"ERROR: not connected, {error}")
        return
    try:
        cur = connection.cursor()
        cur.execute(stmt)
        connection.commit()
        return True
    except:
        print(stmt)
        traceback.print_exc()
