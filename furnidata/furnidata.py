#!/usr/bin/env python3
import os
import json
import datetime
import requests
import time
from deepdiff import DeepDiff

# URL del furnidata
FURNIDATA_URL = "https://www.habbo.it/gamedata/furnidata_json/0"

# Percorso locale: salva il file nella stessa cartella dello script
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_FILE = os.path.join(CURRENT_DIR, "furnidata.json")

# Discord webhook (impostato come secret: DISCORD_WEBHOOK)
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

def download_furnidata():
    try:
        response = requests.get(FURNIDATA_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error downloading furnidata: {e}")
        return None

def load_local_furnidata():
    if os.path.exists(LOCAL_FILE):
        with open(LOCAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_local_furnidata(data):
    with open(LOCAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def send_discord_embeds(embeds):
    if not DISCORD_WEBHOOK:
        print("DISCORD_WEBHOOK not set. Skipping Discord notification.")
        return
    payload = {"embeds": embeds}
    try:
        response = requests.post(DISCORD_WEBHOOK, json=payload)
        if response.status_code not in (200, 204):
            print(f"Failed to send Discord notification: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Error sending Discord notification: {e}")

def send_discord_diff_notification(diff):
    embeds = []
    
    additions = {}
    if "dictionary_item_added" in diff:
        additions["dictionary_item_added"] = diff["dictionary_item_added"]
    if "iterable_item_added" in diff:
        additions["iterable_item_added"] = diff["iterable_item_added"]
    
    modifications = diff.get("values_changed")
    
    if additions:
        additions_desc = json.dumps(additions, indent=2)
        embeds.append({
            "title": "Furnidata Additions",
            "description": f"```json\n{additions_desc}\n```",
            "color": 65280  # Verde
        })
    if modifications:
        modifications_desc = json.dumps(modifications, indent=2)
        embeds.append({
            "title": "Furnidata Modifications",
            "description": f"```json\n{modifications_desc}\n```",
            "color": 16753920  # Arancione
        })
        
    if embeds:
        send_discord_embeds(embeds)
    else:
        send_discord_embeds([{
            "title": "Furnidata Check",
            "description": f"No changes detected as of {datetime.datetime.now().isoformat()}",
            "color": 3447003  # Blu
        }])

def main():
    new_data = download_furnidata()
    if new_data is None:
        print("Failed to download new furnidata.")
        return

    local_data = load_local_furnidata()
    if local_data is None:
        # Primo avvio: salva lo snapshot iniziale e notifica
        save_local_furnidata(new_data)
        message = f"Initial furnidata snapshot saved on {datetime.datetime.now().isoformat()}."
        print(message)
        send_discord_embeds([{
            "title": "Initial Furnidata Snapshot",
            "description": message,
            "color": 3447003  # Blu
        }])
        return

    diff = DeepDiff(local_data, new_data, ignore_order=True)
    if diff:
        send_discord_diff_notification(diff)
        print("Furnidata changes detected:")
        print(json.dumps(diff, indent=2))
        save_local_furnidata(new_data)
    else:
        print(f"No changes in furnidata as of {datetime.datetime.now().isoformat()}.")

if __name__ == "__main__":
    main()
