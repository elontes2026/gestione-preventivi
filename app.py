import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import os
import hashlib
from datetime import datetime
from supabase import create_client
from io import BytesIO

# 🔐 Credenziali Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ Credenziali mancanti.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- FUNZIONI DI AUTENTICAZIONE ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verifica_login(username, password):
    try:
        response = supabase.table('utenti').select('*').eq('username', username).eq('attivo', True).execute()
        if not response.data:
            return None, "Utente non trovato o disattivato"
        utente = response.data[0]
        if utente['password_hash'] != hash_password(password):
            return None, "Password errata"
        supabase.table('utenti').update({'ultimo_accesso': datetime.now().isoformat()}).eq('id', utente['id']).execute()
        return utente, None
    except Exception as e:
        return None, f"Errore: {e}"

def cambia_password_admin(username_admin, username_target, nuova_password):
    try:
        response = supabase.table('utenti').select('ruolo').eq('username', username_admin).execute()
        if not response.data or response.data[0]['ruolo'] != 'admin':
            return False, "Non hai i privilegi di amministratore"
        nuovo_hash = hash_password(nuova_password)
        supabase.table('utenti').update({'password_hash': nuovo_hash}).eq('username', username_target).execute()
        return True, f"Password aggiornata per {username_target}"
    except Exception as e:
        return False, f"Errore: {e}"

def crea_utente_admin(username_creatore, username, password, nome_completo, prefisso, ruolo='tecnico'):
    try:
        response = supabase.table('utenti').select('ruolo').eq('username', username_creatore).execute()
        if not response.data or response.data[0]['ruolo'] != 'admin':
            return False, "Solo gli admin possono creare utenti"
        supabase.table('utenti').insert({
            'username': username,
            'password_hash': hash_password(password),
            'nome_completo': nome_completo,
            'prefisso': prefisso,
            'ruolo': ruolo,
            'attivo': True
        }).execute()
        return True, f"Utente {username} creato"
    except Exception as e:
        return False, f"Errore: {e}"

def disattiva_utente_admin(username_admin, username_target):
    try:
        response = supabase.table('utenti').select('ruolo').eq('username', username_admin).execute()
        if not response.data or response.data[0]['ruolo'] != 'admin':
            return False, "Solo gli admin possono disattivare utenti"
        supabase.table('utenti').update({'attivo': False}).eq('username', username_target).execute()
        return True, f"Utente {username_target} disattivato"
    except Exception as e:
        return False, f"Errore: {e}"

# --- FUNZIONI DATI ---
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
    except:
        return f"{prefisso}_001/{datetime.now().strftime('%y')}"

def carica_dati(filtro_tecnico=None, filtro_stato=None, filtro_region=None, data_inizio=None, data_fine=None):
    try:
        query = supabase.table('preventivi').select('*')
        if filtro_tecnico and filtro_tecnico != 'Tutti':
            query = query.eq('tecnico', filtro_tecnico)
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
    except:
        return pd.DataFrame()

def carica_utenti():
    try:
        response = supabase.table('utenti').select('*').eq('attivo', True).execute()
        return response.data if response.data else []
    except:
        return []

# --- CONFIGURAZIONE ---
TIPOLOGIE = ['EXTRA CANONE', 'DECOR EASY', 'SAFETY', 'PIANIFICATA 2027', 'RINA', 'EMAIL']
TIPI_DOC = ['PREVENTIVO', 'CONSUNTIVO']
STATI = ['INVIATO IN ATTESA ODS', 'REALIZZATO', 'REALIZZATO E FATTURATO', 'RESPINTO', 'SOSPESO']
REGIONI = ['Tutti', 'Emilia-Romagna', 'Toscana/Marche/Umbria']

COLORI_PERSONE = {
    'Bonazza': '#FF6B6B',
    'Espa': '#4ECDC4',
    'Tenneriello': '#45B7D1',
    'Scacchetti': '#96CEB4',
    'Tessitore': '#FFEAA7',
    'Usai': '#DDA0DD',
}

COLORI_REGIONI = {
    'Emilia-Romagna': '#FF6B6B',
    'Toscana/Marche/Umbria': '#4ECDC4',
}

COLORI_STATI = {
    'INVIATO IN ATTESA ODS': '#FFA500',
    'REALIZZATO': '#4CAF50',
    'REALIZZATO E FATTURATO': '#2196F3',
    'RESPINTO': '#F44336',
    'SOSPESO': '#9E9E9E',
}

COLORI_TIPOLOGIE = {
    'EXTRA CANONE': '#FF6B6B',
    'DECOR EASY': '#4ECDC4',
    'SAFETY': '#45B7D1',
    'PIANIFICATA 2027': '#96CEB4',
    'RINA': '#FFEAA7',
    'EMAIL': '#DDA0DD',
}

# --- INTERFACCIA ---
st.set_page_config(page_title="Gestione Preventivi", layout="wide", page_icon="📊")

# ============ LOGIN ============
if 'utente_loggato' not in st.session_state:
    st.session_state.utente_loggato = None

if st.session_state.utente_loggato is None:
    st.title("🔐 Login - Commessa 790 Unicredit FM")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.subheader("Accedi al sistema")
            username = st.text_input("👤 Username", placeholder="es. ptessore")
            password = st.text_input("🔑 Password", type="password", placeholder="Inserisci la password")
            
            submitted = st.form_submit_button("🔓 Accedi", use_container_width=True, type="primary")
            
            if submitted:
                if not username or not password:
                    st.error("⚠️ Inserisci username e password")
                else:
                    utente, errore = verifica_login(username.lower(), password)
                    if utente:
                        st.session_state.utente_loggato = utente
                        st.success(f"✅ Benvenuto {utente['nome_completo']}!")
                        st.rerun()
                    else:
                        st.error(f"❌ {errore}")
    
    st.markdown("---")
    st.info("💡 **Password iniziali:**\n- Admin (ptessore): `Admin2026!`\n- Tecnici: `Tecnico2026!`\n\n⚠️ Cambia la password dopo il primo accesso!")
    st.stop()

# ============ APP PRINCIPALE (dopo login) ============
utente = st.session_state.utente_loggato
is_admin = utente['ruolo'] == 'admin'

# Sidebar
st.sidebar.title(f"👤 {utente['nome_completo']}")
st.sidebar.info(f"**Ruolo:** {'👑 Amministratore' if is_admin else '🔧 Tecnico'}\n**Prefisso:** `{utente['prefisso']}`")

st.sidebar.divider()

if is_admin:
    st.sidebar.subheader("👑 Pannello Admin")
    menu_admin = st.sidebar.radio(
        "Gestione:",
        ["📊 Dashboard", "➕ Nuovo Documento", "📋 Elenco", "📈 Grafici", "🖨️ Export", "⚙️ Gestione Utenti"],
        key='menu_admin'
    )
else:
    st.sidebar.subheader("🔧 Menu Tecnico")
    menu_admin = st.sidebar.radio(
        "Sezioni:",
        ["📊 Dashboard", "➕ Nuovo Documento", "📋 Elenco", "📈 Grafici", "🖨️ Export"],
        key='menu_tecnico'
    )

st.sidebar.divider()
if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.utente_loggato = None
    st.rerun()

# ============ GESTIONE UTENTI (solo admin) ============
if menu_admin == "⚙️ Gestione Utenti" and is_admin:
    st.title("⚙️ Gestione Utenti")
    st.markdown("Gestisci account tecnici, reset password e crea nuovi utenti.")
    
    tab_utenti1, tab_utenti2, tab_utenti3 = st.tabs(["👥 Lista Utenti", "🔑 Reset Password", "➕ Nuovo Utente"])
    
    with tab_utenti1:
        st.subheader("Elenco utenti registrati")
        utenti_lista = carica_utenti()
        
        if utenti_lista:
            df_utenti = pd.DataFrame(utenti_lista)
            df_utenti['ultimo_accesso'] = pd.to_datetime(df_utenti['ultimo_accesso'], errors='coerce')
            df_utenti['ultimo_accesso'] = df_utenti['ultimo_accesso'].dt.strftime('%d/%m/%Y %H:%M')
            
            cols_mostra = ['username', 'nome_completo', 'prefisso', 'ruolo', 'ultimo_accesso']
            st.dataframe(df_utenti[cols_mostra], use_container_width=True)
            
            st.markdown("---")
            st.subheader("🚫 Disattiva utente")
            utenti_attivi = [u['username'] for u in utenti_lista if u['username'] != utente['username']]
            if utenti_attivi:
                utente_da_disattivare = st.selectbox("Seleziona utente da disattivare:", utenti_attivi)
                if st.button("🚫 Disattiva", type="secondary"):
                    ok, msg = disattiva_utente_admin(utente['username'], utente_da_disattivare)
                    if ok:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")
        else:
            st.info("Nessun utente registrato.")
    
    with tab_utenti2:
        st.subheader("🔑 Reset Password Tecnico")
        st.warning("⚠️ Usa questa funzione per resettare la password di un tecnico che l'ha dimenticata.")
        
        utenti_lista = carica_utenti()
        tecnici = [u['username'] for u in utenti_lista if u['ruolo'] == 'tecnico']
        
        if tecnici:
            tecnico_sel = st.selectbox("Seleziona tecnico:", tecnici)
            nuova_pwd = st.text_input("Nuova password:", type="password")
            conferma_pwd = st.text_input("Conferma nuova password:", type="password")
            
            if st.button("🔑 Resetta Password", type="primary"):
                if not nuova_pwd or len(nuova_pwd) < 6:
                    st.error("⚠️ La password deve essere di almeno 6 caratteri")
                elif nuova_pwd != conferma_pwd:
                    st.error("⚠️ Le password non coincidono")
                else:
                    ok, msg = cambia_password_admin(utente['username'], tecnico_sel, nuova_pwd)
                    if ok:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")
        else:
            st.info("Nessun tecnico registrato.")
        
        st.divider()
        st.subheader("🔐 Cambia la tua password")
        vecchia_pwd = st.text_input("Password attuale:", type="password", key='vecchia_admin')
        nuova_pwd_admin = st.text_input("Nuova password:", type="password", key='nuova_admin')
        conferma_pwd_admin = st.text_input("Conferma:", type="password", key='conf_admin')
        
        if st.button("💾 Aggiorna mia password"):
            if hash_password(vecchia_pwd) != utente['password_hash']:
                st.error("⚠️ Password attuale errata")
            elif len(nuova_pwd_admin) < 6:
                st.error("⚠️ Minimo 6 caratteri")
            elif nuova_pwd_admin != conferma_pwd_admin:
                st.error("⚠️ Le password non coincidono")
            else:
                ok, msg = cambia_password_admin(utente['username'], utente['username'], nuova_pwd_admin)
                if ok:
                    st.success("✅ Password aggiornata! Effettua nuovamente il login.")
                    st.session_state.utente_loggato = None
                    st.rerun()
    
    with tab_utenti3:
        st.subheader("➕ Crea nuovo utente")
        
        col1, col2 = st.columns(2)
        with col1:
            nuovo_username = st.text_input("Username (senza spazi, minuscolo):")
            nuovo_nome = st.text_input("Nome completo:")
            nuovo_prefisso = st.selectbox("Prefisso:", ['ER', 'T', 'MU'])
        with col2:
            nuovo_ruolo = st.selectbox("Ruolo:", ['tecnico', 'admin'])
            nuova_password = st.text_input("Password iniziale:", type="password")
            conferma = st.text_input("Conferma password:", type="password")
        
        if st.button("➕ Crea utente", type="primary"):
            if not nuovo_username or not nuovo_nome or not nuova_password:
                st.error("⚠️ Compila tutti i campi")
            elif nuova_password != conferma:
                st.error("⚠️ Le password non coincidono")
            elif len(nuova_password) < 6:
                st.error("⚠️ Minimo 6 caratteri")
            else:
                ok, msg = crea_utente_admin(
                    utente['username'],
                    nuovo_username.lower(),
                    nuova_password,
                    nuovo_nome,
                    nuovo_prefisso,
                    nuovo_ruolo
                )
                if ok:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

# ============ DASHBOARD ============
elif menu_admin == "📊 Dashboard":
    st.title("📊 Dashboard Commessa 790")
    
    df_all = carica_dati()
    
    if df_all.empty:
        st.info("📭 Nessun documento presente.")
    else:
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.metric("📄 Documenti Totali", len(df_all))
        with kpi2:
            st.metric("💰 Fatturato Totale", f"€ {df_all['importo'].sum():,.2f}")
        with kpi3:
            st.metric("📊 Importo Medio", f"€ {df_all['importo'].mean():,.2f}")
        with kpi4:
            realizzati = len(df_all[df_all['stato_documento'].isin(['REALIZZATO', 'REALIZZATO E FATTURATO'])])
            st.metric("✅ Completati", realizzati)
        
        st.divider()
        
        st.subheader("💰 Fatturato per Tecnico")
        fatt_tecnici = df_all.groupby('tecnico')['importo'].sum().reset_index().sort_values('importo', ascending=False)
        fatt_tecnici['colore'] = fatt_tecnici['tecnico'].map(COLORI_PERSONE)
        
        fig1 = go.Figure()
        for idx, row in fatt_tecnici.iterrows():
            fig1.add_trace(go.Bar(
                x=[row['tecnico']],
                y=[row['importo']],
                name=row['tecnico'],
                marker_color=row['colore'],
                text=f"€ {row['importo']:,.0f}",
                textposition='outside'
            ))
        fig1.update_layout(
            title='Fatturato totale per tecnico',
            xaxis_title='Tecnico',
            yaxis_title='Importo (€)',
            showlegend=False,
            template='plotly_white'
        )
        st.plotly_chart(fig1, use_container_width=True)
        
        st.subheader("🗺️ Fatturato per Regione")
        fatt_regioni = df_all.groupby('regione')['importo'].sum().reset_index()
        fatt_regioni['colore'] = fatt_regioni['regione'].map(COLORI_REGIONI)
        
        fig2 = go.Figure()
        for idx, row in fatt_regioni.iterrows():
            fig2.add_trace(go.Bar(
                x=[row['regione']],
                y=[row['importo']],
                name=row['regione'],
                marker_color=row['colore'],
                text=f"€ {row['importo']:,.0f}",
                textposition='outside'
            ))
        fig2.update_layout(
            title='Fatturato per regione',
            xaxis_title='Regione',
            yaxis_title='Importo (€)',
            showlegend=False,
            template='plotly_white'
        )
        st.plotly_chart(fig2, use_container_width=True)
        
        st.subheader("🥧 Distribuzione Documenti per Tecnico")
        count_tecnici = df_all['tecnico'].value_counts().reset_index()
        count_tecnici.columns = ['tecnico', 'count']
        count_tecnici['colore'] = count_tecnici['tecnico'].map(COLORI_PERSONE)
        
        fig3 = go.Figure(data=[go.Pie(
            labels=count_tecnici['tecnico'],
            values=count_tecnici['count'],
            marker_colors=count_tecnici['colore'],
            textinfo='label+percent+value',
            hole=0.4
        )])
        fig3.update_layout(title='Numero documenti per tecnico', template='plotly_white')
        st.plotly_chart(fig3, use_container_width=True)
        
        st.subheader("🥧 Distribuzione per Regione")
        count_regioni = df_all['regione'].value_counts().reset_index()
        count_regioni.columns = ['regione', 'count']
        count_regioni['colore'] = count_regioni['regione'].map(COLORI_REGIONI)
        
        fig4 = go.Figure(data=[go.Pie(
            labels=count_regioni['regione'],
            values=count_regioni['count'],
            marker_colors=count_regioni['colore'],
            textinfo='label+percent+value',
            hole=0.4
        )])
        fig4.update_layout(title='Numero documenti per regione', template='plotly_white')
        st.plotly_chart(fig4, use_container_width=True)
        
        st.subheader("📊 Fatturato per Stato Documento")
        fatt_stati = df_all.groupby('stato_documento')['importo'].sum().reset_index()
        fatt_stati['colore'] = fatt_stati['stato_documento'].map(COLORI_STATI)
        
        fig5 = go.Figure()
        for idx, row in fatt_stati.iterrows():
            fig5.add_trace(go.Bar(
                x=[row['stato_documento']],
                y=[row['importo']],
                name=row['stato_documento'],
                marker_color=row['colore'],
                text=f"€ {row['importo']:,.0f}",
                textposition='outside'
            ))
        fig5.update_layout(
            title='Fatturato per stato',
            xaxis_title='Stato',
            yaxis_title='Importo (€)',
            showlegend=False,
            template='plotly_white'
        )
        st.plotly_chart(fig5, use_container_width=True)
        
        st.subheader("🏷️ Fatturato per Tipologia Richiesta")
        fatt_tip = df_all.groupby('tipologia_richiesta')['importo'].sum().reset_index()
        fatt_tip['colore'] = fatt_tip['tipologia_richiesta'].map(COLORI_TIPOLOGIE)
        
        fig6 = go.Figure()
        for idx, row in fatt_tip.iterrows():
            fig6.add_trace(go.Bar(
                x=[row['tipologia_richiesta']],
                y=[row['importo']],
                name=row['tipologia_richiesta'],
                marker_color=row['colore'],
                text=f"€ {row['importo']:,.0f}",
                textposition='outside'
            ))
        fig6.update_layout(
            title='Fatturato per tipologia',
            xaxis_title='Tipologia',
            yaxis_title='Importo (€)',
            showlegend=False,
            template='plotly_white'
        )
        st.plotly_chart(fig6, use_container_width=True)

# ============ NUOVO DOCUMENTO ============
elif menu_admin == "➕ Nuovo Documento":
    st.title("➕ Registra Nuovo Documento")
    st.info(f"Sei loggato come **{utente['nome_completo']}** - Prefisso: `{utente['prefisso']}`")
    
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
        
        if st.form_submit_button("💾 Registra Documento", use_container_width=True, type="primary"):
            if not comune or not indirizzo or not descrizione:
                st.error("⚠️ Compila i campi obbligatori (*)")
            else:
                protocollo = genera_progressivo(utente['prefisso'])
                dati = {
                    'protocollo': protocollo,
                    'tecnico': utente['nome_completo'],
                    'prefisso': utente['prefisso'],
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
                    'creato_da': utente['username']
                }
                try:
                    supabase.table('preventivi').insert(dati).execute()
                    supabase.table('audit_log').insert({
                        'protocollo': protocollo,
                        'azione': 'CREAZIONE',
                        'utente': utente['username'],
                        'dettaglio': f"Documento creato da {utente['nome_completo']}"
                    }).execute()
                    st.success(f"✅ Documento registrato!\n\n**Protocollo: {protocollo}**")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Errore: {e}")

# ============ ELENCO ============
elif menu_admin == "📋 Elenco":
    st.title("📋 Elenco Documenti")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_tecnico = st.selectbox("Filtra tecnico:", ['Tutti'], key='tec_elenco')
    with col2:
        filtro_stato = st.selectbox("Filtra stato:", ['Tutti'] + STATI, key='stato_elenco')
    with col3:
        filtro_region = st.selectbox("Filtra regione:", REGIONI, key='reg_elenco')
    
    df = carica_dati(filtro_tecnico, filtro_stato, filtro_region)
    
    if not df.empty:
        kpi1, kpi2, kpi3 = st.columns(3)
        with kpi1:
            st.metric("📄 Documenti", len(df))
        with kpi2:
            st.metric("💰 Fatturato", f"€ {df['importo'].sum():,.2f}")
        with kpi3:
            st.metric("📊 Media", f"€ {df['importo'].mean():,.2f}")
        
        cols = ['protocollo', 'tecnico', 'tipo_documento', 'comune', 'descrizione', 'importo', 'stato_documento', 'creato_il']
        st.dataframe(df[cols], use_container_width=True)
    else:
        st.info("📭 Nessun documento presente.")

# ============ GRAFICI ============
elif menu_admin == "📈 Grafici":
    st.title("📈 Grafici Analitici")
    
    df_dash = carica_dati()
    
    if df_dash.empty:
        st.info("📊 Nessun dato disponibile.")
    else:
        st.subheader("💰 Fatturato per Tecnico (Barre Colorate)")
        fatt_tecnici = df_dash.groupby('tecnico')['importo'].sum().reset_index().sort_values('importo', ascending=False)
        fatt_tecnici['colore'] = fatt_tecnici['tecnico'].map(COLORI_PERSONE)
        
        fig = go.Figure()
        for idx, row in fatt_tecnici.iterrows():
            fig.add_trace(go.Bar(
                x=[row['tecnico']],
                y=[row['importo']],
                marker_color=row['colore'],
                text=f"€ {row['importo']:,.0f}",
                textposition='outside'
            ))
        fig.update_layout(title='Fatturato per tecnico', xaxis_title='Tecnico', yaxis_title='Importo (€)', showlegend=False, template='plotly_white')
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("🗺️ Fatturato per Regione (Barre Colorate)")
        fatt_regioni = df_dash.groupby('regione')['importo'].sum().reset_index()
        fatt_regioni['colore'] = fatt_regioni['regione'].map(COLORI_REGIONI)
        
        fig = go.Figure()
        for idx, row in fatt_regioni.iterrows():
            fig.add_trace(go.Bar(
                x=[row['regione']],
                y=[row['importo']],
                marker_color=row['colore'],
                text=f"€ {row['importo']:,.0f}",
                textposition='outside'
            ))
        fig.update_layout(title='Fatturato per regione', xaxis_title='Regione', yaxis_title='Importo (€)', showlegend=False, template='plotly_white')
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("🥧 Distribuzione per Tecnico (Torta Colorata)")
        count_tecnici = df_dash['tecnico'].value_counts().reset_index()
        count_tecnici.columns = ['tecnico', 'count']
        count_tecnici['colore'] = count_tecnici['tecnico'].map(COLORI_PERSONE)
        
        fig = go.Figure(data=[go.Pie(
            labels=count_tecnici['tecnico'],
            values=count_tecnici['count'],
            marker_colors=count_tecnici['colore'],
            textinfo='label+percent+value',
            hole=0.4
        )])
        fig.update_layout(title='Documenti per tecnico', template='plotly_white')
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("🥧 Distribuzione per Regione (Torta Colorata)")
        count_regioni = df_dash['regione'].value_counts().reset_index()
        count_regioni.columns = ['regione', 'count']
        count_regioni['colore'] = count_regioni['regione'].map(COLORI_REGIONI)
        
        fig = go.Figure(data=[go.Pie(
            labels=count_regioni['regione'],
            values=count_regioni['count'],
            marker_colors=count_regioni['colore'],
            textinfo='label+percent+value',
            hole=0.4
        )])
        fig.update_layout(title='Documenti per regione', template='plotly_white')
        st.plotly_chart(fig, use_container_width=True)

# ============ EXPORT ============
elif menu_admin == "🖨️ Export":
    st.title("🖨️ Export e Stampa")
    
    df_all = carica_dati()
    
    if df_all.empty:
        st.info("📭 Nessun documento presente.")
    else:
        st.info(f"📊 **{len(df_all)} documenti** - Fatturato: **€ {df_all['importo'].sum():,.2f}**")
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_all.to_excel(writer, sheet_name='Preventivi', index=False)
        output.seek(0)
        
        st.download_button(
            label="⬇️ Scarica Excel",
            data=output.getvalue(),
            file_name=f"preventivi_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
