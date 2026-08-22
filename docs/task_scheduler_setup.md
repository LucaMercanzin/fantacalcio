# Schedulare lo scraping con Windows Task Scheduler

1. Apri "Utilità di pianificazione" (Task Scheduler).
2. "Crea attività di base" → nome: "Fantacalcio Scraping Giornaliero".
3. Trigger: giornaliero, orario a scelta (es. 08:00).
4. Azione: "Avvia un programma".
   - Programma/script: percorso completo di `python.exe` (es. `C:\Python311\python.exe`)
   - Aggiungi argomenti: percorso completo di `pipeline\scheduled_run.py`
   - Inizia in: cartella `fantacalcio` (es. `C:\Users\<utente>\Projects\AI-Projects\fantacalcio`)
5. Salva. Verifica i log in `data/scraping.log` dopo la prima esecuzione schedulata.
