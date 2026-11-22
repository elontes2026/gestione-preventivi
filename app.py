import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ============ CONFIG ============
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.set_page_config(page_title="Gestione Preventivi", layout="wide")

# ============ MENU A TENDINA ============
OPZIONI = {
    "tecnico": [
        "", "BONAZZA", "DI GENOVA", "ESPA", "MASALA", "SCACCHETTI",
        "TAMBURINI", "TENNERIELLO", "TESSITORE", "USAI"
    ],
    "tipologia_richiesta": [
        "", "DECOR EASY", "EXTRA CANONE", "RINA", "SAFETY",
        "PIANIFICATA 2027", "EMAIL"
    ],
    "tipo_documento": [
        "", "CONSUNTIVO", "PREVENTIVO"
    ],
    "rem_riferimento": [
        "", "CACCIARI", "CENCINI", "DE CECCO", "FIOCCHI", "FLORIO",
        "FRANGELLA", "MAGNANI", "MATERAZZI", "PAGANI", "PAOLOCCI",
        "PARENTI", "PARISOLI", "PASSANNANTE", "RETTAROLI",
        "Luca Passannante", "Corrado Parisoli", "LUCA CAMARDA",
        "Silvia Giorgini", "Rettaroli Massimo", "Materazzi Federico"
    ],
    "stato_documento": [
        "", "REALIZZATO", "INVIATO IN ATTESA ODS",
        "REALIZZATO E FATTURATO", "RESPINTO", "SOSPESO"
    ],
    "numero_fattura": [
        "", "Fatturato"
    ]
}

# ============ CARICA DATI ============
@st.cache_data(ttl=30)
def load_data():
    response = supabase.table("preventivi").select("*").order("id").execute()
    return pd.DataFrame(response.data)

df = load_data()

# ============ FILTRI ============
st.title("📋 Gestione Preventivi - UniCredit FM")

col1, col2, col3 = st.columns(3)
with col1:
    filtro_tecnico = st.multiselect("👷 Tecnico", sorted(df["tecnico"].dropna().unique()))
with col2:
    filtro_stato = st.multiselect("📌 Stato documento", sorted(df["stato_documento"].dropna().unique()))
with col3:
    filtro_tipo = st.multiselect("📄 Tipo documento", sorted(df["tipo_documento"].dropna().unique()))

# Applica filtri
df_view = df.copy()
if filtro_tecnico:
    df_view = df_view[df_view["tecnico"].isin(filtro_tecnico)]
if filtro_stato:
    df_view = df_view[df_view["stato_documento"].isin(filtro_stato)]
if filtro_tipo:
    df_view = df_view[df_view["tipo_documento"].isin(filtro_tipo)]

st.info(f"🔎 {len(df_view)} righe su {len(df)} totali")

# ============ EDITOR CON MENU A TENDINA ============
edited_df = st.data_editor(
    df_view,
    num_rows="fixed",
    hide_index=True,
    use_container_width=True,
    column_config={
        "id": st.column_config.TextColumn("ID", disabled=True),
        "tecnico": st.column_config.SelectboxColumn(
            "Tecnico", options=OPZIONI["tecnico"], required=False
        ),
        "tipologia_richiesta": st.column_config.SelectboxColumn(
            "Tipologia richiesta", options=OPZIONI["tipologia_richiesta"], required=False
        ),
        "protocollo": st.column_config.TextColumn("Protocollo"),
        "numero_oda": st.column_config.TextColumn("N° ODA"),
        "data_oda": st.column_config.TextColumn("Data ODA"),
        "tipo_documento": st.column_config.SelectboxColumn(
            "Tipo documento", options=OPZIONI["tipo_documento"], required=False
        ),
        "comune": st.column_config.TextColumn("Comune"),
        "indirizzo": st.column_config.TextColumn("Indirizzo"),
        "descrizione": st.column_config.TextColumn("Descrizione", width="large"),
        "importo": st.column_config.TextColumn("Importo"),
        "rem_riferimento": st.column_config.SelectboxColumn(
            "REM riferimento", options=OPZIONI["rem_riferimento"], required=False
        ),
        "inizio_lavori": st.column_config.TextColumn("Inizio lavori"),
        "fine_lavori": st.column_config.TextColumn("Fine lavori"),
        "stato_documento": st.column_config.SelectboxColumn(
            "Stato documento", options=OPZIONI["stato_documento"], required=False
        ),
        "numero_fattura": st.column_config.SelectboxColumn(
            "Numero fattura", options=OPZIONI["numero_fattura"], required=False
        ),
        "stato_finale": st.column_config.TextColumn("Stato finale"),
        "importo_fatturato": st.column_config.TextColumn("Importo fatturato"),
        "saldo": st.column_config.TextColumn("Saldo"),
    },
    key="editor_preventivi"
)

# ============ SALVATAGGIO ============
if st.button("💾 Salva tutte le modifiche", type="primary"):
    # Trova le righe modificate
    changed = edited_df.merge(df, on="id", suffixes=("_new", "_old"))
    updates = []
    for _, row in changed.iterrows():
        # Controlla se qualche campo è cambiato
        modified_fields = {}
        for col in df.columns:
            if col == "id":
                continue
            new_val = row[f"{col}_new"]
            old_val = row[f"{col}_old"]
            # Normalizza NaN
            if pd.isna(new_val):
                new_val = ""
            if pd.isna(old_val):
                old_val = ""
            if str(new_val) != str(old_val):
                modified_fields[col] = new_val if new_val != "" else None
        if modified_fields:
            updates.append({"id": row["id"], **modified_fields})

    if updates:
        for upd in updates:
            rid = upd.pop("id")
            supabase.table("preventivi").update(upd).eq("id", rid).execute()
        st.success(f"✅ Aggiornate {len(updates)} righe!")
        st.cache_data.clear()
        st.rerun()
    else:
        st.warning("⚠️ Nessuna modifica da salvare.")
