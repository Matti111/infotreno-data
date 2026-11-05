# infotreno-data

Dati pubblici per l'app **Infotreno** (Android).

## scioperi.json

Elenco dei prossimi scioperi dei treni (settori «Generale nazionale», «Trasporto ferroviario» e «Generale trasporti»), per i
prossimi 90 giorni.

- **Fonte**: [Commissione di Garanzia Sciopero](https://cgsse.it/calendario-scioperi) (cgsse.it), calendario pubblico degli scioperi.
  Ogni sciopero ha il collegamento alla sua pagina ufficiale (`url`).
- **Come si aggiorna**: l'azione automatica `.github/workflows/scioperi.yml` lancia `scioperi_cgsse.py` due volte al giorno.
  Il programma fa una richiesta al secondo, si presenta con il suo nome e non invia dati personali.
- **Avvertenza**: gli scioperi possono essere revocati o cambiare orario dopo l'aggiornamento; il campo `status` dice se uno
  sciopero è stato revocato. L'ora è testo libero scritto dalla Commissione. Per il proprio treno controllare sempre anche
  il sito del vettore. Questo file non è un servizio ufficiale.

Campi: `id`, `url`, `dateStart`, `dateEnd` (aaaa-mm-gg), `sector`, `company`, `scope` (Nazionale, Regionale, Locale), `area`,
`time`, `hours`, `unions`, `notes`, `status`, `declared`.

Contatti: applicazionimobile@gmail.com
