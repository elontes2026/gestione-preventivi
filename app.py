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
st.set_page_config(page_title="Gestione Preventivi", layout="wide", page_icon="📊")
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
            st.metric("📄 Totale Documenti", len(df))
        with kpi2:
            st.metric("💰 Fatturato Totale", f"€ {df['importo'].sum():,.2f}")
        with kpi3:
            st.metric("📊 Importo Medio", f"€ {df['importo'].mean():,.2f}")
        with kpi4:
            st.metric("✅ Realizzati", len(df[df['stato_documento'] == 'REALIZZATO']))

        cols = ['protocollo', 'tecnico', 'tipo_documento', 'comune', 'descrizione', 'importo', 'stato_documento', 'creato_il']
        st.dataframe(df[cols], use_container_width=True)
    else:
        st.info("📭 Nessun documento presente. Vai nella tab '➕ Nuovo Documento' per registrare il primo!")

# ============ TAB 3: DASHBOARD & GRAFICI ============
with tab3:
    st.subheader("📈 Dashboard Analitica")

    col1, col2 = st.columns(2)
    with col1:
        filtro_tec_dash = st.selectbox("Tecnico:", ['Tutti'] + list(TECNICI.keys()), key='tec_dash')
    with col2:
        filtro_reg_dash = st.selectbox("Regione:", REGIONI, key='reg_dash')

    df_dash = carica_dati(
        filtro_tec_dash if filtro_tec_dash != 'Tutti' else None,
        None,
        filtro_reg_dash,
        data_inizio,
        data_fine
    )

    if df_dash.empty:
        st.info("📊 Nessun dato disponibile. Inserisci dei documenti per vedere le statistiche.")
    else:
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.metric("📄 Documenti", len(df_dash))
        with kpi2:
            st.metric("💰 Fatturato", f"€ {df_dash['importo'].sum():,.2f}")
        with kpi3:
            st.metric("📊 Media", f"€ {df_dash['importo'].mean():,.2f}")
        with kpi4:
            realizzati = len(df_dash[df_dash['stato_documento'].isin(['REALIZZATO', 'REALIZZATO E FATTURATO'])])
            st.metric("✅ Completati", realizzati)

        st.divider()

        st.subheader("💰 Fatturato per Tecnico")
        fatt_tecnici = df_dash.groupby('tecnico')['importo'].sum().reset_index().sort_values('importo', ascending=False)
        fig1 = px.bar(fatt_tecnici, x='tecnico', y='importo', title='Fatturato per tecnico', color='tecnico', text='importo')
        fig1.update_traces(texttemplate='€ %{text:,.0f}', textposition='outside')
        st.plotly_chart(fig1, use_container_width=True)

        st.subheader("🗺️ Fatturato per Regione")
        fatt_regioni = df_dash.groupby('regione')['importo'].sum().reset_index()
        fig2 = px.bar(fatt_regioni, x='regione', y='importo', title='Fatturato per regione', color='regione', text='importo')
        fig2.update_traces(texttemplate='€ %{text:,.0f}', textposition='outside')
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("📅 Andamento Temporale (mensile)")
        df_mese = df_dash.groupby('mese')['importo'].sum().reset_index()
        df_mese['mese_str'] = df_mese['mese'].astype(str)
        fig3 = px.line(df_mese, x='mese_str', y='importo', title='Fatturato mensile', markers=True)
        st.plotly_chart(fig3, use_container_width=True)

        st.subheader("🥧 Distribuzione per Tipologia")
        col_pie1, col_pie2 = st.columns(2)
        with col_pie1:
            tip_count = df_dash['tipologia_richiesta'].value_counts().reset_index()
            tip_count.columns = ['tipologia', 'count']
            fig4 = px.pie(tip_count, values='count', names='tipologia', title='Numero documenti per tipologia')
            st.plotly_chart(fig4, use_container_width=True)
        with col_pie2:
            tip_imp = df_dash.groupby('tipologia_richiesta')['importo'].sum().reset_index()
            fig5 = px.pie(tip_imp, values='importo', names='tipologia_richiesta', title='Fatturato per tipologia')
            st.plotly_chart(fig5, use_container_width=True)

        st.subheader("📊 Stato dei Documenti")
        stato_count = df_dash['stato_documento'].value_counts().reset_index()
        stato_count.columns = ['stato', 'count']
        fig6 = px.bar(stato_count, y='stato', x='count', orientation='h', title='Distribuzione per stato', color='stato')
        st.plotly_chart(fig6, use_container_width=True)

# ============ TAB 4: STAMPA & EXPORT ============
with tab4:
    st.subheader("🖨️ Stampa e Export")

    df_all = carica_dati()

    if df_all.empty:
        st.info("📭 Nessun documento presente nel database.")
    else:
        st.info(f"📊 **{len(df_all)} documenti** disponibili. Fatturato totale: **€ {df_all['importo'].sum():,.2f}**")

        st.markdown("### 📊 Export Excel (.xlsx)")
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_all.to_excel(writer, sheet_name='Preventivi', index=False)
        output.seek(0)

        st.download_button(
            label="⬇️ Scarica Excel completo",
            data=output.getvalue(),
            file_name=f"preventivi_completi_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        st.divider()

        st.markdown("### 📄 Export PDF (Tabella completa)")
        pdf = FPDF()
        pdf.add_page('L')
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Commessa 790 - Elenco Preventivi", ln=True, align='C')
        pdf.cell(0, 6, f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
        pdf.ln(5)

        colonne = ['Protocollo', 'Tecnico', 'Tipo', 'Comune', 'Importo', 'Stato']
        larghezze = [35, 30, 25, 50, 30, 50]

        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(70, 130, 180)
        pdf.set_text_color(255, 255, 255)
        for col, larg in zip(colonne, larghezze):
            pdf.cell(larg, 8, col, border=1, fill=True, align='C')
        pdf.ln()

        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(0, 0, 0)
        for idx, row in df_all.iterrows():
            if idx % 2 == 0:
                pdf.set_fill_color(240, 240, 240)
            else:
                pdf.set_fill_color(255, 255, 255)

            importo = f"€ {row.get('importo', 0):,.2f}" if row.get('importo') else "€ 0,00"
            valori = [
                str(row.get('protocollo', '')),
                str(row.get('tecnico', '')),
                str(row.get('tipo_documento', '')),
                str(row.get('comune', ''))[:25],
                importo,
                str(row.get('stato_documento', ''))[:25]
            ]

            for val, larg in zip(valori, larghezze):
                pdf.cell(larg, 6, val, border=1, fill=True, align='L')
            pdf.ln()

        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 8, f"Totale documenti: {len(df_all)}", ln=True)
        pdf.cell(0, 8, f"Fatturato totale: € {df_all['importo'].sum():,.2f}", ln=True)

        pdf_bytes = pdf.output()
        st.download_button(
            label="⬇️ Scarica PDF tabella",
            data=pdf_bytes,
            file_name=f"preventivi_tabella_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

        st.divider()

        st.markdown("### 📋 PDF Singolo Documento")
        doc_sel = st.selectbox("Seleziona documento:", df_all['protocollo'].tolist(), key='doc_pdf_singolo')

        if doc_sel:
            doc = df_all[df_all['protocollo'] == doc_sel].iloc[0].to_dict()

            col_prev1, col_prev2 = st.columns(2)
            with col_prev1:
                st.markdown(f"**Protocollo:** {doc.get('protocollo')}")
                st.markdown(f"**Tecnico:** {doc.get('tecnico')}")
                st.markdown(f"**Comune:** {doc.get('comune')}")
            with col_prev2:
                st.markdown(f"**Importo:** € {doc.get('importo', 0):,.2f}")
                st.markdown(f"**Stato:** {doc.get('stato_documento')}")
                st.markdown(f"**Tipo:** {doc.get('tipo_documento')}")

            if st.button("🖨️ Genera PDF documento", use_container_width=True):
                pdf_doc = FPDF()
                pdf_doc.add_page()
                pdf_doc.set_font("Helvetica", "B", 16)
                pdf_doc.cell(0, 10, "Commessa 790 - Unicredit FM", ln=True, align='C')
                pdf_doc.ln(5)

                pdf_doc.set_font("Helvetica", "B", 14)
                pdf_doc.cell(0, 10, f"Protocollo: {doc.get('protocollo', 'N/D')}", ln=True)
                pdf_doc.ln(5)

                pdf_doc.set_font("Helvetica", "", 11)
                campi = [
                    ('Tecnico', doc.get('tecnico', '')),
                    ('Tipo Documento', doc.get('tipo_documento', '')),
                    ('Tipologia Richiesta', doc.get('tipologia_richiesta', '')),
                    ('Comune', doc.get('comune', '')),
                    ('Indirizzo', doc.get('indirizzo', '')),
                    ('Importo', f"€ {doc.get('importo', 0):,.2f}" if doc.get('importo') else 'N/D'),
                    ('Stato', doc.get('stato_documento', '')),
                    ('N° ODA', doc.get('numero_oda', '')),
                    ('Data ODA', doc.get('data_oda', '')),
                    ('REM Riferimento', doc.get('rem_riferimento', '')),
                ]

                for label, valore in campi:
                    pdf_doc.set_font("Helvetica", "B", 11)
                    pdf_doc.cell(50, 8, f"{label}:", ln=False)
                    pdf_doc.set_font("Helvetica", "", 11)
                    pdf_doc.cell(0, 8, str(valore), ln=True)

                pdf_doc.ln(5)
                pdf_doc.set_font("Helvetica", "B", 11)
                pdf_doc.cell(0, 8, "Descrizione Intervento:", ln=True)
                pdf_doc.set_font("Helvetica", "", 10)
                pdf_doc.multi_cell(0, 6, doc.get('descrizione', ''))

                if doc.get('note'):
                    pdf_doc.ln(3)
                    pdf_doc.set_font("Helvetica", "B", 11)
                    pdf_doc.cell(0, 8, "Note:", ln=True)
                    pdf_doc.set_font("Helvetica", "", 10)
                    pdf_doc.multi_cell(0, 6, doc['note'])

                pdf_bytes_doc = pdf_doc.output()
                st.download_button(
                    label="⬇️ Scarica PDF documento",
                    data=pdf_bytes_doc,
                    file_name=f"{doc_sel}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
