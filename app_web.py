import streamlit as st
import json
import re
import requests
import time
import tempfile
import os
from fpdf import FPDF

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Fábrica V7 (Anti-Bloqueio)", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #27ae60; color: white; height: 3.5em; border-radius: 8px; }
    .status-box { padding: 15px; border: 1px solid #ddd; border-radius: 8px; background: #e8f5e9; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Fábrica V7 (Diagnóstico & Anti-Bloqueio)")
st.info("Sistema otimizado para temas sensíveis (Marketing/Finanças) e com relatórios de erro detalhados.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔑 Acesso")
    api_key = st.text_input("Sua API Key do Google:", type="password")
    st.markdown("[Criar Chave Grátis](https://aistudio.google.com/app/apikey)")
    st.divider()
    estilo = st.selectbox("Estilo do Texto:", ["Didático", "Storytelling", "Acadêmico", "Técnico"])

# --- FUNÇÃO DETETIVE (Melhorada) ---
def detectar_modelo_disponivel(chave):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={chave}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return None, f"Erro HTTP {response.status_code}: {response.text}"
        dados = response.json()
        
        # 1. Tenta achar o Flash (Rápido e Estável)
        if 'models' in dados:
            for m in dados['models']:
                if 'flash' in m['name'] and 'generateContent' in m.get('supportedGenerationMethods', []):
                    return m['name'], None
            
            # 2. Se não, pega o Pro
            for m in dados['models']:
                if 'generateContent' in m.get('supportedGenerationMethods', []):
                    return m['name'], None
                    
        return None, "Nenhum modelo de texto liberado na sua chave."
    except Exception as e: return None, str(e)

# --- FUNÇÃO CHAMADA API (Com logs de erro) ---
def chamar_gemini(prompt, chave, nome_modelo):
    url = f"https://generativelanguage.googleapis.com/v1beta/{nome_modelo}:generateContent?key={chave}"
    headers = {"Content-Type": "application/json"}
    
    # Configuração de Segurança para aceitar temas como "Tráfego Pago"
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
        
        if response.status_code != 200:
            return f"ERRO API ({response.status_code}): {response.text}"
        
        resultado = response.json()
        
        # Verifica se foi bloqueado por segurança
        if 'promptFeedback' in resultado and 'blockReason' in resultado['promptFeedback']:
            return f"BLOQUEIO: O Google bloqueou o tema por segurança ({resultado['promptFeedback']['blockReason']})."
            
        try:
            return resultado['candidates'][0]['content']['parts'][0]['text']
        except KeyError:
            return "ERRO: Resposta vazia ou bloqueada pelo filtro de conteúdo."
            
    except Exception as e:
        return f"ERRO CONEXÃO: {e}"

# --- FUNÇÃO RETRY (Mais paciente) ---
def tentar_gerar_com_retry(prompt, chave, modelo, tentativas=3):
    """Tenta 3 vezes. Se for erro 429 (Muitos pedidos), espera mais tempo."""
    erros_log = []
    
    for i in range(tentativas):
        res = chamar_gemini(prompt, chave, modelo)
        
        if "ERRO" not in res and "BLOQUEIO" not in res:
            return res
        
        erros_log.append(res)
        
        # Se for erro de Cota (429), espera 15 segundos. Se não, 5.
        wait_time = 15 if "429" in res else 5
        time.sleep(wait_time)
    
    return f"[FALHA FINAL] Não foi possível gerar após 3 tentativas. Último erro: {erros_log[-1]}"

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
        if "FALHA FINAL" in texto_pag or "ERRO" in texto_pag:
             pdf.set_text_color(255, 0, 0) # Vermelho para avisar erro
        else:
             pdf.set_text_color(0, 0, 0)
             
        pdf.multi_cell(0, 6, limpar_texto(texto_pag))
        
    return pdf.output(dest="S").encode("latin-1")

# --- APP ---
tema = st.text_input("Tema do Livro:", placeholder="Ex: Tráfego Pago e Marketing")
paginas = st.slider("Páginas:", 10, 200, 30)

if st.button("🚀 INICIAR V7 (DIAGNÓSTICO)"):
    if not api_key: st.error("Falta a API Key!")
    elif not tema: st.warning("Falta o tema.")
    else:
        status = st.status("🔍 Detectando modelo...", expanded=True)
        modelo, erro = detectar_modelo_disponivel(api_key)
        
        if not modelo:
            status.update(label="Erro Crítico", state="error")
            st.error(f"Não foi possível conectar. Motivo: {erro}")
        else:
            status.write(f"✅ Modelo Detectado: {modelo}")
            try:
                # 1. Planejamento (Com prompt 'Acadêmico' para evitar bloqueio)
                caps = int(paginas / 2.5)
                if caps < 4: caps = 4
                status.write(f"🧠 Planejando {caps} capítulos...")
                
                # Prompt modificado para passar nos filtros de segurança
                prompt_plan = f"""
                Atue como um professor universitário. Crie um plano de curso (livro) estritamente EDUCACIONAL e TEÓRICO sobre: {tema}.
                Objetivo: Ensinar conceitos técnicos de forma ética.
                Meta: {paginas} páginas.
                Saída OBRIGATÓRIA em JSON:
                {{
                    "titulo_livro": "...",
                    "autor_ficticio": "...",
                    "prompt_imagem_capa": "...",
                    "estrutura": [
                        {{ "capitulo": 1, "titulo": "...", "descricao": "...", "prompt_imagem_capitulo": "..." }}
                    ]
                }}
                """
                
                res = tentar_gerar_com_retry(prompt_plan, api_key, modelo)
                
                # Se falhar aqui, mostra o erro EXATO para sabermos o que houve
                if "ERRO" in res or "FALHA" in res:
                    raise Exception(f"Erro no Planejamento: {res}")
                
                # Limpeza JSON Robusta (Regex)
                json_match = re.search(r'\{.*\}', res, re.DOTALL)
                if not json_match:
                    raise Exception(f"O Google não retornou JSON válido. Retornou: {res[:100]}...")
                
                json_str = json_match.group(0)
                plano = json.loads(json_str)
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
                    
                    # Prompt também suavizado para evitar bloqueio
                    prompt = f"""
                    Escreva o capítulo '{cap['titulo']}' do livro '{plano['titulo_livro']}'.
                    Contexto puramente educacional: {cap['descricao']}.
                    Texto LONGO (1000 palavras), estilo {estilo}. Sem markdown. Foco técnico.
                    """
                    
                    txt = tentar_gerar_com_retry(prompt, api_key, modelo)
                    
                    status.write(f"🖼️ Ilustrando Cap {cap['capitulo']}...")
                    img_cap = baixar_imagem(cap.get('prompt_imagem_capitulo', cap['titulo']))
                    
                    conteudo.append({"titulo": cap['titulo'], "texto": txt, "imagem_bytes": img_cap})
                    bar.progress((i+1)/total)
                    time.sleep(2)
                    
                # 4. PDF
                status.write("🖨️ PDF...")
                pdf = gerar_pdf(plano, conteudo, img_capa)
                status.update(label="Concluído!", state="complete")
                st.download_button("📥 Baixar PDF V7", pdf, "livro_v7.pdf", "application/pdf")
                
            except Exception as e:
                status.update(label="Erro Fatal", state="error")
                st.error(f"🛑 OCORREU UM ERRO: {e}")
