import streamlit as st
from supabase import create_client, Client

# Connessione a Supabase (usa le tue chiavi)
url = st.secrets["connections"]["supabase"]["url"]
key = st.secrets["connections"]["supabase"]["key"]
supabase: Client = create_client(url, key)

st.title("📝 Revisione e Modifica Preventivi")

# 1. Carichiamo i dati da Supabase
response = supabase.table("preventivi").select("*").execute()
df = response.data

# 2. Mostriamo i dati in una griglia modificabile
# columns_config permette di bloccare le colonne che NON devono essere modificate (es. l'ID)
edited_df = st.data_editor(
    df, 
    num_rows="dynamic", # Permette anche di aggiungere nuove righe se serve
    column_config={
        "id": st.column_config.TextColumn("ID (Non modificabile)", disabled=True),
        "importo": st.column_config.NumberColumn("Importo (€)", format="%.2f"),
    }
)

# 3. Pulsante per salvare le modifiche
if st.button("💾 Salva le modifiche nel Database"):
    # Per ogni riga modificata, inviamo l'aggiornamento a Supabase
    # (Streamlit gestisce automaticamente il rilevamento delle modifiche)
    for index, row in edited_df.iterrows():
        supabase.table("preventivi").update(row).eq("id", row["id"]).execute()
    
    st.success("✅ Dati aggiornati con successo nel database!")
    st.rerun() # Ricarica la pagina per mostrare i dati aggiornati
