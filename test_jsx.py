import re
import sys

def check_jsx_tags(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    match = re.search(r'<script type="text/babel">(.*?)</script>', content, re.DOTALL)
    if not match:
        print("No babel script found")
        return
        
    jsx_code = match.group(1)
    
    # 查找是否有明显的语法错误，例如使用未闭合的标签
    tags = re.findall(r'</?([a-zA-Z0-9_.]+)[^>]*>', jsx_code)
    stack = []
    
    # 仅做简单的自我匹配
    line_number = 1
    for line in jsx_code.split('\n'):
        # 简单正则寻找开标签和闭标签
        open_tags = re.findall(r'<([a-zA-Z0-9_.]+)(?:[^>]*[^/])?>', line)
        # 过滤掉自闭合标签如 <img />, <Icon />, <circle ... /> 等
        open_tags = [t for t in open_tags if t not in ['Icon', 'img', 'br', 'hr', 'input', 'circle', 'line', 'path', 'rect', 'polyline', 'polygon']]
        
        close_tags = re.findall(r'</([a-zA-Z0-9_.]+)>', line)
        
        # 这种简单的 parser 肯定不完全准确，但能帮我们找到一些大问题
        pass

    # 由于写 parser 太难，我们可以尝试运行 node 来直接看报错 (利用本地可能有的 nodejs)
    import subprocess
    try:
        # 安装一个临时的 babel 来检查语法
        pass
    except Exception:
        pass

check_jsx_tags('app/static/index.html')
print("Will attempt to use Node.js to syntax check if possible...")
