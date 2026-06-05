import re

with open("app/api/server.py", "r") as f:
    content = f.read()

# 1. Add imports at the top
imports = """
from app.api.auth import get_tenant_workspace
from fastapi import Depends, Request
"""
content = content.replace("from fastapi.responses import StreamingResponse", "from fastapi.responses import StreamingResponse\n" + imports)

# 2. Add get_task_service and globals
task_service_logic = """
_tenant_services = {}
_test_service = None

def get_task_service(tenant_id: str = Depends(get_tenant_workspace)):
    if _test_service:
        return _test_service
    if tenant_id not in _tenant_services:
        import tempfile
        from pathlib import Path
        base_dir = Path(tempfile.gettempdir()) / "manual-agent-phase1" / tenant_id
        _tenant_services[tenant_id] = build_default_task_service(base_dir)
    return _tenant_services[tenant_id]
"""
content = content.replace("def create_app(task_service: TaskService | None = None):", task_service_logic + "\n\ndef create_app(task_service: TaskService | None = None):")

# 3. Setup test service
create_app_start = """def create_app(task_service: TaskService | None = None):
    global _test_service
    if task_service:
        _test_service = task_service
"""
content = re.sub(r"def create_app\(task_service: TaskService \| None = None\):\n    if FastAPI is None:", create_app_start + "    if FastAPI is None:", content)

# 4. Remove old service = 
content = content.replace("service = task_service or build_default_task_service()", "")

# 5. Add Depends to all routes
def replace_route(match):
    decorator = match.group(1)
    func_name = match.group(2)
    args = match.group(3)
    ret = match.group(4)
    
    if args.strip() == "":
        new_args = "service: TaskService = Depends(get_task_service)"
    else:
        new_args = args + ", service: TaskService = Depends(get_task_service)"
        
    return f"{decorator}\n    async def {func_name}({new_args}) {ret}"

# We need to match @app... \n def ...
content = re.sub(r"(@app\.[a-z]+\(.*?\))\n\s+def ([a-zA-Z0-9_]+)\((.*?)\) (-> .*?:)", replace_route, content)

# Wait, some routes are async def
def replace_async_route(match):
    decorator = match.group(1)
    func_name = match.group(2)
    args = match.group(3)
    
    if args.strip() == "":
        new_args = "service: TaskService = Depends(get_task_service)"
    else:
        new_args = args + ", service: TaskService = Depends(get_task_service)"
        
    return f"{decorator}\n    async def {func_name}({new_args}):"

content = re.sub(r"(@app\.[a-z]+\(.*?\))\n\s+async def ([a-zA-Z0-9_]+)\((.*?)\):", replace_async_route, content)

# 6. Replace intercept logic
frustration_logic_1 = """        import re
        frustration_patterns = [r'(?i)wtf', r'(?i)not working', r'(?i)fails again', r'(?i)fuck', r'(?i)糟糕', r'(?i)根本不行', r'(?i)又失败了']
        user_text = request.decision or ""
        if any(re.search(p, user_text) for p in frustration_patterns):
            request.decision = user_text + "\\n[System: 用户情绪受挫。请暂停盲目重试，微调沟通姿态，先安抚并提供 step-by-step 的澄清引导，找出卡点所在。]"
"""
new_frustration_1 = """        from app.cli.utils import intercept_user_emotion
        request.decision = intercept_user_emotion(request.decision or "")
"""
content = content.replace(frustration_logic_1, new_frustration_1)

frustration_logic_2 = """    import re
    frustration_patterns = [r'(?i)wtf', r'(?i)not working', r'(?i)fails again', r'(?i)fuck', r'(?i)糟糕', r'(?i)根本不行', r'(?i)又失败了']
    if any(re.search(p, prompt) for p in frustration_patterns):
        prompt += "\\n[System: 用户情绪受挫。请微调沟通姿态，先安抚并提供 step-by-step 的澄清引导，找出卡点所在。]"
        if "prompt" in payload: payload["prompt"] = prompt
        elif "goal" in payload: payload["goal"] = prompt
        elif "business_goal" in payload: payload["business_goal"] = prompt"""

new_frustration_2 = """    from app.cli.utils import intercept_user_emotion
    new_prompt = intercept_user_emotion(prompt)
    if new_prompt != prompt:
        prompt = new_prompt
        if "prompt" in payload: payload["prompt"] = prompt
        elif "goal" in payload: payload["goal"] = prompt
        elif "business_goal" in payload: payload["business_goal"] = prompt"""
content = content.replace(frustration_logic_2, new_frustration_2)

with open("app/api/server.py", "w") as f:
    f.write(content)

