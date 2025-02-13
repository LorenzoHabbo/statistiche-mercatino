#!/usr/bin/env python3
import json
import os
import datetime
import requests

FURNIDATA_URL = "https://www.habbo.it/gamedata/furnidata_json/0"
OUTPUT_FILE = "historical_stats.json"
ROOM_API_URL_TEMPLATE = "https://www.habbo.it/api/public/marketplace/stats/roomItem/{}"
WALL_API_URL_TEMPLATE = "http://habbo.it/api/public/marketplace/stats/wallitem/{}"
HISTORY_LIMIT = 30  

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
    try:
        response = requests.get(FURNIDATA_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        result = []
        # Processa i roomitemtypes
        room_items = data.get("roomitemtypes", {}).get("furnitype", [])
        for item in room_items:
            classname = item.get("classname", "")
            furniline = item.get("furniline", "")
            if classname.startswith("nft_") or classname.startswith("bc_"):
                continue
            if furniline and furniline.lower() in EXCLUDED_FURNILINE:
                continue
            result.append({"classname": classname, "type": "room"})
        # Processa i wallitemtypes
        wall_items = data.get("wallitemtypes", {}).get("furnitype", [])
        for item in wall_items:
            classname = item.get("classname", "")
            furniline = item.get("furniline", "")
            if classname.startswith("nft_") or classname.startswith("bc_"):
                continue
            if furniline and furniline.lower() in EXCLUDED_FURNILINE:
                continue
            result.append({"classname": classname, "type": "wall"})
        print(f"Trovati {len(result)} classnames utili (room e wall).")
        return result
    except Exception as e:
        print("Errore nel fetch dei classnames dal furnidata:", e)
        return []

def load_historical_stats():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_historical_stats(stats):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

def fetch_stats_for_item(item):
    classname = item["classname"]
    item_type = item["type"]
    if item_type == "room":
        url = ROOM_API_URL_TEMPLATE.format(classname)
    else:
        url = WALL_API_URL_TEMPLATE.format(classname)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Errore nel fetch per {classname}: {e}")
        return None

def update_day_offsets(history, current_date):
    updated_history = []
    for record in history:
        try:
            record_date = datetime.datetime.strptime(record["statsDate"], "%Y-%m-%d").date()
            delta = (current_date - record_date).days
            day_offset = -min(delta, HISTORY_LIMIT)
            record["dayOffset"] = str(day_offset)
            updated_history.append(record)
        except Exception as e:
            print(f"Errore nel calcolo del dayOffset: {e}")
            updated_history.append(record)
    return updated_history

def main():
    current_date = datetime.date.today()
    items = load_classnames()
    all_stats = load_historical_stats()

    for item in items:
        classname = item["classname"]
        print(f"Fetch stats per {classname} ({item['type']})...")
        api_result = fetch_stats_for_item(item)
        if api_result is None:
            continue

        if classname not in all_stats:
            history_list = api_result.get("history", [])
            api_stats_date = api_result.get("statsDate", current_date.isoformat())
            for rec in history_list:
                if "statsDate" not in rec:
                    rec["statsDate"] = api_stats_date
            all_stats[classname] = update_day_offsets(history_list, current_date)
            print(f"Salvata cronologia completa per {classname} ({len(history_list)} record).")
        else:
            new_entry = None
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
                    print(f"Aggiunto nuovo record per {classname}.")
                else:
                    print(f"Record per {classname} già aggiornato per oggi.")
            all_stats[classname] = update_day_offsets(all_stats[classname], current_date)

    save_historical_stats(all_stats)
    print("Aggiornamento completato.")

if __name__ == "__main__":
    main()
