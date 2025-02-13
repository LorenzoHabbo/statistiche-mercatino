#!/usr/bin/env python3
import os
import sys
import requests
import difflib
import datetime

# URL del file di external_flash_texts
URL = "https://www.habbo.it/gamedata/external_flash_texts/0"

# Salva il file nella stessa cartella dello script
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_FILE = os.path.join(CURRENT_DIR, "external_flash_texts.txt")

# Discord webhook (impostato come secret: DISCORD_WEBHOOK_EXT_FLASH_TEXTS)
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_EXT_FLASH_TEXTS")

def download_text():
    try:
        response = requests.get(URL, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error downloading external flash texts: {e}")
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
    if not DISCORD_WEBHOOK:
        print("Discord webhook not set. Skipping notification.")
        return
    payload = {"embeds": embeds}
    try:
        response = requests.post(DISCORD_WEBHOOK, json=payload)
        if response.status_code not in (200, 204):
            print(f"Failed to send Discord notification: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Error sending Discord notification: {e}")

def split_diff_chunks(diff_lines, max_length=1900):
    """Suddivide la lista di righe (ogni riga rappresenta una variabile) in chunk, senza spezzare righe singole."""
    chunks = []
    current_chunk = ""
    for line in diff_lines:
        if not current_chunk:
            current_chunk = line
        else:
            if len(current_chunk) + len(line) + 1 > max_length:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += "\n" + line
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def generate_diff(old_text, new_text):
    diff_lines = list(difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm=""))
    # Filtra le righe di header
    filtered_lines = [line for line in diff_lines if not (line.startswith('---') or line.startswith('+++') or line.startswith('@@'))]
    return filtered_lines

def send_test_webhook():
    test_embed = {
        "title": "Test Webhook - External Flash Texts",
        "description": f"This is a test message sent on {datetime.datetime.now().isoformat()}",
        "color": 3447003  # Blu
    }
    send_discord_notification([test_embed])
    print("Test webhook sent.")

def main():
    new_text = download_text()
    if new_text is None:
        return
    old_text = load_local_text()
    if old_text is None:
        # Primo avvio: salva lo snapshot iniziale e notifica
        save_local_text(new_text)
        message = f"Initial External Flash Texts Snapshot saved on {datetime.datetime.now().isoformat()}."
        embed = {
            "title": "Initial External Flash Texts Snapshot",
            "description": message,
            "color": 3447003  # Blu
        }
        send_discord_notification([embed])
        return

    if new_text == old_text:
        print("No changes in external flash texts.")
        return

    diff_lines = generate_diff(old_text, new_text)
    additions = [line for line in diff_lines if line.startswith('+')]
    deletions = [line for line in diff_lines if line.startswith('-')]

    embeds = []
    if additions:
        add_chunks = split_diff_chunks(additions, max_length=1900)
        for chunk in add_chunks:
            embeds.append({
                "title": "External Flash Texts Additions",
                "description": f"```diff\n{chunk}\n```",
                "color": 65280  # Verde
            })
    if deletions:
        del_chunks = split_diff_chunks(deletions, max_length=1900)
        for chunk in del_chunks:
            embeds.append({
                "title": "External Flash Texts Deletions",
                "description": f"```diff\n{chunk}\n```",
                "color": 16753920  # Arancione
            })

    if embeds:
        send_discord_notification(embeds)

    save_local_text(new_text)
    print("External Flash Texts updated.")

if __name__ == "__main__":
    if "--test" in sys.argv:
        send_test_webhook()
        sys.exit(0)
    main()
