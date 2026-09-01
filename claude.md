# AI RULES — rimando ad AGENTS.md

@AGENTS.md

---

Le regole operative di questo progetto vivono in un file solo:
[`AGENTS.md`](AGENTS.md). La riga `@AGENTS.md` qui sopra lo importa, quindi
Claude Code le legge esattamente come se fossero scritte qui.

**Perché questo file non contiene più le regole** (BACKLOG-2026-08-31 §10).
Fino al 31/08/2026 `AGENTS.md` e `claude.md` erano due copie byte-identiche
di 11.074 byte l'una. Non era un problema di spazio: era che una modifica
alle regole finiva su una sola delle due, e l'altra restava indietro senza
che nulla lo segnalasse. Due file che devono dire la stessa cosa e possono
divergere in silenzio prima o poi divergono.

`AGENTS.md` è la copia canonica perché è il nome che leggono anche gli altri
agenti (Codex, Cursor, Gemini CLI), mentre `claude.md` lo legge solo Claude
Code — che però sa seguire un import, e quindi può fare da rimando senza
perdere niente.

**Se devi cambiare le regole, cambia `AGENTS.md`.**
