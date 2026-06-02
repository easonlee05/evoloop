import requests

try:
    res = requests.get('http://127.0.0.1:8000/api/tasks')
    tasks = res.json().get("tasks", [])
    for t in tasks:
        print(f"ID: {t['id']}, title: {t['title']}, status: {t['status']}, raw_status: {t['raw_status']}")
except Exception as e:
    print(f"Error: {e}")
