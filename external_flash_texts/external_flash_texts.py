#!/usr/bin/env python3
import os
import requests
import difflib
import datetime

# URL del file di external_flash_texts
URL = "https://www.habbo.it/gamedata/external_flash_texts/0"

# Percorso locale (nella cartella external_flash_texts)
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
    os.makedirs(os.path.dirname(LOCAL_FILE), exist_ok=True)
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

def generate_diff(old_text, new_text):
    diff_lines = list(difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm=""))
    return diff_lines

def main():
    new_text = download_text()
    if new_text is None:
        return
    old_text = load_local_text()
    if old_text is None:
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
    additions = []
    deletions = []
    for line in diff_lines:
        if line.startswith('@@'):
            continue
        if line.startswith('---') or line.startswith('+++'):
            continue
        if line.startswith('+'):
            additions.append(line)
        elif line.startswith('-'):
            deletions.append(line)

    embeds = []
    if additions:
        add_desc = "\n".join(additions)
        if len(add_desc) > 1900:
            add_desc = add_desc[:1900] + "\n...(truncated)"
        embeds.append({
            "title": "External Flash Texts Additions",
            "description": f"```diff\n{add_desc}\n```",
            "color": 65280  # Verde
        })
    if deletions:
        del_desc = "\n".join(deletions)
        if len(del_desc) > 1900:
            del_desc = del_desc[:1900] + "\n...(truncated)"
        embeds.append({
            "title": "External Flash Texts Deletions",
            "description": f"```diff\n{del_desc}\n```",
            "color": 16753920  # Arancione
        })
    
    if embeds:
        send_discord_notification(embeds)
    
    save_local_text(new_text)
    print("External Flash Texts updated.")

if __name__ == "__main__":
    main()
