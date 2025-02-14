#!/usr/bin/env python3
import os
import json
import datetime
import requests
import re
from deepdiff import DeepDiff

# URL del furnidata
FURNIDATA_URL = "https://www.habbo.it/gamedata/furnidata_json/0"

# Percorso locale: salva il file nella stessa cartella dello script
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_FILE = os.path.join(CURRENT_DIR, "furnidata.json")

# Discord webhook (impostato come secret: DISCORD_WEBHOOK)
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

MAX_LENGTH = 1900  # Lunghezza massima per la descrizione degli embed

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
    for embed in embeds:
        payload = {"embeds": [embed]}
        try:
            response = requests.post(DISCORD_WEBHOOK, json=payload)
            if response.status_code not in (200, 204):
                print(f"Failed to send Discord notification: {response.status_code} {response.text}")
        except Exception as e:
            print(f"Error sending Discord notification: {e}")

def split_text_into_chunks(text, max_length=MAX_LENGTH):
    """
    Suddivide il testo in chunk, senza spezzare le righe.
    """
    lines = text.splitlines()
    chunks = []
    current_chunk = ""
    for line in lines:
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

# --- Helper per il parsing dei path DeepDiff ---
def parse_diff_path(diff_path):
    """
    Converte una stringa tipo
    "root['roomitemtypes']['furnitype'][14853]['name']"
    in una lista di chiavi: ["roomitemtypes", "furnitype", 14853, "name"]
    """
    pattern = re.compile(r"\['([^']+)'\]|\[(\d+)\]")
    keys = []
    for match in pattern.finditer(diff_path):
        if match.group(1) is not None:
            keys.append(match.group(1))
        elif match.group(2) is not None:
            keys.append(int(match.group(2)))
    return keys

def get_by_path(data, keys):
    for key in keys:
        data = data[key]
    return data

# --- Funzioni per generare il diff formattato in stile "diff" per Discord ---
def generate_object_diff(old_obj, new_obj, modifications):
    """
    Genera una stringa diff in stile JSON per un oggetto con modifiche.
    Le righe modificate iniziano direttamente con '-' o '+' per attivare
    la sintassi diff di Discord.
    """
    # Crea una lista di chiavi preservando l'ordine del nuovo oggetto
    keys = list(new_obj.keys())
    for key in old_obj:
        if key not in new_obj and key not in keys:
            keys.append(key)
    lines = []
    lines.append("{")
    for key in keys:
        if modifications and key in modifications:
            old_val = modifications[key]["old"]
            new_val = modifications[key]["new"]
            # Rimuoviamo l'indentazione per le righe modificate
            line_old = f'- {json.dumps(key)}: {json.dumps(old_val)},'
            line_new = f'+ {json.dumps(key)}: {json.dumps(new_val)},'
            lines.append(line_old)
            lines.append(line_new)
        else:
            # Le righe non modificate possono essere mantenute con indentazione (non influenzano il diff)
            val = new_obj.get(key, old_obj.get(key))
            line = f'  {json.dumps(key)}: {json.dumps(val)},'
            lines.append(line)
    lines.append("}")
    return "\n".join(lines)

def generate_new_object_diff(new_obj):
    """
    Genera la rappresentazione completa di un nuovo oggetto, con ogni riga
    preceduta dal segno "+".
    """
    lines = []
    lines.append("{")
    for key, value in new_obj.items():
        line = f'+ {json.dumps(key)}: {json.dumps(value)},'
        lines.append("  " + line)
    lines.append("}")
    return "\n".join(lines)

def send_discord_diff_notification(diff, local_data, new_data):
    embeds = []
    
    # --- Gestione dei nuovi oggetti ---
    new_objects = {}
    if "dictionary_item_added" in diff:
        for path in diff["dictionary_item_added"]:
            keys = parse_diff_path(path)
            try:
                new_obj = get_by_path(new_data, keys)
                new_objects[tuple(keys)] = new_obj
            except Exception as e:
                print(f"Error retrieving new object for path {path}: {e}")
    if "iterable_item_added" in diff:
        for path in diff["iterable_item_added"]:
            keys = parse_diff_path(path)
            try:
                new_obj = get_by_path(new_data, keys)
                new_objects[tuple(keys)] = new_obj
            except Exception as e:
                print(f"Error retrieving new iterable item for path {path}: {e}")
                
    for parent, new_obj in new_objects.items():
        diff_str = "```diff\n" + generate_new_object_diff(new_obj) + "\n```"
        embed = {
            "title": "Furnidata New Object",
            "description": diff_str,
            "color": 65280  # verde
        }
        embeds.append(embed)
    
    # --- Gestione delle modifiche ---
    modifications_by_parent = {}
    if "values_changed" in diff:
        for path, change in diff["values_changed"].items():
            keys = parse_diff_path(path)
            parent = tuple(keys[:-1])
            field = keys[-1]
            modifications_by_parent.setdefault(parent, {})[field] = {
                "old": change["old_value"],
                "new": change["new_value"]
            }
    
    for parent, modifications in modifications_by_parent.items():
        try:
            old_obj = get_by_path(local_data, list(parent))
        except Exception as e:
            old_obj = {}
        try:
            new_obj = get_by_path(new_data, list(parent))
        except Exception as e:
            new_obj = {}
        diff_representation = generate_object_diff(old_obj, new_obj, modifications)
        diff_str = "```diff\n" + diff_representation + "\n```"
        embed = {
            "title": "Furnidata Modifications",
            "description": diff_str,
            "color": 16776960  # giallo
        }
        embeds.append(embed)
    
    if embeds:
        # Se il testo supera MAX_LENGTH lo suddividiamo
        final_embeds = []
        for embed in embeds:
            if len(embed["description"]) > MAX_LENGTH:
                chunks = split_text_into_chunks(embed["description"], max_length=MAX_LENGTH)
                for chunk in chunks:
                    final_embeds.append({
                        "title": embed["title"],
                        "description": chunk,
                        "color": embed["color"]
                    })
            else:
                final_embeds.append(embed)
        send_discord_embeds(final_embeds)
    else:
        send_discord_embeds([{
            "title": "Furnidata Check",
            "description": f"No changes detected as of {datetime.datetime.now().isoformat()}",
            "color": 3447003  # blu
        }])

def main():
    new_data = download_furnidata()
    if new_data is None:
        print("Failed to download new furnidata.")
        return

    local_data = load_local_furnidata()
    if local_data is None:
        # Primo avvio: salva lo snapshot iniziale e invia una notifica
        save_local_furnidata(new_data)
        message = f"Initial furnidata snapshot saved on {datetime.datetime.now().isoformat()}."
        print(message)
        send_discord_embeds([{
            "title": "Initial Furnidata Snapshot",
            "description": message,
            "color": 3447003  # blu
        }])
        return

    diff = DeepDiff(local_data, new_data, ignore_order=True)
    if diff:
        send_discord_diff_notification(diff, local_data, new_data)
        print("Furnidata changes detected:")
        print(json.dumps(diff, indent=2))
        save_local_furnidata(new_data)
    else:
        print(f"No changes in furnidata as of {datetime.datetime.now().isoformat()}.")

if __name__ == "__main__":
    main()
