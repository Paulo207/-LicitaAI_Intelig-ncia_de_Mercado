"""
obter_chat_id.py — LicitaAI · PE&CR Soluções
─────────────────────────────────────────────
Execute este script UMA VEZ para descobrir seu Chat ID do Telegram:

  1. Abra o Telegram e envie qualquer mensagem ao seu bot
  2. Rode: python obter_chat_id.py
  3. Copie o número exibido e cole em .env → CHAT_ID=numero

"""

import requests
import json
from pathlib import Path

def main():
    # Lê token do .env
    env_path = Path(__file__).parent / ".env"
    token = None
    if env_path.exists():
        for linha in env_path.read_text(encoding="utf-8").splitlines():
            if linha.startswith("TOKEN_TELEGRAM="):
                token = linha.split("=", 1)[1].strip()
                break

    if not token:
        print("❌ TOKEN_TELEGRAM não encontrado no .env")
        return

    print(f"🤖 Consultando bot com token: {token[:20]}...")
    url = f"https://api.telegram.org/bot{token}/getUpdates"

    try:
        r = requests.get(url, timeout=15)
        data = r.json()

        if not data.get("ok"):
            print(f"❌ Erro da API: {data}")
            return

        resultados = data.get("result", [])
        if not resultados:
            print("⚠️  Nenhuma mensagem encontrada.")
            print("   → Vá ao Telegram, envie /start ao seu bot e rode este script novamente.")
            return

        print("\n✅ Chat IDs encontrados:\n")
        ids_vistos = set()
        for upd in resultados:
            msg = upd.get("message") or upd.get("channel_post") or {}
            chat = msg.get("chat", {})
            cid = chat.get("id")
            nome = chat.get("first_name") or chat.get("title") or "desconhecido"
            tipo = chat.get("type", "")
            if cid and cid not in ids_vistos:
                ids_vistos.add(cid)
                print(f"  🆔 Chat ID : {cid}")
                print(f"     Nome    : {nome}")
                print(f"     Tipo    : {tipo}")
                print()

        if ids_vistos:
            cid_escolhido = list(ids_vistos)[0]
            print(f"👉 No arquivo .env, substitua a linha:")
            print(f"   CHAT_ID=SEU_CHAT_ID_AQUI")
            print(f"   por:")
            print(f"   CHAT_ID={cid_escolhido}")

    except Exception as ex:
        print(f"❌ Falha na requisição: {ex}")

if __name__ == "__main__":
    main()
