import streamlit as st
import json
import re
import requests
import time
import tempfile
import os
from fpdf import FPDF

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Fábrica de Livros (Anti-Falha)", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #27ae60; color: white; height: 3.5em; border-radius: 8px; }
    .status-box { padding: 15px; border: 1px solid #ddd; border-radius: 8px; background: #e8f5e9; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Fábrica de Livros (Sistema de Persistência)")
st.info("Este sistema tenta gerar cada capítulo até 3 vezes caso ocorra erro de conexão.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔑 Acesso")
    api_key = st.text_input("Sua API Key do Google:", type="password")
    st.markdown("[Criar Chave Grátis](https://aistudio.google.com/app/apikey)")
    st.divider()
    estilo = st.selectbox("Estilo do Texto:", ["Didático", "Storytelling", "Acadêmico", "Técnico"])

# --- FUNÇÃO 1: O DETETIVE ---
def detectar_modelo_disponivel(chave):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={chave}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return None, response.text
        dados = response.json()
        if 'models' in dados:
            for m in dados['models']:
                if 'generateContent' in m.get('supportedGenerationMethods', []) and 'flash' in m['name']:
                    return m['name'], None
            for m in dados['models']:
                if 'generateContent' in m.get('supportedGenerationMethods', []):
                    return m['name'], None
        return None, "Nenhum modelo encontrado."
    except Exception as e: return None, str(e)

# --- FUNÇÃO 2: O ESCRITOR (Direto via HTTP) ---
def chamar_gemini(prompt, chave, nome_modelo):
    url = f"https://generativelanguage.googleapis.com/v1beta/{nome_modelo}:generateContent?key={chave}"
    headers = {"Content-Type": "application/json"}
    data = { "contents": [{ "parts": [{"text": prompt}] }] }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        if response.status_code != 200: return f"ERRO API: {response.status_code}"
        
        resultado = response.json()
        try:
            return resultado['candidates'][0]['content']['parts'][0]['text']
        except KeyError:
            # As vezes o Google bloqueia por segurança (Safety Filter) e não retorna texto
            return "ERRO: Conteúdo bloqueado pelo filtro de segurança do Google."
    except Exception as e:
        return f"ERRO CONEXÃO: {e}"

# --- NOVA FUNÇÃO: A TEIMOSIA (RETRY) ---
def tentar_gerar_com_retry(prompt, chave, modelo, tentativas=3):
    """Tenta gerar o texto. Se falhar, espera e tenta de novo."""
    for i in range(tentativas):
        texto = chamar_gemini(prompt, chave, modelo)
        
        if "ERRO" not in texto:
            return texto # Sucesso!
        
        # Se deu erro, espera um pouco (Backoff exponencial)
        tempo_espera = (i + 1) * 3 # Espera 3s, depois 6s, depois 9s...
        time.sleep(tempo_espera)
    
    return "[ERRO PERSISTENTE] O Google rejeitou este capítulo 3 vezes. Provável sobrecarga ou filtro de segurança."

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
    # Adicionando timestamp para evitar cache
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
        
        # Imagem Capítulo
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
        pdf.multi_cell(0, 6, limpar_texto(cap['texto']))
        
    return pdf.output(dest="S").encode("latin-1")

# --- APP ---
tema = st.text_input("Tema do Livro:", placeholder="Ex: Marketing Digital")
paginas = st.slider("Páginas:", 10, 200, 30)

if st.button("🚀 INICIAR BLINDADO"):
    if not api_key: st.error("Falta a API Key!")
    elif not tema: st.warning("Falta o tema.")
    else:
        status = st.status("🔍 Detectando modelo...", expanded=True)
        modelo, erro = detectar_modelo_disponivel(api_key)
        
        if not modelo:
            status.update(label="Erro na Chave", state="error")
            st.error(erro)
        else:
            status.write(f"✅ Modelo: {modelo}")
            try:
                # 1. Planejamento
                caps = int(paginas / 2.5)
                if caps < 4: caps = 4
                status.write(f"🧠 Planejando {caps} capítulos...")
                
                prompt_plan = f"""
                Crie JSON de livro sobre {tema}. {paginas} paginas.
                Inclua prompts de imagem para capa e capitulos.
                JSON: {{ "titulo_livro": "...", "autor_ficticio": "...", "prompt_imagem_capa": "...", 
                "estrutura": [ {{ "capitulo": 1, "titulo": "...", "descricao": "...", "prompt_imagem_capitulo": "..." }} ] }}
                """
                
                # Usa Retry no planejamento também
                res = tentar_gerar_com_retry(prompt_plan, api_key, modelo)
                if "ERRO" in res: raise Exception("Falha ao criar o plano do livro.")
                
                json_str = res.replace("```json", "").replace("```", "").strip()
                s = json_str.find('{'); e = json_str.rfind('}') + 1
                plano = json.loads(json_str[s:e])
                st.success(f"📘 {plano['titulo_livro']}")
                
                # 2. Capa
                status.write("🎨 Capa...")
                img_capa = baixar_imagem(plano.get('prompt_imagem_capa', tema))
                
                # 3. Escrita (Com Retry)
                conteudo = []
                bar = status.progress(0)
                total = len(plano['estrutura'])
                
                for i, cap in enumerate(plano['estrutura']):
                    status.write(f"✍️ Cap {cap['capitulo']}/{total}: {cap['titulo']}...")
                    
                    # AQUI ESTÁ A CORREÇÃO PRINCIPAL: Tentar 3 vezes
                    prompt = f"Escreva cap '{cap['titulo']}' do livro '{plano['titulo_livro']}'. Contexto: {cap['descricao']}. Texto LONGO (1000 palavras), estilo {estilo}. Sem markdown."
                    txt = tentar_gerar_com_retry(prompt, api_key, modelo)
                    
                    status.write(f"🖼️ Imagem Cap {cap['capitulo']}...")
                    img_cap = baixar_imagem(cap.get('prompt_imagem_capitulo', cap['titulo']))
                    
                    conteudo.append({"titulo": cap['titulo'], "texto": txt, "imagem_bytes": img_cap})
                    bar.progress((i+1)/total)
                    time.sleep(2) # Pausa obrigatória para não travar o Google
                    
                # 4. PDF
                status.write("🖨️ PDF...")
                pdf = gerar_pdf(plano, conteudo, img_capa)
                status.update(label="Concluído!", state="complete")
                st.download_button("📥 Baixar PDF", pdf, "livro_final.pdf", "application/pdf")
                
            except Exception as e: st.error(f"Erro Fatal: {e}")
