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
        "rivali": ["Torino"],
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
