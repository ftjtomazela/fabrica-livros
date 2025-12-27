import streamlit as st
import google.generativeai as genai
import json
import re
import requests
import time
import tempfile
import os
from fpdf import FPDF

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Editora IA Gemini Blindada", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #009900; color: white; height: 3em; }
    .status-box { padding: 10px; border-radius: 5px; border: 1px solid #ddd; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Fábrica de Livros (Versão Blindada)")
st.info("Sistema de auto-recuperação: Se um modelo falhar, ele tenta outro automaticamente.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("AIzaSyBGh_CJgiqxy7N5xyzCMPrtmUubpsCAutQ", type="password")
    st.markdown("[Pegar Chave Grátis](https://aistudio.google.com/app/apikey)")
    st.divider()
    estilo_texto = st.selectbox("Estilo:", 
        ["Didático", "Acadêmico", "Storytelling", "Técnico"])

# --- FUNÇÕES TÉCNICAS ---
class PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def limpar_texto(texto):
    if not texto: return ""
    texto = texto.replace("**", "").replace("*", "").replace("##", "").replace("#", "")
    return re.sub(r'[^\x00-\x7FáéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ0-9.,:;?!()"\'-]', '', texto)

def baixar_imagem_capa(prompt_imagem):
    prompt_formatado = prompt_imagem.replace(" ", "%20")
    url = f"https://image.pollinations.ai/prompt/{prompt_formatado}?width=1080&height=1420&nologo=true&seed=42"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.content
    except:
        return None
    return None

def obter_modelo_disponivel():
    """Tenta encontrar um modelo que funcione na sua conta para evitar erro 404"""
    tentativas = ['gemini-1.5-flash', 'gemini-1.5-flash-latest', 'gemini-pro', 'gemini-1.0-pro']
    
    for nome_modelo in tentativas:
        try:
            model = genai.GenerativeModel(nome_modelo)
            # Teste rápido para ver se conecta
            model.generate_content("Teste")
            return model, nome_modelo
        except:
            continue
    return None, None

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

    pdf.set_y(140)
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_fill_color(0, 0, 0) 
    pdf.set_text_color(255, 255, 255)
    titulo = limpar_texto(plano['titulo_livro']).upper()
    pdf.multi_cell(0, 15, titulo, align="C", fill=True)
    
    pdf.set_y(260)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Autor: {limpar_texto(plano['autor_ficticio'])}", align="C", fill=True)

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
        pdf.set_text_color(0, 51, 102)
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
tema = st.text_input("Tema do Livro:", placeholder="Ex: Astronomia para Iniciantes")
paginas_alvo = st.slider("Meta de Páginas:", 10, 200, 50)

if st.button("🚀 INICIAR SISTEMA"):
    if not api_key:
        st.error("⚠️ Coloque a API Key!")
    elif not tema:
        st.warning("⚠️ Digite um tema.")
    else:
        genai.configure(api_key=api_key)
        
        # --- BLINDAGEM CONTRA ERRO 404 ---
        status = st.status("🔍 Procurando modelo disponível...", expanded=True)
        model, nome_ativo = obter_modelo_disponivel()
        
        if not model:
            status.update(label="❌ Erro Fatal", state="error")
            st.error("Sua API Key não está aceitando nenhum modelo (Flash ou Pro). Verifique no Google AI Studio.")
        else:
            status.write(f"✅ Conectado com sucesso ao modelo: {nome_ativo}")
            
            try:
                # 1. PLANEJAMENTO
                num_capitulos = int(paginas_alvo / 2.5)
                if num_capitulos < 5: num_capitulos = 5
                
                status.write(f"🧠 Planejando {num_capitulos} capítulos...")
                
                prompt_plan = f"""
                Crie a estrutura de um livro sobre: {tema}.
                Meta: {paginas_alvo} páginas ({num_capitulos} capítulos).
                Retorne APENAS JSON:
                {{
                    "titulo_livro": "...",
                    "autor_ficticio": "...",
                    "prompt_imagem_capa": "...",
                    "estrutura": [
                        {{"capitulo": 1, "titulo": "...", "descricao": "..."}}
                    ]
                }}
                """
                
                res_plan = model.generate_content(prompt_plan)
                texto_json = res_plan.text.replace("```json", "").replace("```", "").strip()
                plano = json.loads(texto_json)
                st.success(f"📘 {plano['titulo_livro']}")
                
                # 2. CAPA
                status.write("🎨 Gerando capa...")
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
                    REGRAS: Texto LONGO (800+ palavras), detalhado, estilo {estilo_texto}. Sem markdown complexo.
                    """
                    
                    try:
                        res_text = model.generate_content(prompt_text)
                        conteudo.append({"titulo": cap['titulo'], "texto": res_text.text})
                    except:
                        time.sleep(2) # Espera e tenta de novo se falhar
                        try:
                            res_text = model.generate_content(prompt_text)
                            conteudo.append({"titulo": cap['titulo'], "texto": res_text.text})
                        except:
                            conteudo.append({"titulo": cap['titulo'], "texto": "[Erro ao gerar este capítulo]"})

                    barra.progress((i + 1) / total_caps)
                    time.sleep(1)

                # 4. PDF
                status.write("🖨️ Gerando PDF...")
                pdf_bytes = gerar_pdf_final(plano, conteudo, img_bytes)
                
                status.update(label="✅ Finalizado!", state="complete", expanded=False)
                st.balloons()
                
                st.download_button(
                    label="📥 BAIXAR LIVRO PDF",
                    data=pdf_bytes,
                    file_name="Livro_IA.pdf",
                    mime="application/pdf"
                )

            except Exception as e:
                st.error(f"Erro durante o processo: {e}")