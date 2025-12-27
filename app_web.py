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
st.set_page_config(page_title="Fábrica de Livros (Scanner)", page_icon="📡", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #0066cc; color: white; height: 3em; }
    .status-box { padding: 10px; border: 1px solid #ddd; border-radius: 5px; background: #f9f9f9; }
</style>
""", unsafe_allow_html=True)

st.title("📡 Fábrica de Livros (Auto-Detector)")
st.caption("Este sistema detecta automaticamente quais modelos sua chave pode acessar.")

# --- BARRA LATERAL INTELIGENTE ---
with st.sidebar:
    st.header("🔑 Acesso")
    api_key = st.text_input("Cole sua API Key do Google:", type="password")
    
    modelo_escolhido = None
    
    if api_key:
        try:
            genai.configure(api_key=api_key)
            # O "Scanner": Lista apenas modelos que geram texto
            modelos_disponiveis = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    modelos_disponiveis.append(m.name)
            
            if modelos_disponiveis:
                st.success(f"✅ {len(modelos_disponiveis)} Modelos encontrados!")
                # Remove o prefixo 'models/' para ficar mais limpo na visualização
                lista_limpa = [m.replace("models/", "") for m in modelos_disponiveis]
                
                # Tenta selecionar o Flash automaticamente, se não, pega o primeiro
                index_padrao = 0
                for i, nome in enumerate(lista_limpa):
                    if "flash" in nome:
                        index_padrao = i
                        break
                
                modelo_selecionado_nome = st.selectbox("Selecione o Modelo:", lista_limpa, index=index_padrao)
                modelo_escolhido = modelo_selecionado_nome # Salva a escolha
            else:
                st.error("Nenhum modelo disponível para esta chave.")
        except Exception as e:
            st.error(f"Erro na chave: {e}")
            
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
    texto = texto.replace("**", "").replace("*", "").replace("##", "").replace("#", "")
    return re.sub(r'[^\x00-\x7FáéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ0-9.,:;?!()"\'-]', '', texto)

def baixar_imagem(prompt):
    url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1080&height=1420&nologo=true"
    try:
        r = requests.get(url, timeout=10)
        return r.content if r.status_code == 200 else None
    except: return None

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
    if not api_key or not modelo_escolhido:
        st.error("Configure a chave e escolha o modelo na barra lateral!")
    elif not tema:
        st.warning("Digite o tema.")
    else:
        try:
            # Configura com o modelo ESCOLHIDO pelo usuário (Sem erro 404!)
            model = genai.GenerativeModel(modelo_escolhido)
            status = st.status("🏗️ Trabalhando...", expanded=True)
            
            # 1. Planejamento
            caps = int(paginas / 2.5)
            if caps < 4: caps = 4
            status.write(f"🧠 Planejando {caps} capítulos usando {modelo_escolhido}...")
            
            prompt_plan = f"""
            Crie estrutura de livro sobre {tema}. Meta: {paginas} páginas.
            Retorne APENAS JSON:
            {{ "titulo_livro": "...", "autor_ficticio": "...", "prompt_imagem": "...", 
               "estrutura": [ {{ "capitulo": 1, "titulo": "...", "descricao": "..." }} ] }}
            """
            res = model.generate_content(prompt_plan)
            plano = json.loads(res.text.replace("```json","").replace("```","").strip())
            st.success(f"📖 {plano['titulo_livro']}")
            
            # 2. Capa
            img = baixar_imagem(plano.get('prompt_imagem', f"Cover {tema}"))
            
            # 3. Escrita
            conteudo = []
            bar = status.progress(0)
            total = len(plano['estrutura'])
            
            for i, cap in enumerate(plano['estrutura']):
                status.write(f"✍️ Escrevendo {cap['capitulo']}/{total}...")
                prompt_text = f"Escreva cap '{cap['titulo']}' do livro '{plano['titulo_livro']}'. Contexto: {cap['descricao']}. Texto LONGO ({estilo})."
                
                try:
                    txt = model.generate_content(prompt_text).text
                    conteudo.append({"titulo": cap['titulo'], "texto": txt})
                except:
                    conteudo.append({"titulo": cap['titulo'], "texto": "[Erro geração]"})
                
                bar.progress((i+1)/total)
                time.sleep(1)
                
            # 4. PDF
            status.write("🖨️ Gerando PDF...")
            pdf_bytes = gerar_pdf(plano, conteudo, img)
            
            status.update(label="Concluído!", state="complete")
            st.download_button("📥 Baixar PDF", pdf_bytes, "livro.pdf", "application/pdf")
            
        except Exception as e:
            st.error(f"Erro: {e}")
