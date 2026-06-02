import re

with open('app/static/index.html', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    # 打印 1145 到 1160 行
    if 1145 <= i <= 1155:
        print(f"{i+1}: {line.rstrip()}")
    # 打印 1615 到 1630 行
    if 1615 <= i <= 1630:
        print(f"{i+1}: {line.rstrip()}")
    # 打印 2245 到 2260 行
    if 2245 <= i <= 2260:
        print(f"{i+1}: {line.rstrip()}")
    # 打印 2470 到 2480 行
    if 2470 <= i <= 2480:
        print(f"{i+1}: {line.rstrip()}")

