#!/usr/bin/env python3
import json
import os
import datetime
import requests
import time

# Costanti per gli endpoint API (usati per il test; in ambiente reale verrebbero richiamati)
ROOM_API_URL_TEMPLATE = "https://www.habbo.it/api/public/marketplace/stats/roomItem/{}"
WALL_API_URL_TEMPLATE = "http://habbo.it/api/public/marketplace/stats/wallitem/{}"

# File di output per la cronologia
OUTPUT_FILE = "historical_stats.json"

# Limite massimo per il dayOffset (in negativo)
HISTORY_LIMIT = 30

def load_classnames():
    """
    Per il test, restituisce una lista predefinita di dizionari contenenti:
      - "classname": il nome dell'oggetto
      - "type": "room" oppure "wall"
    
    Questo evita di dover fare il fetch dal furnidata online.
    """
    test_items = [
        {"classname": "shelves_norja", "type": "room"},
        {"classname": "example_wall_item", "type": "wall"},
        {"classname": "chair_example", "type": "room"},
        {"classname": "lamp_test", "type": "wall"}
    ]
    print(f"Loaded {len(test_items)} test classnames.")
    return test_items

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
    
    - Per i roomitem usa ROOM_API_URL_TEMPLATE
    - Per i wallitem usa WALL_API_URL_TEMPLATE
    
    Implementa retry con backoff in caso di errore 429.
    """
    classname = item["classname"]
    item_type = item["type"]
    url = ROOM_API_URL_TEMPLATE.format(classname) if item_type == "room" else WALL_API_URL_TEMPLATE.format(classname)
    
    retries = 0
    wait_time = 5  # secondi di attesa iniziali
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

def update_day_offsets(history, current_date):
    """
    Per ogni record della cronologia:
      - Calcola il delta in giorni tra la data corrente e il record (statsDate).
      - Imposta il campo "dayOffset" come valore negativo (fino a -HISTORY_LIMIT).
      - Calcola inoltre la data corrispondente al dayOffset, salvandola nel campo "calculatedDate".
    """
    updated_history = []
    for record in history:
        try:
            # La data originale del record (statsDate) deve essere nel formato "YYYY-MM-DD"
            record_date = datetime.datetime.strptime(record["statsDate"], "%Y-%m-%d").date()
            delta = (current_date - record_date).days
            day_offset = -min(delta, HISTORY_LIMIT)
            record["dayOffset"] = str(day_offset)
            # Calcola la data corrispondente al dayOffset:
            # Se dayOffset è -5, la calculatedDate sarà current_date - 5 giorni
            calculated_date = current_date + datetime.timedelta(days=int(day_offset))
            record["calculatedDate"] = calculated_date.isoformat()
            updated_history.append(record)
        except Exception as e:
            print(f"Error updating dayOffset for record: {e}")
            updated_history.append(record)
    return updated_history

def main():
    current_date = datetime.date.today()
    items = load_classnames()  # Lista di classnames di test
    all_stats = load_historical_stats()
    
    for item in items:
        classname = item["classname"]
        print(f"Fetching stats for {classname} ({item['type']})...")
        api_result = fetch_stats_for_item(item)
        if api_result is None:
            continue
        
        # Se il classname non è ancora presente nel file storico, salva tutta la cronologia restituita dall'API
        if classname not in all_stats:
            history_list = api_result.get("history", [])
            # Se l'API non fornisce un campo "statsDate" per ogni record, usa la data odierna
            api_stats_date = api_result.get("statsDate", current_date.isoformat())
            for rec in history_list:
                if "statsDate" not in rec:
                    rec["statsDate"] = api_stats_date
            all_stats[classname] = update_day_offsets(history_list, current_date)
            print(f"Saved complete history for {classname} ({len(history_list)} records).")
        else:
            # Se il classname è già presente, aggiungi solo il nuovo record (se non già aggiornato per oggi)
            new_entry = None
            # Cerca il record più recente (ad esempio, con dayOffset "-1")
            for rec in api_result.get("history", []):
                if rec.get("dayOffset") == "-1":
                    new_entry = rec
                    break
            if new_entry is None and api_result.get("history"):
                new_entry = api_result["history"][-1]
            if new_entry:
                new_entry["statsDate"] = current_date.isoformat()
                last_date = datetime.datetime.strptime(all_stats[classname][-1]["statsDate"], "%Y-%m-%d").date()
                if last_date < current_date:
                    all_stats[classname].append(new_entry)
                    print(f"Added new record for {classname}.")
                else:
                    print(f"Record for {classname} already updated for today.")
            all_stats[classname] = update_day_offsets(all_stats[classname], current_date)
    
    save_historical_stats(all_stats)
    print("Update completed.")

if __name__ == "__main__":
    main()
