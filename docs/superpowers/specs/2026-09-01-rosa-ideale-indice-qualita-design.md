# Rosa Ideale: da piano d'acquisto rotto a indice di qualità

Data: 1 settembre 2026

## Problema

La Rosa Ideale mostrata in `dashboard/pages/5_La_Mia_Rosa.py` è un'euristica
greedy (`ranking/ideal_squad.py::build_ideal_squad`) che nella stessa pagina
convive con un LP solver che la domina su ogni metrica. Misurato sul DB reale
(budget 500, rosa vuota, 2026-09-01):

| | Rosa Ideale (euristica) | Rosa Ottimale (LP) |
|---|---|---|
| Giocatori | 18 (11+7) | 25 (rosa legale) |
| Speso | 356.6 / 476 | 498.6 / 500 |
| Budget inutilizzato | 119.4 (25%) | 1.4 |
| Portiere titolare | Stankovic (1.1) | Svilar (36.2) |

Tre difetti strutturali, non di taratura:

1. **Il 25% del budget resta non speso.** I budget per ruolo sono tetti
   rigidi: nessun travaso tra ruoli, nessuna saturazione possibile.
2. **`decision_score` premia il rapporto qualità/prezzo**, non la qualità.
   L'euristica rastrella occasioni da 1.1 crediti e poi non sa spendere il
   resto.
3. **La rosa è illegale**: 18 giocatori invece di 3/8/8/6. Non schierabile.

Due rami sono inoltre codice morto:

- `_form_factor` non si attiva mai: `get_ideal_formation` non passa
  `recent_form_by_player`.
- `AVAILABILITY_PENALTY` non si attiva mai: legge una chiave `status` che
  sulle righe giocatore non esiste (l'unico `status` del progetto è la salute
  *delle tabelle* in `get_data_quality_report`, un'altra cosa).

## Decisione

La Rosa Ideale smette di essere un piano d'acquisto e diventa **un indice di
qualità**: i 25 giocatori più forti che si potrebbero ancora avere, **senza
vincolo di spesa**. Un giocatore può costare 500 crediti da solo.

Questo la rende una domanda diversa da quella della Rosa Ottimale LP ("cosa
posso davvero permettermi"), invece che una risposta peggiore alla stessa
domanda. Le due sezioni smettono di competere.

### Criterio

`score` (Fantasy Value, `ranking/scorer.py::compute_score`): produzione reale
scalata su quanto il giocatore è titolare, penalizzata se indisponibile.
**Non contiene il prezzo** — è forza pura, che è il criterio richiesto.
`decision_score` viene abbandonato proprio perché il prezzo ce l'ha dentro.

Slot regolamentari `config.ROLE_SLOTS` (3 P / 8 D / 8 C / 6 A).

### Esclusioni

- **Infortunati alla data odierna.**
- **Giocatori già presi dagli avversari** (`repository.get_opponent_picks`).
- **Chi ha giocato troppo poco** (`RELIABLE_APPEARANCES_MIN`, filtro già
  esistente): senza, uno score gonfiato su 2 presenze entra in rosa.

Non si escludono i giocatori già in rosa propria: l'indice descrive la qualità
disponibile, non gli acquisti mancanti.

### Infortuni: vincolo sui dati

`player_injuries` contiene 16 infortuni che coprono oggi, ma le date sono
stringhe `GG/MM/AAAA`, non ISO. Vanno parsate in Python: un confronto SQL
`date_to >= '2026-09-01'` compara stringhe e restituisce 1619 righe prive di
senso.

Nessuno dei 16 infortunati rientra oggi nella top-25, quindi il filtro non
cambia la rosa al momento dell'implementazione. Va scritto lo stesso: è il
tipo di filtro che conta esattamente il giorno in cui conta.

Righe con date non parsabili vengono ignorate (giocatore considerato
disponibile) invece di far fallire il calcolo: un archivio storico con formati
sporchi non deve poter svuotare l'indice.

## Modifiche

1. **Nuovo `get_currently_injured_ids(conn)`** in `dashboard/data_access.py`:
   legge `player_injuries`, parsa `GG/MM/AAAA`, restituisce gli id con un
   infortunio che copre la data di riferimento (default: oggi; parametrizzata
   per i test).

2. **`get_ideal_squad(conn)`** passa da `limit_per_role=5` a `ROLE_SLOTS` e
   applica le esclusioni. Restituisce anche il costo teorico totale, mostrato
   come misura di quanto la realtà obbliga a scendere a compromessi.

3. **Pagina 5 e sidebar** consumano `get_ideal_squad`. Sparisce la tabella di
   confronto Rosa Ideale vs LP: mette a paragone due risposte a domande
   diverse.

4. **`ranking/ideal_squad.py` si riduce alle `FORMATIONS`.** Rimossi
   `build_ideal_squad`, `compute_ideal_score`, `compare_starters_to_lp`,
   `BENCH_COVERAGE`, `WEIGHT_FORM`, `WEIGHT_RELIABILITY`,
   `AVAILABILITY_PENALTY`, `_reliability_factor`, `_form_factor`.

5. **La Rosa Ottimale LP resta invariata.**

## Risultato atteso

Rosa ideale al 2026-09-01, costo teorico ~1001 crediti (≈2× budget):

- **P**: Svilar, Butez, Carnesecchi
- **D**: Dimarco, Kalulu, Mancini, Pavlovic, Chalobah, Zappacosta, Hainaut, Doekhi
- **C**: Paz, Vlasic, McTominay, Orsolini, Da Cunha, Zaniolo, Busio, Pulisic
- **A**: Lautaro, Douvikas, Hojlund, Yildiz, Thuram, Lauriente'

## Test

- `get_currently_injured_ids`: infortunio in corso incluso; concluso escluso;
  futuro escluso; data non parsabile ignorata senza sollevare eccezione.
- `get_ideal_squad`: rispetta `ROLE_SLOTS`; esclude infortunati e presi dagli
  avversari; ordina per `score` e non per `decision_score`; ignora il budget
  (un giocatore che costa più dell'intero budget entra se è il più forte).
- `tests/test_ideal_squad.py` riscritto sui confini rimasti; i test delle
  funzioni rimosse spariscono con loro.
- `tests/test_config.py` resta valido (usa solo `FORMATIONS`).
