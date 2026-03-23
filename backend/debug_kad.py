import requests
from bs4 import BeautifulSoup
import re
import os

session = requests.Session()
payload = {"w": "password", "p": "1647380"}
resp = session.post("http://127.0.0.1:4711/", data=payload)
match = re.search(r'\?ses=([A-Za-z0-9_]+)', resp.text)
if match:
    ses = match.group(1)

    # Guardamos los dumps en la raíz del proyecto para facilitar su lectura
    output_dir = os.path.join(os.path.dirname(__file__), '..')

    for page, name in [('kad', 'kad'), ('stats', 'stats')]:
        url = f"http://127.0.0.1:4711/?ses={ses}&w={page}"
        resp = session.get(url)
        html_path = os.path.join(output_dir, f'test_{name}.html')
        txt_path  = os.path.join(output_dir, f'test_{name}_text.txt')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(resp.text)
        soup = BeautifulSoup(resp.text, 'html.parser')
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(soup.get_text(separator='\n', strip=True))
        print(f"[+] Done: {name} → {txt_path}")
else:
    print("[!] Login failed")
