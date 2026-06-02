import requests
import json
import time
import os
import glob

# 找到一个 task_id
tasks = requests.get('http://127.0.0.1:8000/api/tasks').json().get("tasks", [])
if not tasks:
    print("No tasks found")
    exit()
task = tasks[0]
task_id = task["id"]
print(f"Testing task: {task_id}, status: {task['status']}, raw_status: {task.get('raw_status')}")

task_dir = f"/tmp/manual-agent-phase1/tasks/{task_id}"
events_file = f"{task_dir}/events.jsonl"
print(f"Before: events_file mtime = {os.path.getmtime(events_file) if os.path.exists(events_file) else 'N/A'}")

# 调用 run
print("Calling /run ...")
res = requests.post(f"http://127.0.0.1:8000/api/tasks/{task_id}/run")
print(res.json())

# 等待后台任务完成
time.sleep(1)

print(f"After: events_file mtime = {os.path.getmtime(events_file) if os.path.exists(events_file) else 'N/A'}")
