import subprocess
from common import get_now_local_naive


def main():
    """
    Looks for amount of used space on a disk
    Run every 6 hours on the hour starting midnight on rpi
    Reboots if used space is over 95% (to clear memory)
    """
    now = get_now_local_naive().strftime("%Y-%m-%d %H:%M:%S")
    print(f"checking at local time: {now}")
    space = get_space_used()
    if space is not None and space > 95:
        reboot(now)


def get_space_used():
    """
    Return
        (int)   :   Percent of used space on the dev/root disk device.
                    Or None if no output (rare)
    """
    result = subprocess.run(["df", "-h"], stdout=subprocess.PIPE)
    data = result.stdout.decode("utf-8")
    for line in data.split("\n"):
        if line[:9] == "/dev/root":
            for item in line.split(" "):
                if "%" in item:
                    return int(item[:-1])
    return None


def reboot(time_str):
    """
    Reboots the pi
    Args:
        time_str (str)  :   local naive time string
    """
    print(f"  REBOOTING at {time_str}\n")
    subprocess.run(["sudo", "reboot"])


main()
