import streamlit as st
import json
import re
import requests
import time
import tempfile
import os
from fpdf import FPDF

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Fábrica V9 (Menu Dinâmico)", page_icon="🧬", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #574b90; color: white; height: 3.5em; border-radius: 8px; }
    .status-box { padding: 15px; border: 1px solid #ddd; border-radius: 8px; background: #fdfdfd; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("🧬 Fábrica V9 (Lista Real)")
st.info("Este sistema baixa a lista de modelos da SUA conta. Selecione um na lateral.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔑 Configuração")
    api_key = st.text_input("Sua API Key:", type="password")
    
    modelo_escolhido = None
    
    # --- LÓGICA DO MENU DINÂMICO ---
    if api_key:
        try:
            # Pergunta pro Google: "O que eu posso usar?"
            url_list = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            resp = requests.get(url_list, timeout=10)
            
            if resp.status_code == 200:
                dados = resp.json()
                # Filtra só os que geram texto
                lista_modelos = []
                if 'models' in dados:
                    for m in dados['models']:
                        if 'generateContent' in m.get('supportedGenerationMethods', []):
                            # Salva o nome exato (ex: models/gemini-1.5-flash)
                            lista_modelos.append(m['name'])
                
                if lista_modelos:
                    st.success(f"{len(lista_modelos)} modelos disponíveis!")
                    # O usuário escolhe um da lista REAL
                    modelo_escolhido = st.selectbox("Selecione o Modelo:", lista_modelos)
                else:
                    st.error("Sua chave não tem acesso a modelos de texto.")
            else:
                st.error(f"Erro na chave: {resp.status_code}")
        except Exception as e:
            st.error(f"Erro de conexão: {e}")

    st.divider()
    estilo = st.selectbox("Estilo:", ["Didático", "Storytelling", "Acadêmico", "Técnico"])

# --- FUNÇÃO CHAMADA API ---
def chamar_gemini(prompt, chave, nome_modelo_completo):
    # O nome já vem com 'models/' do menu, então usamos direto
    # Ex: https://.../v1beta/models/gemini-pro:generateContent
    url = f"https://generativelanguage.googleapis.com/v1beta/{nome_modelo_completo}:generateContent?key={chave}"
    
    headers = {"Content-Type": "application/json"}
    
    # Configuração de Segurança Mínima
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}
    ]
    
    data = {
        "contents": [{ "parts": [{"text": prompt}] }],
        "safetySettings": safety_settings
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        # Tratamento de Erro de Cota (429)
        if response.status_code == 429:
            return "ERRO 429"
            
        if response.status_code != 200:
            return f"ERRO API ({response.status_code}): {response.text}"
        
        resultado = response.json()
        
        if 'promptFeedback' in resultado and 'blockReason' in resultado['promptFeedback']:
            return f"BLOQUEIO: {resultado['promptFeedback']['blockReason']}"
            
        try:
            return resultado['candidates'][0]['content']['parts'][0]['text']
        except KeyError:
            return "ERRO: Resposta vazia do Google."
            
    except Exception as e:
        return f"ERRO CONEXÃO: {e}"

# --- FUNÇÃO RETRY ---
def tentar_gerar(prompt, chave, modelo):
    # Tenta 3 vezes
    for i in range(3):
        res = chamar_gemini(prompt, chave, modelo)
        
        if res == "ERRO 429":
            time.sleep(10) # Se for cota, espera mais
            continue
            
        if "ERRO" not in res and "BLOQUEIO" not in res:
            return res
        
        time.sleep(3)
    
    if res == "ERRO 429":
        return "COTA_ESTOURADA"
        
    return res # Retorna o erro final

# --- FUNÇÕES VISUAIS ---
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
    seed = int(time.time() * 1000) % 1000
    url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=768&nologo=true&seed={seed}"
    try:
        r = requests.get(url, timeout=20)
        return r.content if r.status_code == 200 else None
    except: return None

def gerar_pdf(plano, conteudo, img_capa_bytes):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    # Capa
    pdf.add_page()
    if img_capa_bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(img_capa_bytes)
            path = f.name
        try: pdf.image(path, x=0, y=0, w=210, h=297)
        except: pass
        try: os.remove(path)
        except: pass

    pdf.set_y(150)
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_fill_color(0,0,0)
    pdf.set_text_color(255,255,255)
    pdf.multi_cell(0, 15, limpar_texto(plano.get('titulo_livro', 'Titulo')).upper(), align="C", fill=True)
    pdf.set_y(260)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Autor: {limpar_texto(plano.get('autor_ficticio', 'IA'))}", align="C", fill=True)
    
    # Conteúdo
    for cap in conteudo:
        pdf.add_page()
        pdf.set_text_color(0,0,0)
        pdf.set_font("Helvetica", "B", 22)
        pdf.multi_cell(0, 10, limpar_texto(cap['titulo']))
        pdf.ln(5)
        
        if cap.get('imagem_bytes'):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
                f.write(cap['imagem_bytes'])
                path = f.name
            try: 
                pdf.image(path, x=30, w=150)
                pdf.ln(10)
            except: pass
            try: os.remove(path)
            except: pass
            
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(10)
        pdf.set_font("Helvetica", "", 12)
        
        texto_pag = cap['texto']
        if "ERRO" in texto_pag or "COTA" in texto_pag:
             pdf.set_text_color(255, 0, 0)
        else:
             pdf.set_text_color(0, 0, 0)
             
        pdf.multi_cell(0, 6, limpar_texto(texto_pag))
        
    return pdf.output(dest="S").encode("latin-1")

# --- APP ---
tema = st.text_input("Tema do Livro:", placeholder="Ex: Tráfego Pago")
paginas = st.slider("Páginas:", 10, 200, 30)

if st.button("🚀 INICIAR V9"):
    if not api_key: st.error("Falta API Key")
    elif not tema: st.warning("Falta Tema")
    elif not modelo_escolhido: st.error("Aguarde a lista de modelos carregar na lateral!")
    else:
        status = st.status(f"Usando {modelo_escolhido}...", expanded=True)
        
        try:
            # 1. Planejamento
            caps = int(paginas / 2.5)
            if caps < 4: caps = 4
            status.write(f"🧠 Planejando {caps} capítulos...")
            
            prompt_plan = f"""
            Atue como professor universitário. Crie plano de curso/livro sobre: {tema}.
            Meta: {paginas} paginas.
            JSON OBRIGATÓRIO:
            {{
                "titulo_livro": "...",
                "autor_ficticio": "...",
                "prompt_imagem_capa": "...",
                "estrutura": [
                    {{ "capitulo": 1, "titulo": "...", "descricao": "...", "prompt_imagem_capitulo": "..." }}
                ]
            }}
            """
            
            res = tentar_gerar(prompt_plan, api_key, modelo_escolhido)
            
            if res == "COTA_ESTOURADA":
                st.error(f"🛑 Cota do modelo {modelo_escolhido} acabou! Selecione OUTRO na lateral.")
                st.stop()
            
            if "ERRO" in res: raise Exception(res)
            
            # Extração JSON
            json_match = re.search(r'\{.*\}', res, re.DOTALL)
            if not json_match: raise Exception("JSON inválido.")
            plano = json.loads(json_match.group(0))
            
            st.success(f"📘 {plano['titulo_livro']}")
            
            # 2. Capa
            status.write("🎨 Capa...")
            img_capa = baixar_imagem(plano.get('prompt_imagem_capa', tema))
            
            # 3. Escrita
            conteudo = []
            bar = status.progress(0)
            total = len(plano['estrutura'])
            
            for i, cap in enumerate(plano['estrutura']):
                status.write(f"✍️ Cap {cap['capitulo']}/{total}: {cap['titulo']}...")
                
                prompt = f"""
                Escreva o capítulo '{cap['titulo']}' do livro '{plano['titulo_livro']}'.
                Contexto acadêmico: {cap['descricao']}.
                Texto LONGO (1000 palavras), estilo {estilo}. Sem markdown.
                """
                
                txt = tentar_gerar(prompt, api_key, modelo_escolhido)
                
                if txt == "COTA_ESTOURADA":
                    st.warning("⚠️ Cota acabou no meio. O PDF será gerado até aqui.")
                    conteudo.append({"titulo": cap['titulo'], "texto": "ERRO: Cota acabou. Tente outro modelo.", "imagem_bytes": None})
                    break
                
                status.write(f"🖼️ Ilustração {cap['capitulo']}...")
                img_cap = baixar_imagem(cap.get('prompt_imagem_capitulo', cap['titulo']))
                
                conteudo.append({"titulo": cap['titulo'], "texto": txt, "imagem_bytes": img_cap})
                bar.progress((i+1)/total)
                time.sleep(2)
                
            # 4. PDF
            status.write("🖨️ PDF...")
            pdf = gerar_pdf(plano, conteudo, img_capa)
            status.update(label="Pronto!", state="complete")
            st.download_button("📥 Baixar PDF V9", pdf, "livro_v9.pdf", "application/pdf")
            
        except Exception as e:
            st.error(f"Erro: {e}")
