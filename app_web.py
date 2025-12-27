import streamlit as st
from google import genai # <--- ESSA É A BIBLIOTECA NOVA
from google.genai import types
import json
import re
import requests
import time
import tempfile
import os
from fpdf import FPDF

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Editora IA (Versão Final)", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #2e86de; color: white; height: 3em; border-radius: 8px; }
    .status-box { padding: 15px; border-radius: 10px; background-color: #f8f9fa; border: 1px solid #ddd; margin-bottom: 20px; }
    h1 { color: #2c3e50; }
</style>
""", unsafe_allow_html=True)

st.title("💎 Fábrica de Livros (Google GenAI V1)")
st.caption("Código atualizado para a nova biblioteca oficial do Google.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configuração")
    api_key = st.text_input("Sua API Key do Google:", type="password")
    st.markdown("[Criar Chave Grátis Aqui](https://aistudio.google.com/app/apikey)")
    st.divider()
    estilo_texto = st.selectbox("Estilo do Texto:", 
        ["Didático e Simples", "Acadêmico", "Storytelling (História)", "Técnico Profissional"])

# --- FUNÇÕES TÉCNICAS ---
class PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def limpar_texto(texto):
    if not texto: return ""
    # Remove formatações Markdown que estragam o PDF
    texto = texto.replace("**", "").replace("*", "").replace("##", "").replace("#", "")
    return re.sub(r'[^\x00-\x7FáéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ0-9.,:;?!()"\'-]', '', texto)

def baixar_imagem_capa(prompt_imagem):
    prompt_formatado = prompt_imagem.replace(" ", "%20")
    # Pollinations gera imagem sem precisar de chave
    url = f"https://image.pollinations.ai/prompt/{prompt_formatado}?width=1080&height=1420&nologo=true&seed=42"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.content
    except:
        return None
    return None

def gerar_pdf_final(plano, conteudo_completo, imagem_bytes):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    # 1. CAPA
    pdf.add_page()
    if imagem_bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            tmp_file.write(imagem_bytes)
            tmp_path = tmp_file.name
        try:
            pdf.image(tmp_path, x=0, y=0, w=210, h=297)
        except: pass
        try: os.remove(tmp_path)
        except: pass

    pdf.set_y(150)
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_fill_color(0, 0, 0) 
    pdf.set_text_color(255, 255, 255)
    
    titulo = limpar_texto(plano['titulo_livro']).upper()
    pdf.multi_cell(0, 15, titulo, align="C", fill=True)
    
    pdf.set_y(260)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Autor IA: {limpar_texto(plano['autor_ficticio'])}", align="C", fill=True)

    # 2. SUMÁRIO
    pdf.add_page()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 20, "SUMÁRIO", ln=True, align='C')
    pdf.set_font("Helvetica", "", 12)
    for cap in plano['estrutura']:
        pdf.cell(0, 10, f"{cap['capitulo']}. {limpar_texto(cap['titulo'])}", ln=True)

    # 3. CONTEÚDO
    for capitulo in conteudo_completo:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(41, 128, 185)
        pdf.multi_cell(0, 12, limpar_texto(capitulo['titulo']))
        pdf.ln(5)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(10)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, limpar_texto(capitulo['texto']))
        
    return pdf.output(dest="S").encode("latin-1")

# --- LÓGICA PRINCIPAL ---
tema = st.text_input("Tema do Livro:", placeholder="Ex: Guia de Sobrevivência na Selva")
col1, col2 = st.columns(2)
with col1:
    paginas_alvo = st.slider("Meta de Páginas:", 10, 200, 30)
with col2:
    densidade = st.slider("Profundidade (1-5):", 1, 5, 4)

if st.button("🚀 INICIAR SISTEMA"):
    if not api_key:
        st.error("⚠️ Cole sua API Key na barra lateral!")
    elif not tema:
        st.warning("⚠️ Digite um tema.")
    else:
        # --- CÓDIGO ATUALIZADO PARA A NOVA BIBLIOTECA ---
        try:
            client = genai.Client(api_key=api_key)
            
            status = st.status("🏗️ Iniciando os motores...", expanded=True)
            
            # 1. PLANEJAMENTO
            num_capitulos = int(paginas_alvo / 2.5) 
            if num_capitulos < 4: num_capitulos = 4
            
            status.write(f"🧠 Planejando {num_capitulos} capítulos...")
            
            prompt_plan = f"""
            Crie a estrutura de um livro sobre: {tema}.
            Meta: {paginas_alvo} páginas ({num_capitulos} capítulos).
            Retorne APENAS JSON puro:
            {{
                "titulo_livro": "...",
                "autor_ficticio": "...",
                "prompt_imagem_capa": "...",
                "estrutura": [
                    {{"capitulo": 1, "titulo": "...", "descricao": "..."}}
                ]
            }}
            """
            
            # Usa o modelo Gemini 1.5 Flash (Gratuito e Rápido)
            res_plan = client.models.generate_content(
                model='gemini-1.5-flash', 
                contents=prompt_plan,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            plano = json.loads(res_plan.text)
            st.success(f"📘 {plano['titulo_livro']}")
            
            # 2. CAPA
            status.write("🎨 Pintando a capa...")
            img_bytes = baixar_imagem_capa(plano.get('prompt_imagem_capa', f"Book cover {tema}"))
            
            # 3. ESCRITA
            conteudo = []
            barra = status.progress(0)
            total_caps = len(plano['estrutura'])
            
            for i, cap in enumerate(plano['estrutura']):
                status.write(f"✍️ Escrevendo Cap {cap['capitulo']}/{total_caps}...")
                
                prompt_text = f"""
                Escreva o CAPÍTULO {cap['capitulo']}: '{cap['titulo']}' do livro '{plano['titulo_livro']}'.
                Contexto: {cap['descricao']}
                REGRAS:
                - Texto LONGO (mínimo 1000 palavras).
                - Estilo: {estilo_texto}.
                - Apenas texto corrido, sem markdown complexo.
                """
                
                try:
                    res_text = client.models.generate_content(
                        model='gemini-1.5-flash', 
                        contents=prompt_text
                    )
                    conteudo.append({"titulo": cap['titulo'], "texto": res_text.text})
                except Exception as e:
                    time.sleep(2)
                    try:
                        res_text = client.models.generate_content(
                            model='gemini-1.5-flash', 
                            contents=prompt_text
                        )
                        conteudo.append({"titulo": cap['titulo'], "texto": res_text.text})
                    except:
                        conteudo.append({"titulo": cap['titulo'], "texto": "[Erro na geração]"})

                barra.progress((i + 1) / total_caps)
                time.sleep(1)

            # 4. PDF
            status.write("🖨️ Diagramando PDF...")
            pdf_bytes = gerar_pdf_final(plano, conteudo, img_bytes)
            
            status.update(label="✅ Finalizado!", state="complete", expanded=False)
            st.balloons()
            
            st.download_button(
                label="📥 BAIXAR LIVRO PDF",
                data=pdf_bytes,
                file_name=f"Livro_IA.pdf",
                mime="application/pdf"
            )

        except Exception as e:
            st.error(f"Erro: {e}")