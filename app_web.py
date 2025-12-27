import streamlit as st
import google.generativeai as genai
import json
import re
import requests
import time
import tempfile
import os
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Editora IA Gemini", page_icon="📚", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #4B90FF; color: white; height: 3em; }
    .status-box { padding: 10px; border-radius: 5px; border: 1px solid #ddd; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("📚 Fábrica de Livros (Motor Gemini)")
st.info("Otimizado para livros longos (até 200+ páginas) sem erros de limite.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("Google API Key:", type="password")
    st.markdown("[Pegar Chave Grátis Aqui](https://aistudio.google.com/app/apikey)")
    st.divider()
    estilo_texto = st.selectbox("Estilo de Escrita:", 
        ["Didático e Simples", "Acadêmico e Denso", "Storytelling", "Técnico Profissional"])

# --- CLASSE PDF ---
class PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def limpar_texto(texto):
    if not texto: return ""
    # Remove formatações Markdown que atrapalham o PDF
    texto = texto.replace("**", "").replace("*", "").replace("##", "").replace("#", "")
    return re.sub(r'[^\x00-\x7FáéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ0-9.,:;?!()"\'-]', '', texto)

def baixar_imagem_capa(prompt_imagem):
    prompt_formatado = prompt_imagem.replace(" ", "%20")
    # Usa Pollinations para gerar imagem
    url = f"https://image.pollinations.ai/prompt/{prompt_formatado}?width=1080&height=1420&nologo=true&seed=42"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.content # Retorna bytes puros
    except:
        return None
    return None

def gerar_pdf_final(plano, conteudo_completo, imagem_bytes):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    # --- 1. CAPA (TÉCNICA DO ARQUIVO TEMPORÁRIO) ---
    # Isso corrige o erro '_io.BytesIO object has no attribute rfind'
    pdf.add_page()
    
    if imagem_bytes:
        # Salva imagem num arquivo temporário real para o FPDF conseguir ler
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            tmp_file.write(imagem_bytes)
            tmp_path = tmp_file.name
        
        try:
            pdf.image(tmp_path, x=0, y=0, w=210, h=297)
        except:
            pass # Se falhar a imagem, segue sem ela
        
        # Remove o arquivo temporário depois de usar
        try:
            os.remove(tmp_path)
        except:
            pass

    # Título na Capa
    pdf.set_y(140)
    pdf.set_font("Helvetica", "B", 30)
    # Caixa semi-transparente simulada (preto fundo)
    pdf.set_fill_color(0, 0, 0) 
    pdf.set_text_color(255, 255, 255)
    
    titulo = limpar_texto(plano['titulo_livro']).upper()
    pdf.multi_cell(0, 15, titulo, align="C", fill=True)
    
    pdf.set_y(260)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Autor IA: {limpar_texto(plano['autor_ficticio'])}", align="C", fill=True)

    # --- 2. SUMÁRIO ---
    pdf.add_page()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 20, "SUMÁRIO", ln=True, align='C')
    
    pdf.set_font("Helvetica", "", 12)
    for cap in plano['estrutura']:
        pdf.cell(0, 10, f"{cap['capitulo']}. {limpar_texto(cap['titulo'])}", ln=True)

    # --- 3. CONTEÚDO ---
    for capitulo in conteudo_completo:
        pdf.add_page()
        
        # Título do Capítulo
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(0, 51, 102) # Azul Marinho
        pdf.multi_cell(0, 12, limpar_texto(capitulo['titulo']))
        pdf.ln(5)
        
        # Linha divisória
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(10)
        
        # Corpo do texto
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(0, 0, 0)
        
        texto_limpo = limpar_texto(capitulo['texto'])
        pdf.multi_cell(0, 6, texto_limpo)
        
    return pdf.output(dest="S").encode("latin-1")

# --- LÓGICA PRINCIPAL ---
tema = st.text_input("Tema do Livro:", placeholder="Ex: História da Roma Antiga")
col1, col2 = st.columns(2)
with col1:
    paginas_alvo = st.slider("Meta de Páginas:", 10, 200, 50)
with col2:
    densidade = st.slider("Profundidade (1-5):", 1, 5, 4)

if st.button("🚀 INICIAR FÁBRICA (GEMINI)"):
    if not api_key:
        st.error("Coloque a chave do Google Gemini na lateral!")
    elif not tema:
        st.warning("Digite um tema.")
    else:
        # Configura Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        status = st.status("🏗️ Iniciando os motores do Gemini...", expanded=True)
        
        try:
            # 1. PLANEJAMENTO
            num_capitulos = int(paginas_alvo / 2.5) # Ajuste para gerar volume
            if num_capitulos < 5: num_capitulos = 5
            
            status.write(f"🧠 Criando arquitetura para {num_capitulos} capítulos...")
            
            prompt_plan = f"""
            Aja como um Editor Chefe. Crie a estrutura de um livro sobre: {tema}.
            O livro deve ser LONGO, com meta de {paginas_alvo} páginas.
            Crie EXATAMENTE {num_capitulos} capítulos.
            
            Retorne APENAS UM JSON (sem markdown) com:
            - 'titulo_livro'
            - 'subtitulo'
            - 'autor_ficticio'
            - 'prompt_imagem_capa' (Descrição visual em inglês para a capa)
            - 'estrutura': lista de objetos com 'capitulo' (numero), 'titulo', 'descricao'.
            """
            
            res_plan = model.generate_content(prompt_plan)
            texto_json = res_plan.text.replace("```json", "").replace("```", "").strip()
            plano = json.loads(texto_json)
            
            st.success(f"📘 Título: {plano['titulo_livro']}")
            
            # 2. CAPA
            status.write("🎨 Gerando capa com IA...")
            img_bytes = baixar_imagem_capa(plano.get('prompt_imagem_capa', f"Book cover about {tema}"))
            if img_bytes:
                st.image(img_bytes, caption="Capa Gerada", width=150)
            
            # 3. ESCRITA (Aqui o Gemini brilha)
            conteudo = []
            barra = status.progress(0)
            total_caps = len(plano['estrutura'])
            
            for i, cap in enumerate(plano['estrutura']):
                status.write(f"✍️ Escrevendo Cap {cap['capitulo']}/{total_caps}: {cap['titulo']}...")
                
                prompt_text = f"""
                Escreva o CAPÍTULO {cap['capitulo']} do livro '{plano['titulo_livro']}'.
                Título: {cap['titulo']}
                Contexto: {cap['descricao']}
                
                REGRAS:
                1. Escreva um texto MUITO DETALHADO, didático e longo (mínimo 800 palavras).
                2. Use subtítulos para organizar.
                3. Estilo: {estilo_texto}.
                4. Não use Markdown complexo, apenas texto corrido e parágrafos.
                """
                
                try:
                    res_text = model.generate_content(prompt_text)
                    conteudo.append({"titulo": cap['titulo'], "texto": res_text.text})
                except Exception as e:
                    st.error(f"Erro no cap {i}: {e}")
                    # Tenta esperar um pouco se der erro de velocidade, mas Gemini é rápido
                    time.sleep(2) 
                
                barra.progress((i + 1) / total_caps)
                time.sleep(1) # Pausa de segurança de 1s entre capítulos

            # 4. PDF
            status.write("🖨️ Imprimindo PDF final...")
            pdf_bytes = gerar_pdf_final(plano, conteudo, img_bytes)
            
            status.update(label="✅ Livro Concluído!", state="complete", expanded=False)
            st.balloons()
            
            st.download_button(
                label=f"📥 BAIXAR LIVRO ({total_caps} Capítulos)",
                data=pdf_bytes,
                file_name=f"Livro_Gemini_{limpar_texto(tema)[:20]}.pdf",
                mime="application/pdf"
            )

        except Exception as e:
            st.error(f"Erro Fatal: {e}")