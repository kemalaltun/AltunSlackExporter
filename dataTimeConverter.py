import datetime

dt = datetime.datetime(2025, 7, 29, 15, 0, 0)  # istediğin tarihi yaz
ts = dt.timestamp()
print(f"{ts:.6f}")  # 1722363600.000000 gibi