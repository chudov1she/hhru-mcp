import socket

for p in (22, 2222, 2022):
    s = socket.socket()
    s.settimeout(6)
    print(p, ":", "OPEN" if s.connect_ex(("194.156.101.162", p)) == 0 else "closed")
    s.close()