#!/usr/bin/env python3
import json
import os
import datetime
import requests
import time

# URL del furnidata
FURNIDATA_URL = "https://www.habbo.it/gamedata/furnidata_json/0"

# Endpoint API per ottenere le statistiche
ROOM_API_URL_TEMPLATE = "https://www.habbo.it/api/public/marketplace/stats/roomItem/{}"
WALL_API_URL_TEMPLATE = "http://habbo.it/api/public/marketplace/stats/wallitem/{}"

# File di output per la cronologia
OUTPUT_FILE = "historical_stats.json"

# Limite massimo per il dayOffset (in negativo)
HISTORY_LIMIT = 30

# Set di furniline da escludere (tutti in minuscolo)
EXCLUDED_FURNILINE = {
    "room_noob",
    "buildersclub",
    "buildersclub_alpha1",
    "testing",
    "sanrio",
    "room_xbar",
    "room_pcnc15",
    "room_hall15",
    "room_info15",
    "room_thr15",
    "room_cof15",
    "habbo15",
    "room_welcomelounge",
    "spaces",
    "newbie",
    "room_gh15",
    "room_hcl15",
    "room_wl15",
    "room_picnic",
    "room_theatredome",
    "room_lido"
}

def load_classnames():
    """
    Carica il furnidata direttamente dall'API e restituisce una lista di dizionari contenenti:
      - "classname": il nome dell'oggetto
      - "type": "room" oppure "wall"
    Vengono esclusi gli oggetti che:
      - Hanno un classname che inizia con "nft_" o "bc_"
      - Hanno un campo "furniline" presente nell'insieme EXCLUDED_FURNILINE.
    """
    try:
        response = requests.get(FURNIDATA_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        result = []
        # Processa roomitemtypes
        room_items = data.get("roomitemtypes", {}).get("furnitype", [])
        for item in room_items:
            classname = item.get("classname", "")
            furniline = item.get("furniline", "")
            if classname.startswith("nft_") or classname.startswith("bc_"):
                continue
            if furniline and furniline.lower() in EXCLUDED_FURNILINE:
                continue
            result.append({"classname": classname, "type": "room"})
        # Processa wallitemtypes
        wall_items = data.get("wallitemtypes", {}).get("furnitype", [])
        for item in wall_items:
            classname = item.get("classname", "")
            furniline = item.get("furniline", "")
            if classname.startswith("nft_") or classname.startswith("bc_"):
                continue
            if furniline and furniline.lower() in EXCLUDED_FURNILINE:
                continue
            result.append({"classname": classname, "type": "wall"})
        print(f"Found {len(result)} valid classnames from furnidata.")
        return result
    except Exception as e:
        print("Error fetching classnames from furnidata:", e)
        return []

def load_historical_stats():
    """
    Carica il file storico se esiste, altrimenti restituisce un dizionario vuoto.
    """
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_historical_stats(stats):
    """
    Salva il dizionario 'stats' nel file OUTPUT_FILE in formato JSON.
    """
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

def fetch_stats_for_item(item, max_retries=3):
    """
    Esegue il fetch dei dati dall'API per un determinato item.
    Usa ROOM_API_URL_TEMPLATE per i roomitem e WALL_API_URL_TEMPLATE per i wallitem.
    Implementa retry con backoff in caso di errore 429.
    """
    classname = item["classname"]
    item_type = item["type"]
    url = ROOM_API_URL_TEMPLATE.format(classname) if item_type == "room" else WALL_API_URL_TEMPLATE.format(classname)
    
    retries = 0
    wait_time = 5  # secondi iniziali
    while retries < max_retries:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            print(f"Fetched stats for {classname}.")
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                print(f"Too many requests for {classname}. Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                retries += 1
                wait_time *= 2  # backoff esponenziale
                continue
            else:
                print(f"HTTP error for {classname}: {e}")
                return None
        except Exception as e:
            print(f"Error fetching stats for {classname}: {e}")
            return None
    print(f"Max retries reached for {classname}. Skipping...")
    return None

def update_day_offsets(history, current_date, api_stats_date):
    """
    Per ogni record della cronologia:
      - Se il record non ha il campo "date", lo calcola come:
            date = (api_stats_date) + (int(record["dayOffset"]) giorni)
      - Calcola il nuovo dayOffset come:
            new_day_offset = -( (current_date - date).days )
        (limitato a -HISTORY_LIMIT se necessario)
      - Il campo "date" rimane fisso.
    """
    updated_history = []
    api_stats_date_obj = datetime.datetime.strptime(api_stats_date, "%Y-%m-%d").date()
    for record in history:
        try:
            if "date" not in record:
                api_day_offset = int(record.get("dayOffset", "0"))
                computed_date = api_stats_date_obj + datetime.timedelta(days=api_day_offset)
                record["date"] = computed_date.isoformat()
            else:
                computed_date = datetime.datetime.strptime(record["date"], "%Y-%m-%d").date()
            delta = (current_date - computed_date).days
            new_day_offset = -delta
            if new_day_offset < -HISTORY_LIMIT:
                new_day_offset = -HISTORY_LIMIT
            record["dayOffset"] = str(new_day_offset)
            updated_history.append(record)
        except Exception as e:
            print(f"Error updating dayOffset for record: {e}")
            updated_history.append(record)
    return updated_history

def main():
    current_date = datetime.date.today()
    # Carica i classnames dal furnidata API
    items = load_classnames()
    all_stats = load_historical_stats()
    
    for item in items:
        classname = item["classname"]
        print(f"Fetching stats for {classname} ({item['type']})...")
        api_result = fetch_stats_for_item(item)
        if api_result is None:
            continue
        
        # Otteniamo la data di riferimento dalla API; se non esiste, usiamo la data corrente.
        api_stats_date = api_result.get("statsDate", current_date.isoformat())
        
        if classname not in all_stats:
            history_list = api_result.get("history", [])
            # Per ogni record, se manca "statsDate", lo impostiamo con api_stats_date
            for rec in history_list:
                if "statsDate" not in rec:
                    rec["statsDate"] = api_stats_date
            # Calcola e imposta il campo "date" per ciascun record
            all_stats[classname] = update_day_offsets(history_list, current_date, api_stats_date)
            print(f"Saved complete history for {classname} ({len(history_list)} records).")
        else:
            # Se il classname esiste già, aggiungi solo il nuovo record se non già aggiornato per oggi
            new_entry = None
            for rec in api_result.get("history", []):
                if rec.get("dayOffset") == "-1":
                    new_entry = rec
                    break
            if new_entry is None and api_result.get("history"):
                new_entry = api_result["history"][-1]
            if new_entry:
                new_entry["statsDate"] = current_date.isoformat()
                new_entry["date"] = current_date.isoformat()
                last_date = datetime.datetime.strptime(all_stats[classname][-1]["statsDate"], "%Y-%m-%d").date()
                if last_date < current_date:
                    all_stats[classname].append(new_entry)
                    print(f"Added new record for {classname}.")
                else:
                    print(f"Record for {classname} already updated for today.")
            all_stats[classname] = update_day_offsets(all_stats[classname], current_date, api_stats_date)
    
    save_historical_stats(all_stats)
    print("Update completed.")

if __name__ == "__main__":
    main()
