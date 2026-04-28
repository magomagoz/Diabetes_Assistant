import streamlit as st
import google.generativeai as genai
from PIL import Image
import os

# Configurazione della pagina Streamlit
st.set_page_config(page_title="Diabete-IA Helper", layout="wide")
st.title("🥗 Diabetes Assistant")
st.write("Carica la foto del tuo piatto per una stima dei carboidrati (CHO).")

# Recupero API Key (da impostare nei Secrets di Streamlit/GitHub)
api_key = st.secrets.get("API_KEY", "")

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    # Sostituiamo st.file_uploader con st.camera_input
    foto_piatto = st.camera_input("Inquadra il tuo piatto e scatta!")
    
    if foto_piatto is not None:
        # Convertiamo l'immagine per PIL (necessario per Gemini)
        image = Image.open(foto_piatto)
        
        # Mostriamo un'anteprima (opzionale, st.camera_input la mostra già)
        # st.image(image, caption='Analisi in corso...')
    
        if st.button('Calcola Carboidrati'):
            with st.spinner('Gemini sta analizzando le porzioni...'):
                # Invia l'immagine catturata dalla camera al modello
                response = model.generate_content([prompt, image])
                st.markdown("### 📊 Stima Nutrizionale")
                st.write(response.text)
        
        if st.button('Analizza Carboidrati'):
            # Il Prompt strategico
            prompt = """
            Sei un assistente nutrizionale esperto in diabete tipo 1. 
            Analizza l'immagine e:
            1. Identifica gli alimenti.
            2. Stima il peso di ogni porzione.
            3. Calcola i grammi di carboidrati.
            4. Fornisci un totale finale.
            Sii prudente e avvisa se ci sono ingredienti incerti.
            """
            
            with st.spinner('Analisi in corso...'):
                response = model.generate_content([prompt, image])
                st.subheader("Risultato Stima:")
                st.write(response.text)
                
                st.warning("⚠️ ATTENZIONE: Questa è una stima automatica. Verifica sempre i valori prima di calcolare il bolo.")
else:
    st.info("Inserisci l'API Key nella barra laterale per iniziare.")
