"""Legge il calendario scioperi della Commissione di Garanzia Sciopero (cgsse.it) e scrive un file JSON leggero.

Uso: python scioperi_cgsse.py <file_output.json> [giorni_avanti=90]

Solo libreria standard. Gentile con il sito: una richiesta al secondo, nome del programma nell'intestazione, nessun dato personale.
Settori: 382 Generale nazionale, 110 Trasporto ferroviario, 390 Generale trasporti.
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

BASE = "https://cgsse.it"
SECTORS = ["382", "110", "390"]
UA = "Infotreno-scioperi/1.0 (lettore del calendario pubblico CGSSE)"
LABELS = ["Data sciopero", "Data proclamazione", "Stato sciopero", "Sciopero generale", "Settore", "Azienda", "Sindacato proclamante",
          "Sindacato aderente", "Ambito geografico", "Rilevanza", "Modalità", "Ore sciopero", "Note"]


def get(url):
    time.sleep(1.0)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8")


def text_lines(page):
    page = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    return [re.sub(r"\s+", " ", l).strip() for l in html.unescape(re.sub(r"<[^>]+>", "\n", page)).splitlines() if l.strip()]


def listing(start, end):
    ids = []
    page_no = 0
    while True:
        params = [("data_inizio", start.isoformat()), ("data_fine", end.isoformat())] + [("settore[]", s) for s in SECTORS]
        if page_no:
            params.append(("page", str(page_no)))
        page = get(f"{BASE}/calendario-scioperi?" + urllib.parse.urlencode(params))
        found = re.findall(r'href="/calendario-scioperi/dettaglio-sciopero/(\d+)"', page)
        new = [i for i in dict.fromkeys(found) if i not in ids]
        if not new:
            break
        ids += new
        # c'è un'altra pagina solo se il sito la propone
        if not re.search(r"[?&]page=%d" % (page_no + 1), page):
            break
        page_no += 1
    return ids


def parse_date(s):
    """«21/11/2026» oppure «Dal 20/11/2026 al 21/11/2026» -> (inizio, fine) in ISO."""
    d = re.findall(r"(\d\d)/(\d\d)/(\d{4})", s)
    if not d:
        return None, None
    iso = ["%s-%s-%s" % (y, m, g) for g, m, y in d]
    return iso[0], iso[-1]


def detail(sid):
    lines = text_lines(get(f"{BASE}/calendario-scioperi/dettaglio-sciopero/{sid}"))
    start = next((k for k, l in enumerate(lines) if l == "Data sciopero"), None)
    if start is None:
        return None
    fields, current = {}, None
    for l in lines[start:]:
        if l in LABELS:
            current = l
            fields[current] = []
        elif current:
            if l in ("Interventi", "Delibere", "Argomenti", "Normativa"):
                break
            fields[current].append(l)
    g = lambda k: " ".join(fields.get(k, [])).strip()
    d1, d2 = parse_date(g("Data sciopero"))
    if not d1:
        return None
    return {
        "id": int(sid),
        "url": f"{BASE}/calendario-scioperi/dettaglio-sciopero/{sid}",
        "dateStart": d1,
        "dateEnd": d2,
        "sector": g("Settore"),
        "company": g("Azienda"),
        "scope": g("Rilevanza"),  # Nazionale / Regionale / Locale
        "area": g("Ambito geografico"),
        "time": g("Modalità"),
        "hours": g("Ore sciopero"),
        "unions": g("Sindacato proclamante"),
        "notes": g("Note"),
        "status": g("Stato sciopero"),  # Attivo / Revocato
        "declared": parse_date(g("Data proclamazione"))[0],
    }


def main():
    out = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    today = date.today()
    ids = listing(today, today + timedelta(days=days))
    strikes = []
    skipped = 0
    for sid in ids:
        try:
            d = detail(sid)
        except Exception as e:  # una pagina che non si legge non ferma le altre
            print("saltato", sid, e)
            skipped += 1
            continue
        if d:
            strikes.append(d)
        else:
            skipped += 1
    strikes.sort(key=lambda s: (s["dateStart"], s["company"], s["id"]))  # l'id evita che i pari merito cambino ordine a ogni lettura

    # Controlli di prudenza: se il sito cambia impaginazione non si deve sovrascrivere l'elenco buono con uno vuoto o a pezzi
    if skipped and skipped * 2 > len(ids):
        sys.exit(f"Troppe pagine non lette ({skipped} su {len(ids)}): il sito è cambiato? Elenco non aggiornato.")
    try:
        with open(out, encoding="utf-8") as f:
            previous = json.load(f).get("strikes", [])
    except Exception:
        previous = []
    still_open = [p for p in previous if (p.get("dateEnd") or p.get("dateStart") or "") >= today.isoformat() and not str(p.get("status", "")).startswith("Revocat")]
    if not strikes and still_open:
        sys.exit("Nessuno sciopero letto ma nel file ce n'erano ancora in corso: il sito è cambiato? Elenco non aggiornato.")
    doc = {
        "source": "Commissione di Garanzia Sciopero - cgsse.it",
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "from": today.isoformat(),
        "to": (today + timedelta(days=days)).isoformat(),
        "strikes": strikes,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"{len(strikes)} scioperi scritti in {out}")


main()
