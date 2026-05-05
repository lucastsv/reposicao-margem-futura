"""
Helper one-shot pra descobrir seu chat_id do Telegram.
Uso: python obter_chat_id.py <SEU_TOKEN>
"""

import json
import ssl
import sys
import urllib.request

if len(sys.argv) != 2:
    print("Uso: python obter_chat_id.py <SEU_TOKEN>")
    sys.exit(1)

token = sys.argv[1].strip()
url = f"https://api.telegram.org/bot{token}/getUpdates"
ctx = ssl.create_default_context()
with urllib.request.urlopen(url, timeout=30, context=ctx) as r:
    data = json.loads(r.read())

if not data.get("ok"):
    print(f"ERRO: {data}")
    sys.exit(1)

results = data.get("result", [])
if not results:
    print("Nenhuma mensagem encontrada. Mande qualquer texto pro seu bot")
    print("(via Telegram) e rode este script de novo.")
    sys.exit(1)

ids = set()
for upd in results:
    msg = upd.get("message") or upd.get("edited_message") or {}
    chat = msg.get("chat") or {}
    if chat.get("id"):
        ids.add((chat["id"], chat.get("first_name") or chat.get("title") or "?"))

print("Chat IDs encontrados:")
for cid, nome in ids:
    print(f"  chat_id = {cid}  (chat: {nome})")
