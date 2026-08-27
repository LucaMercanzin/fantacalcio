# Grafica Rosa Ideale, navigazione diretta su Monitoraggio, rivalutazione tier, simulazione aste

Data: 2026-08-26

## 1. Contesto

Richiesta utente: la sezione "Rosa Ideale" (campino con formazione) in `dashboard/pages/5_La_Mia_Rosa.py`
non è più leggibile; il sito deve aprirsi direttamente sulla pagina Monitoraggio invece che sulla
pagina placeholder "app"; dopo il lavoro grafico vanno rivalutate le sezioni Top/Semi-top dei tier;
infine va costruita ed eseguita una simulazione di 1000 aste per validare che tutti i calcoli
(prezzi, tier, budget, optimizer) abbiano senso.

## 2. Leggibilità Rosa Ideale

`_chip`/`pitch_html` in `5_La_Mia_Rosa.py` (righe ~133-187) generano un box `position:fixed`,
230×300px, ancorato in basso a sinistra, con testo a 11px/9px — causa di illeggibilità e rischio di
sovrapposizione con altri contenuti della pagina.

Modifica: sostituire il box fisso con una sezione a piena larghezza, in flusso normale di pagina
(niente `position:fixed`), campo proporzionalmente più grande, font aumentati (~15-16px nome,
~12px badge/quotazione), spaziatura tra i chip di centrocampo (4 titolari) sufficiente a evitare
accavallamenti anche su schermi stretti. La logica dati (`get_ideal_formation`, ruoli, badge
✅/quotazione) resta invariata: cambia solo il markup/CSS di presentazione.

Il menu laterale "Rosa Ideale" (`render_sidebar_ideal_squad` in `components.py`) resta invariato:
è già una semplice lista di pulsanti testuali, leggibile.

## 3. Navigazione: rimozione pagina "app", apertura diretta su Monitoraggio

Oggi `dashboard/app.py` è lo script d'ingresso Streamlit; il suo corpo modulo (dopo la definizione
di `get_db_connection`) chiama `st.set_page_config` e stampa un placeholder ("Fantacalcio Dashboard
— Seleziona una pagina..."). Questo produce la voce "app" nel menu e la pagina di apertura vuota.

Streamlit 1.38 (versione installata) supporta `st.Page`/`st.navigation`. Si sostituisce il blocco
finale di `app.py` con la dichiarazione esplicita delle 7 pagine tramite `st.Page(...)`, impostando
`default=True` su Monitoraggio:

```python
pages = [
    st.Page("pages/7_Monitoraggio.py", title="Monitoraggio", icon="📡", default=True),
    st.Page("pages/1_Portieri.py", title="Portieri", icon="🥅"),
    st.Page("pages/2_Difensori.py", title="Difensori", icon="🛡️"),
    st.Page("pages/3_Centrocampisti.py", title="Centrocampisti", icon="⚙️"),
    st.Page("pages/4_Attaccanti.py", title="Attaccanti", icon="⚔️"),
    st.Page("pages/5_La_Mia_Rosa.py", title="La Mia Rosa", icon="⚽"),
    st.Page("pages/6_Dettaglio_Giocatore.py", title="Dettaglio Giocatore", icon="🔍"),
]
st.navigation(pages).run()
```

`get_db_connection()` resta definita in `app.py` esattamente come oggi: le pagine continuano a
importarla con `from dashboard.app import get_db_connection` senza modifiche. I nomi dei file in
`pages/` non cambiano, quindi `st.switch_page("pages/6_Dettaglio_Giocatore.py")` in
`components.py:_open_player_detail` continua a funzionare invariato.

`st.navigation` sostituisce la scoperta automatica della cartella `pages/`: non ci sarà più
duplicazione né la voce "app" nel menu.

## 4. Rivalutazione sezioni Top / Semi-top

Con `classify_role` (`ranking/tiers.py`) invariato nella logica, si esegue un'analisi sui dati reali
del database corrente: per ciascun ruolo (P/D/C/A) si contano i giocatori assegnati a ciascun tier
(TOP, SEMI_TOP, TITOLARE_FISSO, BASSO_PREZZO, SCOMMESSA, DA_EVITARE).

Se l'analisi mostra squilibri evidenti (es. un ruolo senza nessun Top, o Semi-top che raccoglie la
maggioranza dei giocatori disponibili di un ruolo rendendolo poco selettivo), si aggiustano le
soglie esistenti in `classify_role` (percentili di `score_pct`/`risk`/`proven` per TOP e SEMI_TOP)
sulla base della distribuzione osservata, non a intuito. Il criterio guida resta quello già
documentato nel modulo: TOP e SEMI_TOP devono restare shortlist curate (poche decine di giocatori
per ruolo al massimo), non partizioni della popolazione.

Questa rivalutazione si esegue dopo aver costruito la simulazione (sezione 5), usandone l'output
come evidenza aggiuntiva sulla distribuzione dei tier attraverso 1000 scenari diversi di
disponibilità giocatori, non solo lo snapshot attuale del db.

## 5. Simulazione di 1000 aste

Nuovo script `fantacalcio/scripts/simulate_auctions.py` (nuova cartella `scripts/` per strumenti di
validazione/analisi one-off, distinta da `pipeline/` che è per i job di produzione).

Per ciascuna delle 1000 aste simulate:

- si parte dal pool reale di giocatori nel database (quotazioni, ruoli, score già calcolati);
- si simulano N avversari virtuali (N configurabile, default 7 per una lega da 8) che acquistano
  giocatori con selezione casuale pesata sul Fantasy Value (`score`) tra i disponibili nel proprio
  budget/ruolo/slot ancora liberi — più alto lo score, più probabile la scelta, ma non deterministico;
- "io" acquisto seguendo il motore di raccomandazione già esistente (`get_squad_suggestions` /
  `purchase_advisor`), scegliendo ogni turno il miglior candidato realistico per lo slot più urgente;
- il turno alterna acquirenti finché tutti i budget/slot sono esauriti o non restano giocatori
  compatibili.

Dopo ogni asta simulata si verificano questi invarianti:

- nessun budget (mio o di un avversario) va sotto zero;
- nessun giocatore viene assegnato a più di un acquirente;
- `classify_role`/`compute_budget_summary`/l'optimizer LP non sollevano eccezioni e, se l'LP risulta
  infeasible, lo segnalano in modo pulito invece di crashare;
- i tier prodotti restano non vuoti per i ruoli con abbastanza giocatori disponibili.

A fine delle 1000 run lo script stampa un report aggregato: numero di crash/anomalie (obiettivo 0),
distribuzione spesa per ruolo confrontata col piano studiato 6/16/32/46%, Fantasy Value medio della
rosa finale, dimensione media dei tier per ruolo. Questo report è la base sia per confermare che "i
calcoli hanno senso", sia per la rivalutazione dei tier del punto 4.

Lo script è pensato per esecuzioni manuali ripetute in futuro (nuovo strumento del repo), non per
essere integrato nella dashboard Streamlit.

## 6. Ordine di esecuzione

1. Fix leggibilità Rosa Ideale (sezione 2).
2. Navigazione diretta su Monitoraggio, rimozione pagina "app" (sezione 3).
3. Script di simulazione 1000 aste, esecuzione e report (sezione 5).
4. Rivalutazione soglie Top/Semi-top sulla base dei dati reali + risultati della simulazione
   (sezione 4).

## 7. Nota sul repository git

La working directory è tracciata da un repository git la cui radice (`git rev-parse
--show-toplevel`) è l'intera home directory dell'utente (`C:/Users/Luca.Mercanzin`), attualmente
senza commit (branch `master` vuoto) e con moltissimi file estranei al progetto non tracciati
(`.ssh`, `.aws`-like config, `Documents`, `Downloads`, ecc.). Per questo motivo questa spec **non**
viene committata automaticamente: un primo commit su un repo con radice così ampia rischierebbe di
includere file sensibili o estranei al progetto fantacalcio. Si consiglia all'utente di inizializzare
un repository dedicato a `fantacalcio/` quando vorrà versionare il progetto.
