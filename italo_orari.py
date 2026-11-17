"""Costruisce l'archivio degli orari dei treni Italo osservando «Italo in viaggio» (italoinviaggio.italotreno.com).

Uso: python italo_orari.py <file_archivio.json>

Italo dà le fermate di un treno solo da una decina di minuti prima della partenza e finché circola. Questo programma, lanciato
spesso nella giornata, guarda le bacheche delle stazioni Italo (partenze e arrivi vicini), prende i numeri dei treni che compaiono
e per ciascuno legge le fermate e gli orari PROGRAMMATI mentre il treno circola. L'archivio ricorda l'ultima osservazione di ogni
treno: l'app lo usa per mostrare le fermate di un treno non ancora partito. Si aggiorna senza perdere i treni già visti; quelli
non visti da più di 45 giorni si tolgono.

Solo libreria standard. Gentile con il sito: richieste distanziate, nome del programma nell'intestazione, nessun dato personale.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

BASE = "https://italoinviaggio.italotreno.com/api/"
UA = "Infotreno-orari/1.0 (archivio degli orari dei treni Italo)"
DELAY = 0.4  # secondi tra due richieste
KEEP_DAYS = 45


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def pause():
    time.sleep(DELAY)


def italo_stations():
    """Codici delle stazioni Italo (senza gli autobus e senza i raggruppamenti «Milano (Tutte)»)."""
    data = get_json(BASE + "getStations?" + urllib.parse.urlencode({"includeWhiteLabel": "true", "lang": "it", "ntvAjaxControlAction": "getStations"}))
    out = []
    for s in data.get("stations", []):
        name = s.get("name", "")
        if s.get("isItaloStation") and not s.get("isItabusStation") and " BUS" not in name and "(Tutte)" not in name:
            out.append(s["stationCode"])
    return out


def train_numbers(codes):
    """I numeri dei treni che compaiono nelle bacheche delle stazioni (arrivi e partenze)."""
    numbers = set()
    for code in codes:
        try:
            board = get_json(BASE + "RicercaStazioneService?" + urllib.parse.urlencode({"CodiceStazione": code}))
        except Exception as e:  # una stazione che non risponde non ferma le altre
            print("stazione saltata", code, e)
            pause()
            continue
        for key in ("ListaTreniArrivo", "ListaTreniPartenza"):
            for t in board.get(key) or []:
                n = str(t.get("Numero") or "").strip()
                if n.isdigit():
                    numbers.add(n)
        pause()
    return numbers


def entry_from_live(schedule, today):
    """L'orario programmato di un treno in circolazione: fermate in ordine con arrivo e partenza «HH:mm»."""
    part = schedule.get("StazionePartenza")
    if not part:
        return None
    stops = [part] + (schedule.get("StazioniFerme") or []) + (schedule.get("StazioniNonFerme") or [])
    if len(stops) < 2:
        return None
    out = []
    for i, s in enumerate(stops):
        first, last = i == 0, i == len(stops) - 1
        arrival = None if first else (s.get("EstimatedArrivalTime") or None)
        departure = None if last else (s.get("EstimatedDepartureTime") or None)
        if not first and not arrival:
            return None
        if not last and not departure:
            return None
        out.append({"n": s.get("LocationDescription") or "", "c": s.get("LocationCode") or "", "a": arrival, "d": departure})
    return {
        "from": schedule.get("DepartureStationDescription") or out[0]["n"],
        "to": schedule.get("ArrivalStationDescription") or out[-1]["n"],
        "stops": out,
        "seen": today.isoformat(),
    }


def main():
    out_path = sys.argv[1]
    today = date.today()
    try:
        with open(out_path, encoding="utf-8") as f:
            archive = json.load(f)
    except Exception:
        archive = {}
    trains = archive.get("trains", {})

    codes = italo_stations()
    print(len(codes), "stazioni Italo")
    numbers = train_numbers(codes)
    print(len(numbers), "treni nelle bacheche")
    # anche i treni già in archivio che circolano adesso: aggiornano l'orario se è cambiato
    numbers |= set(trains.keys())

    seen_now = 0
    for n in sorted(numbers):
        try:
            resp = get_json(BASE + "RicercaTrenoService?" + urllib.parse.urlencode({"TrainNumber": n}))
        except Exception as e:
            print("treno saltato", n, e)
            pause()
            continue
        pause()
        if resp.get("IsEmpty") or not resp.get("TrainSchedule"):
            continue
        entry = entry_from_live(resp["TrainSchedule"], today)
        if entry:
            trains[n] = entry
            seen_now += 1
    print(seen_now, "treni letti dal vivo")

    limit = (today - timedelta(days=KEEP_DAYS)).isoformat()
    trains = {n: e for n, e in trains.items() if e.get("seen", "") >= limit}

    # Controllo di prudenza: se il sito cambia e non si legge più niente non si butta via l'archivio
    if not trains:
        sys.exit("Nessun treno in archivio: il sito è cambiato? Archivio non aggiornato.")

    # Niente da pubblicare se gli orari sono gli stessi (la data «updated» da sola non basta)
    if archive.get("trains") == trains:
        print("nessun cambiamento:", len(trains), "treni")
        return

    doc = {
        "source": "Italo in viaggio - italoinviaggio.italotreno.com",
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trains": dict(sorted(trains.items())),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(len(trains), "treni in archivio ->", out_path)


main()
