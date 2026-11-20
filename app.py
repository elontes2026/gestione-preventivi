import streamlit as st
import pandas as pd
import re
import os
from datetime import datetime
from supabase import create_client

# 🔐 Credenziali da variabili d'ambiente (sicuro!)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ Credenziali Supabase mancanti. Contatta l'amministratore.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURAZIONE ---
TECNICI = {
    'BONAZZA': {'prefisso': 'ER', 'nome': 'Bonazza'},
    'ESPA': {'prefisso': 'ER', 'nome': 'Espa'},
    'TENNERIELLO': {'prefisso': 'ER', 'nome': 'Tenneriello'},
    'SCACCHETTI': {'prefisso': 'ER', 'nome': 'Scacchetti'},
    'TESSITORE': {'prefisso': 'ER', 'nome': 'Tessitore'},
    'USAI': {'prefisso': 'T', 'nome': 'Usai'},
}

TIPOLOGIE = ['EXTRA CANONE', 'DECOR EASY', 'SAFETY', 'PIANIFICATA 2027', 'RINA', 'EMAIL']
TIPI_DOC = ['PREVENTIVO', 'CONSUNTIVO']
STATI = ['INVIATO IN ATTESA ODS', 'REALIZZATO', 'REALIZZATO E FATTURATO', 'RESPINTO', 'SOSPESO']

# --- FUNZIONE PROGRESSIVO ---
def genera_progressivo(prefisso):
    anno = datetime.now().strftime('%y')
    response = supabase.table('preventivi').select('protocollo').eq('prefisso', prefisso).execute()
    
    max_num = 0
    for row in response.data:
        match = re.search(r'_(\d+)/', row['protocollo'])
        if match and f"/{anno}" in row['protocollo']:
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    
    return f"{prefisso}_{str(max_num + 1).zfill(3)}/{anno}"

# --- INTERFACCIA ---
st.set_page_config(page_title="Gestione Preventivi", layout="wide")
st.title("📋 Commessa 790 - Unicredit FM 2026/2031")

# Sidebar
st.sidebar.title("👤 Login Tecnico")
tecnico_sel = st.sidebar.selectbox("Seleziona il tuo nome:", list(TECNICI.keys()))

if tecnico_sel == 'USAI':
    area = st.sidebar.selectbox("Area:", ['T (Toscana)', 'MU (Marche/Umbria)'])
    prefisso = 'T' if area.startswith('T') else 'MU'
else:
    prefisso = TECNICI[tecnico_sel]['prefisso']

st.sidebar.info(f"**{TECNICI[tecnico_sel]['nome']}**\nPrefisso: `{prefisso}`")

# Tabs
tab1, tab2 = st.tabs(["➕ Nuovo Documento", "📊 Elenco Documenti"])

with tab1:
    st.subheader("Registra nuovo documento")
    st.info(f"Il protocollo verrà generato automaticamente con prefisso **{prefisso}**")
    
    with st.form("nuovo_doc"):
        col1, col2 = st.columns(2)
        with col1:
            tipo_doc = st.selectbox("Tipo Documento *", TIPI_DOC)
            tipo_rich = st.selectbox("Tipologia Richiesta *", TIPOLOGIE)
            comune = st.text_input("Comune *")
            indirizzo = st.text_input("Indirizzo *")
            descrizione = st.text_area("Descrizione Intervento *", height=100)
        with col2:
            importo = st.number_input("Importo (€)", min_value=0.0, step=0.01, format="%.2f")
            numero_oda = st.text_input("N° ODA")
            data_oda = st.date_input("Data ODA", value=None)
            stato = st.selectbox("Stato", STATI)
            rem = st.text_input("REM Riferimento")
            note = st.text_area("Note")
        
        if st.form_submit_button("💾 Registra Documento", use_container_width=True):
            if not comune or not indirizzo or not descrizione:
                st.error("⚠️ Compila i campi obbligatori (*)")
            else:
                protocollo = genera_progressivo(prefisso)
                dati = {
                    'protocollo': protocollo,
                    'tecnico': TECNICI[tecnico_sel]['nome'],
                    'prefisso': prefisso,
                    'tipologia_richiesta': tipo_rich,
                    'tipo_documento': tipo_doc,
                    'numero_oda': numero_oda or None,
                    'data_oda': str(data_oda) if data_oda else None,
                    'comune': comune,
                    'indirizzo': indirizzo,
                    'descrizione': descrizione,
                    'importo': importo if importo > 0 else None,
                    'rem_riferimento': rem or None,
                    'stato_documento': stato,
                    'note': note or None,
                    'creato_da': tecnico_sel
                }
                try:
                    supabase.table('preventivi').insert(dati).execute()
                    supabase.table('audit_log').insert({
                        'protocollo': protocollo,
                        'azione': 'CREAZIONE',
                        'utente': tecnico_sel,
                        'dettaglio': f"Documento creato da {tecnico_sel}"
                    }).execute()
                    st.success(f"✅ Documento registrato!\n\n**Protocollo: {protocollo}**")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Errore: {e}")

with tab2:
    st.subheader("Elenco documenti")
    
    col1, col2 = st.columns(2)
    with col1:
        filtro_tecnico = st.selectbox("Filtra tecnico:", ['Tutti'] + list(TECNICI.keys()))
    with col2:
        filtro_stato = st.selectbox("Filtra stato:", ['Tutti'] + STATI)
    
    query = supabase.table('preventivi').select('*').order('creato_il', desc=True)
    if filtro_tecnico != 'Tutti':
        query = query.eq('tecnico', TECNICI[filtro_tecnico]['nome'])
    if filtro_stato != 'Tutti':
        query = query.eq('stato_documento', filtro_stato)
    
    response = query.execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        cols = ['protocollo', 'tecnico', 'tipo_documento', 'comune', 'descrizione', 'importo', 'stato_documento', 'creato_il']
        st.dataframe(df[cols], use_container_width=True)
        st.download_button("📥 Scarica CSV", df.to_csv(index=False).encode('utf-8'), "preventivi.csv", "text/csv")
    else:
        st.info("Nessun documento presente. Vai nella tab 'Nuovo Documento' per registrarne uno.")