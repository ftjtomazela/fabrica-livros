import streamlit as st
import google.generativeai as genai
import json
import re
import requests
import time
import tempfile
import os
from fpdf import FPDF

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Fábrica de Livros (Auto-Fix)", page_icon="🛠️", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #27ae60; color: white; height: 3.5em; border-radius: 8px; }
    .status-box { padding: 15px; border: 1px solid #ddd; border-radius: 8px; background: #eef9f0; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("🛠️ Fábrica de Livros (Sistema Anti-Erro)")
st.caption("Este sistema testa 5 modelos diferentes até achar um que funcione na sua conta.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔑 Configuração")
    api_key = st.text_input("Cole sua API Key do Google:", type="password")
    st.markdown("[Criar Chave Grátis](https://aistudio.google.com/app/apikey)")
    st.divider()
    estilo = st.selectbox("Estilo:", ["Didático", "Storytelling", "Acadêmico", "Técnico"])

# --- FUNÇÕES ---
class PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def limpar_texto(texto):
    if not texto: return ""
    return re.sub(r'[^\x00-\x7FáéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ0-9.,:;?!()"\'-]', '', texto)

def baixar_imagem(prompt):
    url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1080&height=1420&nologo=true"
    try:
        r = requests.get(url, timeout=10)
        return r.content if r.status_code == 200 else None
    except: return None

def encontrar_modelo_funcionando():
    """Testa vários nomes de modelos até um funcionar"""
    lista_tentativas = [
        "gemini-1.5-flash", 
        "gemini-1.5-flash-latest", 
        "gemini-1.5-flash-001",
        "gemini-pro",
        "gemini-1.0-pro"
    ]
    
    status_check = st.empty()
    
    for nome_modelo in lista_tentativas:
        try:
            status_check.text(f"Testando conexão com: {nome_modelo}...")
            model = genai.GenerativeModel(nome_modelo)
            # Teste rápido
            model.generate_content("Oi")
            status_check.empty()
            return model, nome_modelo
        except:
            continue
            
    status_check.empty()
    return None, None

def gerar_pdf(plano, conteudo, img_bytes):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    # Capa
    pdf.add_page()
    if img_bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(img_bytes)
            path = f.name
        try: pdf.image(path, x=0, y=0, w=210, h=297)
        except: pass
        try: os.remove(path)
        except: pass

    pdf.set_y(150)
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_fill_color(0,0,0)
    pdf.set_text_color(255,255,255)
    pdf.multi_cell(0, 15, limpar_texto(plano['titulo_livro']).upper(), align="C", fill=True)
    pdf.set_y(260)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Autor: {limpar_texto(plano['autor_ficticio'])}", align="C", fill=True)
    
    # Conteúdo
    for cap in conteudo:
        pdf.add_page()
        pdf.set_text_color(0,0,0)
        pdf.set_font("Helvetica", "B", 22)
        pdf.multi_cell(0, 10, limpar_texto(cap['titulo']))
        pdf.ln(5)
        pdf.set_font("Helvetica", "", 12)
        pdf.multi_cell(0, 6, limpar_texto(cap['texto']))
        
    return pdf.output(dest="S").encode("latin-1")

# --- APP PRINCIPAL ---
tema = st.text_input("Tema do Livro:")
paginas = st.slider("Meta de Páginas:", 10, 200, 30)

if st.button("🚀 INICIAR"):
    if not api_key:
        st.error("Cole a API Key na barra lateral!")
    elif not tema:
        st.warning("Digite o tema.")
    else:
        # Configura a chave
        genai.configure(api_key=api_key)
        
        # --- AQUI ESTÁ A MÁGICA: AUTO-DETECÇÃO ---
        model, nome_ok = encontrar_modelo_funcionando()
        
        if not model:
            st.error("❌ Erro Fatal: Nenhum modelo funcionou com essa chave. Verifique se a chave foi criada num 'Novo Projeto' no Google AI Studio.")
        else:
            status = st.status(f"✅ Conectado no modelo: {nome_ok}", expanded=True)
            
            try:
                # 1. Planejamento
                caps = int(paginas / 2.5)
                if caps < 4: caps = 4
                status.write(f"🧠 Planejando {caps} capítulos...")
                
                prompt_plan = f"""
                Crie estrutura de livro sobre {tema}. Meta: {paginas} páginas.
                Retorne APENAS JSON:
                {{ "titulo_livro": "...", "autor_ficticio": "...", "prompt_imagem": "...", 
                   "estrutura": [ {{ "capitulo": 1, "titulo": "...", "descricao": "..." }} ] }}
                """
                res = model.generate_content(prompt_plan)
                plano = json.loads(res.text.replace("```json","").replace("```","").strip())
                st.success(f"📖 Título: {plano['titulo_livro']}")
                
                # 2. Capa
                status.write("🎨 Gerando capa...")
                img = baixar_imagem(plano.get('prompt_imagem', f"Cover {tema}"))
                
                # 3. Escrita
                conteudo = []
                bar = status.progress(0)
                total = len(plano['estrutura'])
                
                for i, cap in enumerate(plano['estrutura']):
                    status.write(f"✍️ Escrevendo {cap['capitulo']}/{total}: {cap['titulo']}...")
                    prompt_text = f"Escreva cap '{cap['titulo']}' do livro '{plano['titulo_livro']}'. Contexto: {cap['descricao']}. Texto LONGO e detalhado ({estilo})."
                    
                    try:
                        # Tenta gerar
                        txt = model.generate_content(prompt_text).text
                        conteudo.append({"titulo": cap['titulo'], "texto": txt})
                    except:
                        # Se falhar, espera 2s e tenta de novo
                        time.sleep(2)
                        try:
                            txt = model.generate_content(prompt_text).text
                            conteudo.append({"titulo": cap['titulo'], "texto": txt})
                        except:
                            conteudo.append({"titulo": cap['titulo'], "texto": "[Erro na geração deste capítulo]"})
                    
                    bar.progress((i+1)/total)
                    time.sleep(1)
                    
                # 4. PDF
                status.write("🖨️ Finalizando PDF...")
                pdf_bytes = gerar_pdf(plano, conteudo, img)
                
                status.update(label="Sucesso! Baixe abaixo.", state="complete")
                st.balloons()
                st.download_button("📥 Baixar Livro PDF", pdf_bytes, "livro_ia.pdf", "application/pdf")
                
            except Exception as e:
                st.error(f"Erro durante a criação: {e}")
