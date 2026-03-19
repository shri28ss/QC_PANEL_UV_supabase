import os

helper = """
import json
def safe_json_loads(data):
    if isinstance(data, (dict, list)): return data
    if isinstance(data, str):
        try: return json.loads(data)
        except: return None
    return data
"""

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "json.loads" not in content and "safe_json_loads" not in content:
        return
        
    if "def safe_json_loads" not in content:
        content = helper + content
        
    content = content.replace("json.loads(", "safe_json_loads(")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        print(f"Fixed {filepath}")

for root, dirs, files in os.walk(r"c:\Users\SHREE\UV_AI\LEDGER_AI\backend"):
    if 'venv' in root or '.git' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith('.py') and file != 'fix_json.py':
            fix_file(os.path.join(root, file))
