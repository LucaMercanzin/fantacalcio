"""Static reference info about Serie A teams: city, stadium, rivals, playing style.

This data is general knowledge (club identity, historic rivalries) rather than
live season data, since there is no scraper feeding it. It changes rarely, but
may need manual updates (promotions/relegations, new stadiums).
"""

TEAM_INFO = {
    "Atalanta": {
        "citta": "Bergamo", "stadio": "Gewiss Stadium",
        "rivali": ["Brescia", "Milan", "Inter"],
        "stile": "Pressing alto e aggressivo, costruzione dal basso, tanti uomini in area avversaria.",
    },
    "Bologna": {
        "citta": "Bologna", "stadio": "Renato Dall'Ara",
        "rivali": ["Fiorentina", "Modena"],
        "stile": "Gioco propositivo e verticale, pressing organizzato, squadra fisica.",
    },
    "Cagliari": {
        "citta": "Cagliari", "stadio": "Unipol Domus",
        "rivali": [],
        "stile": "Difesa compatta e ripartenze rapide, attenzione alla fase di non possesso.",
    },
    "Como": {
        "citta": "Como", "stadio": "Giuseppe Sinigaglia",
        "rivali": ["Varese"],
        "stile": "Possesso palla paziente, costruzione dal basso, impostazione da manuale.",
    },
    "Fiorentina": {
        "citta": "Firenze", "stadio": "Artemio Franchi",
        "rivali": ["Juventus", "Bologna", "Empoli"],
        "stile": "Gioco offensivo con esterni a tutta fascia, pressing a tutto campo.",
    },
    "Frosinone": {
        "citta": "Frosinone", "stadio": "Benito Stirpe",
        "rivali": ["Latina"],
        "stile": "Squadra organizzata, gioco di rimessa, compattezza difensiva.",
    },
    "Genoa": {
        "citta": "Genova", "stadio": "Luigi Ferraris",
        "rivali": ["Sampdoria"],
        "stile": "Fisicità, seconde palle, gioco diretto verso gli attaccanti.",
    },
    "Inter": {
        "citta": "Milano", "stadio": "San Siro (Giuseppe Meazza)",
        "rivali": ["Milan", "Juventus"],
        "stile": "Costruzione con i tre difensori, esterni offensivi, manovra fluida.",
    },
    "Juventus": {
        "citta": "Torino", "stadio": "Allianz Stadium",
        "rivali": ["Inter", "Torino", "Fiorentina"],
        "stile": "Solidità difensiva, transizioni rapide, mentalità da risultato.",
    },
    "Lazio": {
        "citta": "Roma", "stadio": "Stadio Olimpico",
        "rivali": ["Roma"],
        "stile": "Palleggio e costruzione dal basso, pressing a uomo, esterni offensivi.",
    },
    "Lecce": {
        "citta": "Lecce", "stadio": "Via del Mare",
        "rivali": ["Bari", "Taranto"],
        "stile": "Difesa organizzata, ripartenze veloci, lotta su ogni pallone.",
    },
    "Milan": {
        "citta": "Milano", "stadio": "San Siro (Giuseppe Meazza)",
        "rivali": ["Inter", "Juventus"],
        "stile": "Gioco verticale e rapido, ampiezza con i terzini, pressing offensivo.",
    },
    "Monza": {
        "citta": "Monza", "stadio": "U-Power Stadium",
        "rivali": ["Como"],
        "stile": "Costruzione dal basso, squadra tecnica e propositiva.",
    },
    "Napoli": {
        "citta": "Napoli", "stadio": "Diego Armando Maradona",
        "rivali": ["Roma", "Juventus"],
        "stile": "Palleggio veloce, ampiezza, transizioni offensive rapide.",
    },
    "Parma": {
        "citta": "Parma", "stadio": "Ennio Tardini",
        "rivali": ["Reggiana"],
        "stile": "Squadra organizzata e propositiva, attenzione alla fase di transizione.",
    },
    "Roma": {
        "citta": "Roma", "stadio": "Stadio Olimpico",
        "rivali": ["Lazio", "Napoli"],
        "stile": "Blocco compatto, ripartenze rapide, fisicità in attacco.",
    },
    "Sassuolo": {
        "citta": "Sassuolo", "stadio": "Mapei Stadium",
        "rivali": ["Modena"],
        "stile": "Palleggio e costruzione dal basso, gioco tecnico e propositivo.",
    },
    "Torino": {
        "citta": "Torino", "stadio": "Stadio Olimpico Grande Torino",
        "rivali": ["Juventus", "Cagliari"],
        "stile": "Intensità e pressing, squadra fisica e organizzata.",
    },
    "Udinese": {
        "citta": "Udine", "stadio": "Bluenergy Stadium",
        "rivali": ["Triestina"],
        "stile": "Fisicità e ripartenze, attenzione ai calci piazzati.",
    },
    "Venezia": {
        "citta": "Venezia", "stadio": "Pier Luigi Penzo",
        "rivali": ["Padova", "Vicenza"],
        "stile": "Squadra organizzata, gioco di rimessa e compattezza difensiva.",
    },
}


def get_team_info(team_name: str) -> dict | None:
    return TEAM_INFO.get(team_name)


ROLE_TASK = {
    "P": "para e avvia la costruzione dal basso quando richiesto dallo stile di squadra.",
    "D": "imposta la difesa e partecipa alla costruzione o alle ripartenze a seconda dello stile.",
    "C": "fa da cerniera tra difesa e attacco, il cui coinvolgimento dipende molto dallo stile di squadra.",
    "A": "punta di riferimento offensivo, il cui rendimento dipende da quanto lo stile di squadra lo serve.",
}

# Ogni voce: (parola chiave da cercare nel testo "stile", {ruolo: (pro, contro)}).
# Valutazione generale basata sul tipo di gioco della squadra, non un dato
# statistico: aiuta a capire perché uno stile aiuta o penalizza un ruolo,
# non è una previsione di rendimento.
STYLE_ROLE_FIT = [
    ("pressing alto", {
        "P": ("Più palloni giocati con i piedi, occasioni di assist.", "Rischio di errori sotto pressione avversaria."),
        "D": ("Recuperi alti, occasioni di ripartenza offensiva.", "Spazio alle spalle da coprire, rischio di essere saltato."),
        "C": ("Tanti recuperi palla, occasioni da interdittore.", "Dispendio fisico alto, rischio ammonizioni."),
        "A": ("Più palloni recuperati vicino alla porta avversaria.", "Fatica accumulata riduce la lucidità sotto porta."),
    }),
    ("costruzione dal basso", {
        "P": ("Coinvolto nella manovra, può accumulare assist.", "Rischio di errori in uscita che regalano gol."),
        "D": ("Più tocchi e possibilità di lanci/assist per i difensori tecnici.", "Rischio perdita palla in zona pericolosa."),
        "C": ("Regista/mediano ben servito, tanti palloni giocati.", "Poco pericoloso se non ha compiti offensivi."),
        "A": ("Meno isolato, può abbassarsi a far salire la squadra.", "Meno occasioni dirette in area avversaria."),
    }),
    ("palleggio", {
        "P": ("Coinvolto nella manovra.", "Rischio di errori in uscita."),
        "D": ("Più occasioni di impostazione e assist.", "Rischio perdita palla in zona pericolosa."),
        "C": ("Centrale nella manovra, tanti tocchi.", "Poco pericoloso se non ha licenza di inserimento."),
        "A": ("Riceve più palloni giocabili in area.", "Deve adattarsi ai tempi lenti della manovra."),
    }),
    ("verticale", {
        "P": ("Meno pressione prolungata sui piedi.", "Più lanci lunghi da gestire con precisione."),
        "D": ("Meno rischio in costruzione.", "Meno occasioni di assist da impostazione."),
        "C": ("Inserimenti rapidi, occasioni da gol/assist per mezzali.", "Meno tocchi se non è il terminale della verticalizzazione."),
        "A": ("Molti palloni giocabili in profondità: bonus gol più probabili.", "Isolamento se il supporto della squadra è scarso."),
    }),
    ("gioco diretto", {
        "P": ("Meno pressione prolungata sui piedi.", "Rilanci frequenti da gestire."),
        "D": ("Meno rischio palla al piede.", "Meno occasioni di costruzione/assist."),
        "C": ("Più seconde palle da raccogliere.", "Meno tocchi in fase di possesso prolungato."),
        "A": ("Riceve molti palloni diretti: favorisce attaccanti fisici.", "Penalizza attaccanti che preferiscono giocare palla a terra."),
    }),
    ("ripartenze", {
        "P": ("Meno assedio prolungato in area.", "Deve essere rapido su rilanci e transizioni."),
        "D": ("Meno rischio nella costruzione.", "Poche occasioni di assist."),
        "C": ("Occasioni da gol/assist in transizione se ha buona corsa.", "Poco coinvolto nel possesso prolungato."),
        "A": ("Spazi da attaccare in campo aperto: favorisce attaccanti veloci.", "Poche palle giocabili se la squadra non recupera alta."),
    }),
    ("contropiede", {
        "P": ("Meno assedio prolungato in area.", "Deve essere rapido su rilanci e transizioni."),
        "D": ("Meno rischio nella costruzione.", "Poche occasioni di assist."),
        "C": ("Occasioni da gol/assist in transizione se ha buona corsa.", "Poco coinvolto nel possesso prolungato."),
        "A": ("Spazi da attaccare in campo aperto: favorisce attaccanti veloci.", "Poche palle giocabili se la squadra non recupera alta."),
    }),
    ("fisicità", {
        "P": ("Meno seconde palle pericolose in area piccola.", "Nessun impatto diretto."),
        "D": ("Meno duelli aerei persi.", "Rischio ammonizioni nei contrasti."),
        "C": ("Recupera più palloni nei duelli.", "Meno spazio per giocatori tecnici e di talento puro."),
        "A": ("Favorisce attaccanti fisici: più rigori/gol di rapina.", "Penalizza attaccanti rapidi e tecnici."),
    }),
    ("esterni a tutta fascia", {
        "P": ("Nessun impatto diretto.", "Più spazio da coprire se gli esterni si sganciano."),
        "D": ("Esterni/terzini con licenza offensiva: occasioni di assist/gol.", "Più spazio da coprire in ripiegamento."),
        "C": ("Più ampiezza libera spazi centrali per gli inserimenti.", "Meno palloni se il gioco passa dalle fasce."),
        "A": ("Riceve più cross e palloni in area.", "Meno spazio se gioca spalle alla porta senza rifornimenti."),
    }),
    ("ampiezza", {
        "P": ("Nessun impatto diretto.", "Più spazio da coprire se gli esterni si sganciano."),
        "D": ("Terzini con licenza offensiva: occasioni di assist/gol.", "Più spazio da coprire in ripiegamento."),
        "C": ("Più spazi centrali per gli inserimenti.", "Meno palloni se il gioco passa dalle fasce."),
        "A": ("Riceve più cross e palloni in area.", "Dipende dalla qualità dei rifornimenti dalle fasce."),
    }),
    ("tre difensori", {
        "P": ("Costruzione più protetta, meno rischio diretto.", "Nessun impatto diretto."),
        "D": ("Centrale con più tempo/spazio per impostare: occasioni di assist.", "Meno protezione individuale, più responsabilità in marcatura."),
        "C": ("Riceve più supporto dai centrali in costruzione.", "Nessun impatto diretto rilevante."),
        "A": ("Nessun impatto diretto.", "Nessun impatto diretto."),
    }),
]


def get_role_fit(team_name: str, role_classic: str, role_mantra: str | None = None) -> dict | None:
    """Compito del giocatore nello stile della sua squadra, con pro e contro
    di quello stile per il suo ruolo. È una lettura generale basata sul tipo
    di gioco della squadra (vedi TEAM_INFO), non un dato statistico."""
    team_info = TEAM_INFO.get(team_name)
    if not team_info or role_classic not in ROLE_TASK:
        return None

    stile = team_info["stile"].lower()
    pros, contros = [], []
    for keyword, role_map in STYLE_ROLE_FIT:
        if keyword in stile and role_classic in role_map:
            pro, contro = role_map[role_classic]
            if pro not in pros:
                pros.append(pro)
            if contro not in contros:
                contros.append(contro)

    if not pros and not contros:
        return None

    return {
        "compito": ROLE_TASK[role_classic],
        "pro": pros,
        "contro": contros,
    }
