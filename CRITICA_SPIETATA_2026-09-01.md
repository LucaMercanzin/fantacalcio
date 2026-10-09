# Fantacalcio: critica spietata, ma chiudibile entro stasera

Data: 1 settembre 2026

## Verdetto

Il progetto non è un disastro: ha molti test, lint pulito e parecchie decisioni documentate. Il problema è più irritante: sotto una superficie molto diligente conserva alcuni errori operativi banali, file-monolite e automazioni duplicate che fanno spendere attenzione nel posto sbagliato. Sembra più controllato di quanto sia davvero.

Questa lista esclude volutamente rifacimenti, nuove architetture e lavori da più giorni. Ogni punto è risolvibile oggi con una patch piccola e verificabile. Ordine consigliato: 1, 2, 3, 4, poi il resto.

## 1. Il controllo più importante arriva quando ormai non può più proteggere nulla

**Severità:** critica  
**Tempo:** 45–75 minuti

In `pipeline/run_scraping.py`, il run viene committato e registrato come `ok`; poi vengono calcolati stagione e consenso; solo alla fine viene verificato `NEW_PLAYER_SURGE_RATIO`. Se lo scraper ha prodotto un'ondata assurda di nuovi giocatori, il codice alza correttamente `NewPlayerSurgeError`, ma troppo tardi: i dati sospetti sono già persistiti e il run risulta riuscito nel database.

È un allarme antincendio montato dopo l'uscita dell'edificio: fa rumore, non protegge il dato.

**Fix minimo:** calcolare e validare il surge prima del `commit()` e di `finish_scraping_run(... status="ok")`. In alternativa, se il commit anticipato è intenzionale, registrare uno stato esplicito `warning`/`quarantined` e non materializzare il consenso.

**Accettazione:** un test con un numero anomalo di nuovi giocatori deve lasciare invariati i dati precedenti e registrare il run come fallito/quarantinato, mai `ok`.

## 2. `.gitignore` finge di proteggere artefatti che Git sta già trascinando

**Severità:** alta  
**Tempo:** 20–40 minuti

`.gitignore` esclude `data/fantacalcio.db` e `data/photos/`, ma entrambi sono già tracciati. Risultato verificato: database da circa 3,66 MB e 817 immagini per circa 42,93 MB dentro la storia del repository. Il repository pesa circa 37,5 MB solo nei pack Git.

Questa è igiene da repository fatta a metà: la regola esiste, ma non produce l'effetto promesso. Inoltre un database mutabile versionato rende facilissimo mescolare dati locali e modifiche di codice.

**Fix minimo:** rimuovere database e foto dall'indice Git senza cancellarli localmente (`git rm --cached` sui target espliciti), aggiungere un piccolo dataset/fixture riproducibile e documentare il comando di bootstrap dei dati.

**Accettazione:** `git ls-files data/fantacalcio.db data/photos` non deve restituire nulla; test e avvio devono funzionare con fixture o bootstrap documentato.

## 3. Il lint è verde perché avete spento proprio il rilevatore che serviva

**Severità:** alta  
**Tempo:** 60–90 minuti

`pyproject.toml` ignora globalmente `BLE001`, cioè l'uso indiscriminato di `except Exception`. Nel codice applicativo ce ne sono numerosi, inclusi `dashboard/components.py`, `pipeline/run_scraping.py`, vari runner e scraper. Ruff quindi stampa “All checks passed” mentre una categoria intera di errori viene deliberatamente resa invisibile.

Un semaforo verde ottenuto scollegando la lampadina rossa non è qualità.

**Fix minimo:** rimuovere `BLE001` dagli ignore globali; restringere le eccezioni dove il tipo è noto; usare ignore locali, commentati, soltanto nei confini di processo dove il catch-all è davvero necessario e viene sempre loggato/rilanciato.

**Accettazione:** `ruff check .` passa con `BLE001` attivo e nessun `except Exception` silenzioso.

## 4. Tre pipeline CI fanno lo stesso lavoro con tre verità diverse

**Severità:** alta  
**Tempo:** 30–60 minuti

Esistono `ci.yml`, `lint.yml` e `python-package-conda.yml`. La prima testa Python 3.11/3.12 con pip; la seconda esegue Ruff; la terza parte a ogni push, usa ancora `actions/setup-python@v3`, installa Conda, aggiunge Flake8 al volo e riesegue pytest. Non è ridondanza utile: sono ambienti e regole divergenti che possono dare risultati discordanti sullo stesso commit.

È una slot machine CI: tre leve, tre tempi, nessuna singola risposta autorevole.

**Fix minimo:** eliminare o rendere manuale il workflow Conda se non rappresenta un ambiente di produzione; in alternativa incorporarlo esplicitamente nella matrice principale. Conservare un solo lint autorevole (Ruff) e un solo comando test.

**Accettazione:** ogni push/PR produce un unico verdetto lint e una matrice test chiaramente dichiarata, senza doppio pytest equivalente.

## 5. `dashboard/components.py` è diventato il cassetto dove finisce tutto

**Severità:** alta  
**Tempo:** 2–3 ore

Il file conta circa 2.005 righe. Contiene grafici, foto, CSS globale, card, dettaglio giocatore, verdetti, intelligence d'asta, valutatore acquisto, tier, correlazioni e portieri. `_inject_card_css` occupa circa 337 righe; `render_player_detail` circa 352 e ha complessità stimata 104. Non è “un componente”: è quasi tutta l'interfaccia compressa in un file.

Ogni patch qui richiede memoria enciclopedica e rende la review una caccia al tesoro.

**Fix minimo per stasera:** estrarre soltanto due blocchi coesi, senza redesign: CSS in un modulo/file dedicato e dettaglio giocatore in `dashboard/player_detail.py`, mantenendo firme pubbliche e import compatibili.

**Accettazione:** `components.py` scende sensibilmente sotto le 1.400 righe; i test di `tests/test_components.py` restano verdi (baseline verificata: 28 passati); nessun cambiamento visivo intenzionale.

## 6. Un'immagine corrotta viene trattata come immagine valida

**Severità:** media  
**Tempo:** 20–35 minuti

`dashboard/components.py::_looks_like_crest` cattura qualsiasi `Exception` e restituisce `False`. Quindi file corrotti, errori I/O o bug Pillow diventano silenziosamente “non è uno stemma”, cioè una foto accettabile. Il fallback non è neutro: trasforma un errore tecnico in un dato positivo.

**Fix minimo:** catturare le eccezioni Pillow/I/O attese, loggare il path/contesto e restituire uno stato tri-valued (`True`, `False`, `None`) oppure rifiutare l'immagine in caso di errore.

**Accettazione:** test con bytes corrotti; l'immagine non viene accettata come foto e l'errore è osservabile.

## 7. La stagione corrente è una bomba a orologeria manuale

**Severità:** media  
**Tempo:** 30–60 minuti

`config.py` fissa `CURRENT_SEASON = "2026/27"`. È centralizzato, quindi meglio delle copie sparse, ma resta uno stato operativo che scade e che nessun controllo obbliga ad aggiornare. Il giorno del rollover il software può continuare a filtrare dati con la stagione vecchia senza fallire rumorosamente.

Centralizzare un valore sbagliato significa soltanto sbagliare in modo coerente.

**Fix minimo:** leggere la stagione da variabile d'ambiente/config locale con default calcolato e validato, oppure aggiungere un controllo di startup che fallisca/avvisi quando la data non è compatibile con `CURRENT_SEASON`.

**Accettazione:** test sui confini giugno/luglio e override esplicito documentato.

## 8. La qualità misurata premia il volume di test ma non impone copertura

**Severità:** media  
**Tempo:** 45–75 minuti

La suite è ampia e Ruff passa, ma la CI esegue soltanto `pytest -q`: non misura né impone copertura. Con file centrali molto complessi (`dashboard/components.py`, `consensus/engine.py`) è possibile aggiungere rami non testati mantenendo tutto verde.

“Ci sono tanti test” non equivale a “i punti fragili sono testati”. Senza una soglia, il numero è una sensazione.

**Fix minimo:** aggiungere `pytest-cov` alle dipendenze dev, produrre il report `term-missing` e impostare una soglia iniziale realistica basata sul valore corrente, senza inseguire il 100%.

**Accettazione:** la CI fallisce se la copertura totale scende sotto la baseline e mostra le righe mancanti.

## Piano da una sera

1. Spostare il surge check prima del commit e aggiungere il test di rollback/quarantena.
2. Riattivare `BLE001` e correggere solo i catch realmente silenziosi.
3. Smettere di tracciare DB e foto, aggiungendo fixture/bootstrap.
4. Consolidare i workflow CI.
5. Estrarre CSS e player detail dal monolite.
6. Correggere il fallback immagini, rendere esplicita la stagione e aggiungere coverage gate.

## Verifiche eseguite

- Scansione Graphify: 191 file, circa 367.000 parole; AST di 138 file di codice con 1.505 nodi e 4.419 relazioni.
- `ruff check`: verde nello stato attuale, con la limitazione critica `BLE001` descritta sopra.
- `tests/test_components.py`: 28 test passati usando una directory temporanea nel workspace.
- Analyzer strutturale: 128 file Python, voto medio B; i segnali più gravi sono concentrati nei monoliti `dashboard/components.py` e `consensus/engine.py`.
- La suite completa non è stata certificata in questa sessione: la directory temporanea predefinita di pytest è inaccessibile nel sandbox e il run completo con `--basetemp` non ha prodotto un riepilogo conclusivo entro la finestra del runner. Non viene quindi dichiarata verde.

## Cose che non ho messo apposta

Niente microservizi, niente cambio database, niente riscrittura Streamlit, niente “mettiamo tutto async”, niente refactoring totale di `consensus/engine.py`. Sarebbero critiche facili da scrivere e impossibili da chiudere entro stasera: quindi sarebbero soltanto rumore.
