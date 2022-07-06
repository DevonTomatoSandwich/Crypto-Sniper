import os
import traceback
import mysql.connector as MySQLdb
import dotenv

dotenv.load_dotenv()
connection = None


def Connect():
    """
    Connects to a SQL database using config variables.
    Overwrites any existing connection
    Returns
        (bool)  :   True if new connection is made
                    Or False if exception during new connection
    """
    global connection
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
        rows = cur.fetchall()
        return rows
    except:
        print(stmt)
        traceback.print_exc()
    finally:
        if not Disconnect():
            print(f"Warning: not disconnected, {error}")


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
    finally:
        if not Disconnect():
            print(f"Warning: not disconnected, {error}")


def Disconnect():
    """
    Disconnects from SQL database. Connection will always
    be set to None. Connection will close first if existing.
    Returns
        (bool)  :   True if connection is closed
                    Or False if exception during connection close
    """
    global connection
    try:
        connection.close()
    except Exception as e:
        print(e)
        return False
    finally:
        connection = None
    return True
