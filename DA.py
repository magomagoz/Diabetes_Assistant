import streamlit as st
import google.generativeai as genai
from PIL import Image
import os

# Configurazione della pagina Streamlit
st.set_page_config(page_title="Diabete-IA Helper", layout="centered")
st.title("🥗 Conta Carboidrati con Gemini")
st.write("Carica la foto del tuo piatto per una stima dei carboidrati (CHO).")

# Recupero API Key (da impostare nei Secrets di Streamlit/GitHub)
api_key = AIzaSyBZQjSbU_e8RidjOpOjSAchnwM8XBvG-lQ

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    uploaded_file = st.file_uploader("Scegli un'immagine...", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='Piatto analizzato', use_column_width=True)
        
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
