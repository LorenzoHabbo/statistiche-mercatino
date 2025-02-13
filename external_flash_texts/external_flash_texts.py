#!/usr/bin/env python3
import os
import sys
import requests
import difflib
import datetime

# URL del file di external_flash_texts
URL = "https://www.habbo.it/gamedata/external_flash_texts/0"

# Percorso locale: salva il file nella stessa cartella dello script
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
    """
    Suddivide la lista di righe (ognuna rappresenta una variabile) in chunk,
    assicurandosi di non spezzare una singola riga, e unendo le righe con doppio newline.
    """
    chunks = []
    current_chunk = ""
    for line in diff_lines:
        # Usa "\n\n" come separatore per aggiungere una riga vuota
        if not current_chunk:
            current_chunk = line
        else:
            # Calcola la lunghezza con due newline (2 caratteri) aggiunti
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
    # Rimuove le righe di header (che iniziano con ---, +++ o @@)
    filtered_lines = [line for line in diff_lines if not (line.startswith('---') or line.startswith('+++') or line.startswith('@@'))]
    return filtered_lines

def main():
    new_text = download_text()
    if new_text is None:
        sys.exit(1)
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
        add_chunks = split_diff_chunks(additions)
        for chunk in add_chunks:
            embeds.append({
                "title": "External Flash Texts Additions",
                "description": f"```diff\n{chunk}\n```",
                "color": 65280  # Verde
            })
    if deletions:
        del_chunks = split_diff_chunks(deletions)
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
    main()
