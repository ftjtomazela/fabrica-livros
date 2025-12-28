import streamlit as st
import json
import re
import requests
import time
import tempfile
import os
from fpdf import FPDF

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Fábrica de Livros (Com Imagens)", page_icon="🎨", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #FF4B4B; color: white; height: 3.5em; border-radius: 8px; }
    .status-box { padding: 15px; border: 1px solid #ddd; border-radius: 8px; background: #fff5f5; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("🎨 Fábrica de Livros (Edição Ilustrada)")
st.info("Este sistema gera uma capa E uma imagem ilustrativa para cada capítulo.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔑 Acesso")
    api_key = st.text_input("Sua API Key do Google:", type="password")
    st.markdown("[Criar Chave Grátis](https://aistudio.google.com/app/apikey)")
    st.divider()
    estilo = st.selectbox("Estilo do Texto:", ["Didático", "Storytelling", "Acadêmico", "Técnico"])

# --- FUNÇÃO 1: O DETETIVE (Descobre o nome do modelo) ---
def detectar_modelo_disponivel(chave):
    """Pergunta ao Google quais modelos existem para essa chave"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={chave}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None, f"Erro ao listar modelos: {response.text}"
            
        dados = response.json()
        
        if 'models' in dados:
            # 1. Tenta achar o FLASH (mais rápido)
            for m in dados['models']:
                nome = m['name'] 
                metodos = m.get('supportedGenerationMethods', [])
                if 'generateContent' in metodos and 'flash' in nome:
                    return nome, None # Achou o Flash!
            
            # 2. Se não achar, pega qualquer um que gere texto
            for m in dados['models']:
                if 'generateContent' in m.get('supportedGenerationMethods', []):
                    return m['name'], None
                    
        return None, "Nenhum modelo de texto encontrado nessa chave."
        
    except Exception as e:
        return None, f"Erro de conexão: {e}"

# --- FUNÇÃO 2: O ESCRITOR (Usa o modelo descoberto) ---
def chamar_gemini(prompt, chave, nome_modelo):
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

# --- FUNÇÕES PDF E IMAGEM ---
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
    # Usa Pollinations, adiciona 'seed' para variar as imagens
    seed = int(time.time() * 1000) % 1000
    url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=768&nologo=true&seed={seed}"
    try:
        r = requests.get(url, timeout=15)
        return r.content if r.status_code == 200 else None
    except: return None

# --- FUNÇÃO DE DIAGRAMAÇÃO (ATUALIZADA PARA IMAGENS INTERNAS) ---
def gerar_pdf(plano, conteudo, img_capa_bytes):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    # --- 1. CAPA ---
    pdf.add_page()
    if img_capa_bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(img_capa_bytes)
            path_capa = f.name
        try: pdf.image(path_capa, x=0, y=0, w=210, h=297)
        except: pass
        try: os.remove(path_capa)
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
    
    # --- 2. CONTEÚDO DOS CAPÍTULOS ---
    for cap in conteudo:
        pdf.add_page()
        
        # Título do Capítulo
        pdf.set_text_color(0,0,0)
        pdf.set_font("Helvetica", "B", 22)
        pdf.multi_cell(0, 10, limpar_texto(cap['titulo']))
        pdf.ln(5)
        
        # --- INSERIR IMAGEM DO CAPÍTULO AQUI ---
        img_chap_bytes = cap.get('imagem_bytes')
        if img_chap_bytes:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
                    f.write(img_chap_bytes)
                    path_chap = f.name
                # Centraliza a imagem (largura 150mm)
                # Pagina A4 = 210mm. Margem esquerda = (210-150)/2 = 30.
                pdf.image(path_chap, x=30, w=150) 
                pdf.ln(10) # Espaço após a imagem
            except: pass
            finally:
                try: os.remove(path_chap)
                except: pass
        # ---------------------------------------
        
        # Texto do Capítulo
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(10)
        pdf.set_font("Helvetica", "", 12)
        pdf.multi_cell(0, 6, limpar_texto(cap['texto']))
        
    return pdf.output(dest="S").encode("latin-1")

# --- APP PRINCIPAL ---
tema = st.text_input("Tema do Livro:", placeholder="Ex: Mitologia Nórdica")
paginas = st.slider("Páginas:", 10, 200, 30)

if st.button("🚀 INICIAR (COM IMAGENS)"):
    if not api_key:
        st.error("Cole a API Key!")
    elif not tema:
        st.warning("Digite o tema.")
    else:
        status = st.status("🕵️ Detectando modelo do Google...", expanded=True)
        
        # 1. DETECÇÃO
        nome_modelo, erro = detectar_modelo_disponivel(api_key)

        if not nome_modelo:
            status.update(label="❌ Falha na Chave", state="error")
            st.error(f"Erro: {erro}")
        else:
            status.write(f"✅ Usando modelo: **{nome_modelo}**")
            
            try:
                # 2. PLANEJAMENTO (Agora pedindo prompts para capítulos também)
                caps = int(paginas / 2.5)
                if caps < 4: caps = 4
                
                status.write(f"🧠 Planejando {caps} capítulos ilustrados...")
                prompt_plan = f"""
                Crie JSON de livro sobre {tema}. {paginas} paginas.
                O JSON deve incluir prompts visuais para a capa E para cada capítulo.
                JSON OBRIGATÓRIO:
                {{
                    "titulo_livro": "...",
                    "autor_ficticio": "...",
                    "prompt_imagem_capa": "Descrição visual da capa...",
                    "estrutura": [
                        {{
                            "capitulo": 1,
                            "titulo": "...",
                            "descricao": "...",
                            "prompt_imagem_capitulo": "Descrição visual para uma imagem que ilustre este capítulo..."
                        }}
                    ]
                }}
                """
                
                res = chamar_gemini(prompt_plan, api_key, nome_modelo)
                
                json_str = res.replace("```json", "").replace("```", "").strip()
                s = json_str.find('{')
                e = json_str.rfind('}') + 1
                plano = json.loads(json_str[s:e])
                
                st.success(f"📘 {plano['titulo_livro']}")
                
                # 3. GERAR CAPA
                status.write("🎨 Pintando a capa...")
                img_capa = baixar_imagem(plano.get('prompt_imagem_capa', tema))
                
                # 4. LOOP DE ESCRITA + GERAÇÃO DE IMAGENS INTERNAS
                conteudo_final = []
                bar = status.progress(0)
                total = len(plano['estrutura'])
                
                for i, cap in enumerate(plano['estrutura']):
                    status.write(f"✍️ Cap {cap['capitulo']}/{total}: {cap['titulo']}...")
                    
                    # 4a. Gera Texto
                    prompt_texto = f"""
                    Escreva cap '{cap['titulo']}' do livro '{plano['titulo_livro']}'.
                    Contexto: {cap['descricao']}.
                    IMPORTANTE: Texto LONGO (1000 palavras), estilo {estilo}. Sem markdown.
                    """
                    txt = chamar_gemini(prompt_texto, api_key, nome_modelo)
                    
                    # 4b. Gera Imagem do Capítulo (Em paralelo com a escrita)
                    status.write(f"🖼️ Gerando ilustração para o Cap {cap['capitulo']}...")
                    prompt_img_cap = cap.get('prompt_imagem_capitulo', f"Image about {cap['titulo']}")
                    img_chap_bytes = baixar_imagem(prompt_img_cap)

                    # Salva tudo (texto e imagem)
                    if "ERRO" in txt:
                        conteudo_final.append({"titulo": cap['titulo'], "texto": "[Erro]", "imagem_bytes": None})
                    else:
                        conteudo_final.append({"titulo": cap['titulo'], "texto": txt, "imagem_bytes": img_chap_bytes})
                    
                    bar.progress((i+1)/total)
                    # Pausa para não sobrecarregar a API de imagem gratuita
                    time.sleep(1) 
                    
                # 5. PDF
                status.write("🖨️ Diagramando PDF ilustrado...")
                pdf_bytes = gerar_pdf(plano, conteudo_final, img_capa)
                
                status.update(label="Livro Ilustrado Pronto!", state="complete")
                st.download_button("📥 Baixar PDF", pdf_bytes, "livro_ilustrado.pdf", "application/pdf")
                
            except Exception as e:
                st.error(f"Erro: {e}")
                st.warning("Se o erro for de JSON, tente gerar novamente.")
