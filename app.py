import streamlit as st
import pandas as pd
import plotly.express as px
import re
import os
from datetime import datetime
from supabase import create_client
from fpdf import FPDF
from io import BytesIO

# 🔐 Credenziali da variabili d'ambiente
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ Credenziali Supabase mancanti. Contatta l'amministratore.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURAZIONE ---
TECNICI = {
    'BONAZZA': {'prefisso': 'ER', 'nome': 'Bonazza', 'regione': 'Emilia-Romagna'},
    'ESPA': {'prefisso': 'ER', 'nome': 'Espa', 'regione': 'Emilia-Romagna'},
    'TENNERIELLO': {'prefisso': 'ER', 'nome': 'Tenneriello', 'regione': 'Emilia-Romagna'},
    'SCACCHETTI': {'prefisso': 'ER', 'nome': 'Scacchetti', 'regione': 'Emilia-Romagna'},
    'TESSITORE': {'prefisso': 'ER', 'nome': 'Tessitore', 'regione': 'Emilia-Romagna'},
    'USAI': {'prefisso': 'T', 'nome': 'Usai', 'regione': 'Toscana/Marche/Umbria'},
}

TIPOLOGIE = ['EXTRA CANONE', 'DECOR EASY', 'SAFETY', 'PIANIFICATA 2027', 'RINA', 'EMAIL']
TIPI_DOC = ['PREVENTIVO', 'CONSUNTIVO']
STATI = ['INVIATO IN ATTESA ODS', 'REALIZZATO', 'REALIZZATO E FATTURATO', 'RESPINTO', 'SOSPESO']
REGIONI = ['Tutti', 'Emilia-Romagna', 'Toscana/Marche/Umbria']

# --- FUNZIONI ---
def genera_progressivo(prefisso):
    try:
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
    except Exception as e:
        st.error(f"Errore nel generare il progressivo: {e}")
        return f"{prefisso}_001/{datetime.now().strftime('%y')}"

def carica_dati(filtro_tecnico=None, filtro_stato=None, filtro_region=None, data_inizio=None, data_fine=None):
    """Carica i dati con gestione errori robusta."""
    try:
        query = supabase.table('preventivi').select('*')
        
        if filtro_tecnico and filtro_tecnico != 'Tutti':
            query = query.eq('tecnico', TECNICI[filtro_tecnico]['nome'])
        if filtro_stato and filtro_stato != 'Tutti':
            query = query.eq('stato_documento', filtro_stato)
        
        response = query.order('creato_il', desc=True).execute()
        
        if not response.data:
            return pd.DataFrame()
        
        df = pd.DataFrame(response.data)
        
        # Conversione date
        df['creato_il'] = pd.to_datetime(df['creato_il'])
        df['mese'] = df['creato_il'].dt.to_period('M')
        df['regione'] = df['prefisso'].apply(lambda x: 'Emilia-Romagna' if x == 'ER' else 'Toscana/Marche/Umbria')
        
        # Filtri avanzati
        if filtro_region and filtro_region != 'Tutti':
            df = df[df['regione'] == filtro_region]
        if data_inizio:
            df = df[df['creato_il'] >= pd.Timestamp(data_inizio)]
        if data_fine:
            df = df[df['creato_il'] <= pd.Timestamp(data_fine)]
        
        return df
    
    except Exception as e:
        st.warning(f"⚠️ Impossibile caricare i dati: {e}")
        st.info("💡 La tabella potrebbe essere vuota. Inserisci il primo documento nella tab 'Nuovo Documento'.")
        return pd.DataFrame()

# --- INTERFACCIA ---
st.set_page_config(page_title="Gestione Preventivi - Dashboard", layout="wide", page_icon="📊")
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
st.sidebar.divider()
st.sidebar.subheader("🔍 Filtri Globali")
filtro_region_global = st.sidebar.selectbox("Regione:", REGIONI)
data_inizio = st.sidebar.date_input("Data inizio", value=datetime(2026, 1, 1))
data_fine = st.sidebar.date_input("Data fine", value=datetime.now())

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "➕ Nuovo Documento", 
    "📊 Elenco Documenti", 
    "📈 Dashboard & Grafici",
    "🖨️ Stampa & Export"
])

# ============ TAB 1: NUOVO DOCUMENTO ============
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

# ============ TAB 2: ELENCO DOCUMENTI ============
with tab2:
    st.subheader("Elenco documenti")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_tecnico = st.selectbox("Filtra tecnico:", ['Tutti'] + list(TECNICI.keys()), key='tec_elenco')
    with col2:
        filtro_stato = st.selectbox("Filtra stato:", ['Tutti'] + STATI, key='stato_elenco')
    with col3:
        filtro_region = st.selectbox("Filtra regione:", REGIONI, key='reg_elenco')
    
    df = carica_dati(filtro_tecnico, filtro_stato, filtro_region, data_inizio, data_fine)
    
    if not df.empty:
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
