import streamlit as st
import json
import re
import requests
import time
import tempfile
import os
from fpdf import FPDF

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Fábrica de Livros (Modo Web)", page_icon="🌐", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #7d5fff; color: white; height: 3.5em; border-radius: 8px; }
    .status-box { padding: 15px; border: 1px solid #ddd; border-radius: 8px; background: #f3f0ff; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("🌐 Fábrica de Livros (Conexão Direta)")
st.caption("Este sistema ignora bibliotecas e conecta direto no servidor do Google.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔑 Acesso")
    api_key = st.text_input("Sua API Key do Google:", type="password")
    st.markdown("[Criar Chave](https://aistudio.google.com/app/apikey)")
    st.divider()
    estilo = st.selectbox("Estilo:", ["Didático", "Storytelling", "Acadêmico", "Técnico"])

# --- FUNÇÃO MÁGICA (CONEXÃO DIRETA) ---
def chamar_gemini(prompt, chave):
    """Manda mensagem pro Google sem usar biblioteca"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={chave}"
    
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code != 200:
            return f"ERRO: {response.text}"
            
        resultado = response.json()
        try:
            return resultado['candidates'][0]['content']['parts'][0]['text']
        except:
            return "Erro ao ler resposta do Google."
            
    except Exception as e:
        return f"Erro de conexão: {e}"

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
    
    titulo = limpar_texto(plano.get('titulo_livro', 'Título')).upper()
    pdf.multi_cell(0, 15, titulo, align="C", fill=True)
    
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

# --- APP ---
tema = st.text_input("Tema do Livro:")
paginas = st.slider("Meta de Páginas:", 10, 200, 30)

if st.button("🚀 INICIAR (MODO DIRETO)"):
    if not api_key:
        st.error("Cole a API Key!")
    elif not tema:
        st.warning("Digite o tema.")
    else:
        # Teste Rápido da Chave
        teste = chamar_gemini("Diga OI", api_key)
        
        if "ERRO" in teste:
            st.error(f"❌ A Chave foi rejeitada pelo Google. Detalhes: {teste}")
            st.info("Dica: Verifique se copiou a chave inteira, sem espaços no final.")
        else:
            status = st.status("✅ Chave Aceita! Conectado.", expanded=True)
            
            try:
                # 1. Planejamento
                caps = int(paginas / 2.5)
                if caps < 4: caps = 4
                status.write(f"🧠 Planejando {caps} capítulos...")
                
                prompt_plan = f"""
                Crie estrutura JSON para livro sobre {tema}. {paginas} paginas.
                JSON OBRIGATORIO:
                {{ "titulo_livro": "...", "autor_ficticio": "...", "prompt_imagem": "...", 
                   "estrutura": [ {{ "capitulo": 1, "titulo": "...", "descricao": "..." }} ] }}
                """
                
                res_txt = chamar_gemini(prompt_plan, api_key)
                # Limpeza bruta do JSON
                json_str = res_txt.replace("```json", "").replace("```", "").strip()
                # Às vezes o google coloca texto antes, pega só o { ... }
                start = json_str.find('{')
                end = json_str.rfind('}') + 1
                plano = json.loads(json_str[start:end])
                
                st.success(f"📘 {plano['titulo_livro']}")
                
                # 2. Capa
                status.write("🎨 Gerando capa...")
                img = baixar_imagem(plano.get('prompt_imagem', tema))
                
                # 3. Escrita
                conteudo = []
                bar = status.progress(0)
                total = len(plano['estrutura'])
                
                for i, cap in enumerate(plano['estrutura']):
                    status.write(f"✍️ Cap {cap['capitulo']}/{total}: {cap['titulo']}...")
                    
                    prompt_texto = f"""
                    Escreva o capitulo '{cap['titulo']}' do livro '{plano['titulo_livro']}'.
                    Contexto: {cap['descricao']}.
                    IMPORTANTE: Texto LONGO (1000 palavras), estilo {estilo}. Sem markdown.
                    """
                    
                    txt = chamar_gemini(prompt_texto, api_key)
                    
                    if "ERRO" in txt:
                        conteudo.append({"titulo": cap['titulo'], "texto": "[Erro na conexão]"})
                    else:
                        conteudo.append({"titulo": cap['titulo'], "texto": txt})
                    
                    bar.progress((i+1)/total)
                    
                # 4. PDF
                status.write("🖨️ Gerando PDF...")
                pdf_bytes = gerar_pdf(plano, conteudo, img)
                
                status.update(label="Pronto!", state="complete")
                st.download_button("📥 Baixar PDF", pdf_bytes, "livro_final.pdf", "application/pdf")
                
            except Exception as e:
                st.error(f"Erro no processamento: {e}")
