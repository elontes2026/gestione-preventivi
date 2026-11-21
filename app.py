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
        return f"{prefisso}_{str(1).zfill(3)}/{datetime.now().strftime('%y')}"

def carica_dati(filtro_tecnico=None, filtro_stato=None, filtro_region=None, data_inizio=None, data_fine=None):
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
        df['creato_il'] = pd.to_datetime(df['creato_il'])
        df['mese'] = df['creato_il'].dt.to_period('M')
        df['regione'] = df['prefisso'].apply(lambda x: 'Emilia-Romagna' if x == 'ER' else 'Toscana/Marche/Umbria')
        if filtro_region and filtro_region != 'Tutti':
            df = df[df['regione'] == filtro_region]
        if data_inizio:
            df = df[df['creato_il'] >= pd.Timestamp(data_inizio)]
        if data_fine:
            df = df[df['creato_il'] <= pd.Timestamp(data_fine)]
        return df
    except Exception as e:
        st.warning(f"⚠️ Impossibile caricare i dati: {e}")
        return pd.DataFrame()

# --- INTERFACCIA ---
st.set_page_config(page_title="Gestione Preventivi", layout="
