#!/usr/bin/env python3
import os
import sys
import requests
import difflib
import datetime

# URL del file di external_variables
URL = "https://www.habbo.it/gamedata/external_variables/0"

# Percorso locale: salva il file nella stessa cartella dello script
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_FILE = os.path.join(CURRENT_DIR, "external_variables.txt")

# Discord webhook (impostato come secret: DISCORD_WEBHOOK_EXT_VARIABLES)
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_EXT_VARIABLES")

def download_text():
    try:
        response = requests.get(URL, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error downloading external variables: {e}")
        return None

def load_local_text():
    if os.path.exists(LOCAL_FILE):
        with open(LOCAL_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return None

def save_local_text(text):
    with open(LOCAL_FILE, "w", encoding="utf-8") as f:
        f.write(text)

def send_discord_notification(embeds):
    """
    Invia ogni embed in una richiesta separata.
    """
    if not DISCORD_WEBHOOK:
        print("Discord webhook not set. Skipping notification.")
        return
    for embed in embeds:
        payload = {"embeds": [embed]}
        try:
            response = requests.post(DISCORD_WEBHOOK, json=payload)
            if response.status_code not in (200, 204):
                print(f"Failed to send Discord notification: {response.status_code} {response.text}")
        except Exception as e:
            print(f"Error sending Discord notification: {e}")

def split_diff_chunks(diff_lines, max_length=1900):
    """
    Suddivide la lista di righe (ognuna rappresenta una variabile) in chunk,
    usando "\n\n" come separatore per aggiungere uno spazio (riga vuota)
    tra le righe, senza spezzare una singola riga.
    """
    chunks = []
    current_chunk = ""
    for line in diff_lines:
        if not current_chunk:
            current_chunk = line
        else:
            if len(current_chunk) + len(line) + 2 > max_length:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += "\n\n" + line
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def generate_diff(old_text, new_text):
    diff_lines = list(difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm=""))
    # Rimuove le righe di header: '---', '+++' e '@@'
    filtered_lines = [line for line in diff_lines if not (line.startswith('---') or line.startswith('+++') or line.startswith('@@'))]
    return filtered_lines

def main():
    new_text = download_text()
    if new_text is None:
        sys.exit(1)
    old_text = load_local_text()
    if old_text is None:
        # Primo avvio: salva lo snapshot iniziale e invia una notifica di test
        save_local_text(new_text)
        message = f"Initial External Variables Snapshot saved on {datetime.datetime.now().isoformat()}."
        embed = {
            "title": "Initial External Variables Snapshot",
            "description": message,
            "color": 3447003  # Blu
        }
        send_discord_notification([embed])
        return

    if new_text == old_text:
        print("No changes in external variables.")
        return

    diff_lines = generate_diff(old_text, new_text)
    additions = [line for line in diff_lines if line.startswith('+')]
    deletions = [line for line in diff_lines if line.startswith('-')]

    embeds = []
    if additions:
        add_chunks = split_diff_chunks(additions)
        for chunk in add_chunks:
            embeds.append({
                "title": "External Variables Additions",
                "description": f"```diff\n{chunk}\n```",
                "color": 65280  # Verde
            })
    if deletions:
        del_chunks = split_diff_chunks(deletions)
        for chunk in del_chunks:
            embeds.append({
                "title": "External Variables Deletions",
                "description": f"```diff\n{chunk}\n```",
                "color": 16753920  # Arancione
            })

    if embeds:
        send_discord_notification(embeds)

    save_local_text(new_text)
    print("External Variables updated.")

if __name__ == "__main__":
    if "--test" in sys.argv:
        test_embed = {
            "title": "Test Webhook - External Variables",
            "description": f"This is a test message sent on {datetime.datetime.now().isoformat()}",
            "color": 3447003  # Blu
        }
        send_discord_notification([test_embed])
        sys.exit(0)
    main()
