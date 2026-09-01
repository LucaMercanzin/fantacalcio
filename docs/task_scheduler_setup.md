# Schedulare la pipeline con Windows Task Scheduler

`pipeline/scheduled_run.py` è l'unico comando da schedulare. Conosce tutti e
dodici i runner di `pipeline/` e la cadenza di ognuno, quindi **una sola
attività giornaliera basta**: allo scatto esegue solo i job scaduti quel
giorno e salta gli altri.

Fino al 31/08/2026 questo documento descriveva la stessa configurazione ma
lo script lanciava solo i sei scraper delle quotazioni: sette tabelle
restavano vuote perché nessuno chiamava i runner corrispondenti
(BACKLOG-2026-08-31 §5). La configurazione qui sotto non è cambiata — è
cambiato cosa fa lo script quando parte.

## Configurazione

1. Apri "Utilità di pianificazione" (Task Scheduler).
2. "Crea attività di base" → nome: "Fantacalcio Pipeline Giornaliera".
3. Trigger: giornaliero, orario a scelta (es. 08:00).
4. Azione: "Avvia un programma".
   - Programma/script: percorso completo di `python.exe` (es. `C:\Python311\python.exe`)
   - Aggiungi argomenti: percorso completo di `pipeline\scheduled_run.py`
   - Inizia in: cartella `fantacalcio` (es. `C:\Users\<utente>\Projects\AI-Projects\fantacalcio`)
5. Salva.

## Verificare che stia funzionando

```bash
python pipeline/scheduled_run.py --list
```

Una tabella con, per ogni job, la cadenza, l'ultimo run riuscito, l'esito e
se è scaduto adesso. È il modo più veloce per accorgersi che un job sta
fallendo da giorni: `stato = failed` con un `ultimo successo` vecchio.

Il dettaglio sta in `data/scraping.log` (una riga per job, con il risultato
o il traceback) e in `data/*.log` per i runner che tengono un log proprio.

## Quanto dura

La durata dipende da quali job sono scaduti. Il caso lungo è `injuries`:
risolve un ID Transfermarkt per giocatore con 1,5 secondi di attesa fra le
richieste, quindi al primo run — con `player_transfermarkt_ids` quasi vuota
— può superare l'ora. Dai run successivi gli ID sono già in tabella e serve
una richiesta sola per giocatore invece di due.

Se serve tenerlo fuori da un run particolare, o lanciarlo a parte:

```bash
python pipeline/scheduled_run.py --only quotations match_ratings
python pipeline/scheduled_run.py --only injuries
```

## Se un job fallisce

Non ferma gli altri: ogni job ha il suo try/except e il run prosegue. Un
fallimento **non** consuma la cadenza — `last_success_at` resta quello
vecchio, il job resta scaduto e viene ritentato al run successivo, invece di
essere considerato fatto perché è stato tentato.
