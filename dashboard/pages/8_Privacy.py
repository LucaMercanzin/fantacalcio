import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import streamlit as st

from dashboard.styles import inject_global_css

inject_global_css()

st.title("Privacy e fonti dei dati")
st.caption(
    "Informazioni essenziali su cosa fa questa app. Bozza da completare: i campi "
    "tra parentesi quadre vanno compilati dal gestore prima della pubblicazione."
)

st.subheader("Chi gestisce l'app")
st.markdown(
    "Titolare del trattamento: [DA FORNIRE: nome o ragione sociale del titolare]  \n"
    "Contatto per richieste privacy: [DA FORNIRE: indirizzo email dedicato]"
)

st.subheader("Cosa fa l'app")
st.markdown(
    "- La consultazione è pubblica: non serve un account e l'app non chiede dati ai visitatori.\n"
    "- L'app non ha un sistema di account e non usa strumenti di analisi o pubblicità propri "
    "(verificato nel codice dell'app: nessun script di analytics, pixel o CDN esterno).\n"
    "- Le azioni che modificano dati (registrare acquisti, segnare avversari, modificare pesi "
    "e conferme dei match) sono protette da una password di gestione. La password non è "
    "memorizzata in chiaro; l'app conserva solo un hash configurato dal gestore.\n"
    "- L'unico collegamento esterno cliccabile nell'app è il profilo Transfermarkt di un "
    "giocatore: si apre solo su scelta dell'utente."
)

st.subheader("Dati trattati")
st.markdown(
    "**Dati dei giocatori di Serie A** (nome, squadra, ruolo, quotazioni, statistiche, "
    "infortuni, date di nascita e nazionalità, foto): provengono da fonti pubbliche, "
    "elencate sotto. Non sono dati personali raccolti dai visitatori.\n\n"
    "**Dati inseriti dal gestore**: acquisti della propria rosa (giocatore, prezzo, data), "
    "acquisti segnati come presi dagli avversari (incluso il **nome dell'avversario**, che "
    "riguarda una terza persona), pesi delle fonti e degli esiti di abbinamento dei nomi.\n\n"
    "**Dati tecnici del servizio di hosting**: vedi la sezione seguente."
)

st.subheader("Fonti dei dati")
st.markdown(
    "I dati sono raccolti dal gestore con gli script della cartella `scrapers/` da questi siti "
    "pubblici. Il visitatore non viene collegato a questi siti dall'app:\n\n"
    "- fantacalcio.it (quotazioni, voti, rigoristi)\n"
    "- fantanalisi.it (valutazioni, squadre, calendario, statistiche giocatori)\n"
    "- fantapazz.com (quotazioni)\n"
    "- pianetafanta.it (quotazioni)\n"
    "- fantacalciopedia.com (lista calciatori, metriche)\n"
    "- api.fantacalcio-online.com (stime prezzi d'asta)\n"
    "- transfermarkt.it (profili, infortuni, foto)\n"
    "- it.wikipedia.org (foto, tramite API pubblica)\n\n"
    "L'app non certifica l'accuratezza dei dati: verificare sempre sulla fonte."
)

st.subheader("Hosting e fornitori terzi")
st.markdown(
    "L'app è pubblicata su Streamlit Community Cloud, servizio di Streamlit, che tratta i "
    "dati tecnici necessari a erogare il servizio secondo la propria informativa.\n\n"
    "[DA VERIFICARE: quali dati tecnici tratta il fornitore, con quale ruolo ai sensi del GDPR "
    "(responsabile o titolare autonomo), dove sono conservati e per quanto tempo. "
    "Non verificato in questo audit.]"
)

st.subheader("Cookie")
st.markdown(
    "Il codice dell'app non imposta cookie propri né strumenti di tracciamento (verificato "
    "nel codice). [DA VERIFICARE: eventuali cookie impostati dal servizio di hosting, vedi "
    "sopra. Finché non verificati, non è dichiarata l'assenza di cookie non essenziali e il "
    "banner di consenso resta un punto aperto dell'audit.]"
)

st.subheader("Conservazione")
st.markdown(
    "[DA FORNIRE: per quanto tempo si conservano acquisti, avversari e log del servizio, "
    "e come si chiede la cancellazione.]"
)

st.subheader("Diritti dell'interessato")
st.markdown(
    "Per accesso, rettifica, cancellazione o opposizione (artt. 15-22 GDPR) scrivere a "
    "[DA FORNIRE: contatto privacy]. Per i dati dei giocatori, che sono pubblici, la "
    "correzione va chiesta alla fonte originale."
)

st.subheader("Aggiornamento")
st.markdown(
    "Data di ultimo aggiornamento: [DA FORNIRE: data di pubblicazione]. "
    "Questa pagina descrive il comportamento del codice alla data di redazione; "
    "va rivista quando cambiano dati, fonti o hosting."
)
