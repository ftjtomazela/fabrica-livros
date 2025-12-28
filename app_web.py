import streamlit as st
import json
import re
import requests
import time
import tempfile
import os
from fpdf import FPDF

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Fábrica de Livros (Auto-Detect)", page_icon="🕵️", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #008080; color: white; height: 3.5em; border-radius: 8px; }
    .status-box { padding: 15px; border: 1px solid #ddd; border-radius: 8px; background: #e0f7fa; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("🕵️ Fábrica de Livros (Detector Automático)")
st.info("Este sistema pergunta ao Google qual modelo está disponível na sua conta antes de começar.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔑 Acesso")
    api_key = st.text_input("Sua API Key do Google:", type="password")
    st.markdown("[Criar Chave Grátis](https://aistudio.google.com/app/apikey)")
    st.divider()
    estilo = st.selectbox("Estilo:", ["Didático", "Storytelling", "Acadêmico", "Técnico"])

# --- FUNÇÃO 1: O DETETIVE (Descobre o nome do modelo) ---
def detectar_modelo_disponivel(chave):
    """Pergunta ao Google quais modelos existem para essa chave"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={chave}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None, f"Erro ao listar modelos: {response.text}"
            
        dados = response.json()
        
        # Procura um modelo que gere texto
        if 'models' in dados:
            # 1. Tenta achar o FLASH (mais rápido)
            for m in dados['models']:
                nome = m['name'] 
                metodos = m.get('supportedGenerationMethods', [])
                if 'generateContent' in metodos and 'flash' in nome:
                    return nome, None # Achou o Flash!
            
            # 2. Se não achar, pega o PRO ou qualquer outro
            for m in dados['models']:
                if 'generateContent' in m.get('supportedGenerationMethods', []):
                    return m['name'], None
                    
        return None, "Nenhum modelo de texto encontrado nessa chave."
        
    except Exception as e:
        return None, f"Erro de conexão: {e}"

# --- FUNÇÃO 2: O ESCRITOR (Usa o modelo descoberto) ---
def chamar_gemini(prompt, chave, nome_modelo):
    # O nome_modelo já vem completo do detetive
    url = f"https://generativelanguage.googleapis.com/v1beta/{nome_modelo}:generateContent?key={chave}"
    
    headers = {"Content-Type": "application/json"}
    data = { "contents": [{ "parts": [{"text": prompt}] }] }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        if response.status_code != 200:
            return f"ERRO GOOGLE: {response.text}"
        
        resultado = response.json()
        try:
            return resultado['candidates'][0]['content']['parts'][0]['text']
        except:
            return "O Google bloqueou a resposta (Conteúdo inseguro)."
            
    except Exception as e:
        return f"ERRO CONEXÃO: {e}"

# --- FUNÇÕES PDF ---
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
        r = requests.get(url, timeout=15)
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
    
    titulo = limpar_texto(plano.get('titulo_livro', 'Título')).upper()
    pdf.multi_cell(0, 15, titulo, align="C", fill=True)
    
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
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(10)
        pdf.set_font("Helvetica", "", 12)
        pdf.multi_cell(0, 6, limpar_texto(cap['texto']))
        
    return pdf.output(dest="S").encode("latin-1")

# --- APP PRINCIPAL ---
tema = st.text_input("Tema do Livro:", placeholder="Ex: A História do Café")
paginas = st.slider("Páginas:", 10, 200, 30)

if st.button("🚀 INICIAR (AUTO-DETECT)"):
    if not api_key:
        st.error("Cole a API Key!")
    elif not tema:
        st.warning("Digite o tema.")
    else:
        status = st.status("🕵️ Detectando qual modelo sua chave aceita...", expanded=True)
        
        # 1. DETECÇÃO AUTOMÁTICA (Aqui estava o erro, agora corrigido!)
        nome_modelo, erro = detecting_modelo_disponivel(api_key) if 'detecting_modelo_disponivel' in globals() else detectar_modelo_disponivel(api_key)

        if not nome_modelo:
            status.update(label="❌ Falha na Chave", state="error")
            st.error(f"Não foi possível encontrar modelos. Detalhe: {erro}")
        else:
            status.write(f"✅ Sucesso! Vamos usar o modelo: **{nome_modelo}**")
            
            try:
                # 2. PLANEJAMENTO
                caps = int(paginas / 2.5)
                if caps < 4: caps = 4
                
                status.write(f"🧠 Planejando {caps} capítulos...")
                prompt_plan = f"""
                Crie JSON de livro sobre {tema}. {paginas} paginas.
                JSON: {{ "titulo_livro": "...", "autor_ficticio": "...", "prompt_imagem": "...", "estrutura": [ {{ "capitulo": 1, "titulo": "...", "descricao": "..." }} ] }}
                """
                
                res = chamar_gemini(prompt_plan, api_key, nome_modelo)
                
                # Limpeza JSON
                json_str = res.replace("```json", "").replace("```", "").strip()
                s = json_str.find('{')
                e = json_str.rfind('}') + 1
                plano = json.loads(json_str[s:e])
                
                st.success(f"📘 {plano['titulo_livro']}")
                
                # 3. CAPA
                status.write("🎨 Capa...")
                img = baixar_imagem(plano.get('prompt_imagem', tema))
                
                # 4. ESCRITA
                conteudo = []
                bar = status.progress(0)
                total = len(plano['estrutura'])
                
                for i, cap in enumerate(plano['estrutura']):
                    status.write(f"✍️ Cap {cap['capitulo']}/{total}: {cap['titulo']}...")
                    
                    prompt_texto = f"""
                    Escreva cap '{cap['titulo']}' do livro '{plano['titulo_livro']}'.
                    Contexto: {cap['descricao']}.
                    IMPORTANTE: Texto LONGO (1000 palavras), estilo {estilo}. Sem markdown.
                    """
                    
                    txt = chamar_gemini(prompt_texto, api_key, nome_modelo)
                    if "ERRO" in txt:
                        conteudo.append({"titulo": cap['titulo'], "texto": "[Erro]"})
                    else:
                        conteudo.append({"titulo": cap['titulo'], "texto": txt})
                    
                    bar.progress((i+1)/total)
                    
                # 5. PDF
                status.write("🖨️ PDF...")
                pdf_bytes = gerar_pdf(plano, conteudo, img)
                
                status.update(label="Pronto!", state="complete")
                st.download_button("📥 Baixar PDF", pdf_bytes, "livro_final.pdf", "application/pdf")
                
            except Exception as e:
                st.error(f"Erro: {e}")
