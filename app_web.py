import streamlit as st
from openai import OpenAI
import json
import re
import requests
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Editora IA Pro", page_icon="📚", layout="wide")

# --- CSS PARA DEIXAR O APP BONITO ---
st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #FF4B4B; color: white; height: 3em; }
    .status-box { padding: 10px; border-radius: 5px; border: 1px solid #ddd; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("📚 Editora IA Pro: Livros de Alta Densidade")
st.markdown("Crie livros **extensos**, com **capa gerada por IA** e diagramação profissional.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("Sua API Key (Groq):", type="password")
    st.info("Obtenha em: console.groq.com")
    st.divider()
    estilo_texto = st.selectbox("Estilo de Escrita:", 
        ["Didático e Simples", "Acadêmico e Denso", "Storytelling Emocionante", "Técnico e Direto"])

# --- CLASSE PDF AVANÇADA (COM RODAPÉ) ---
class PDF(FPDF):
    def footer(self):
        # Posiciona a 1.5cm do fim da página
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128)
        # Imprime número da página centralizado
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def limpar_texto(texto):
    # Limpa caracteres que quebram o PDF, mantendo acentos
    if not texto: return ""
    return re.sub(r'[^\x00-\x7FáéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ0-9.,:;?!()"\'-]', '', texto)

def baixar_imagem_capa(prompt_imagem):
    """
    Gera uma imagem via Pollinations.ai (Grátis, sem API Key)
    """
    prompt_formatado = prompt_imagem.replace(" ", "%20")
    url = f"https://image.pollinations.ai/prompt/{prompt_formatado}?width=1080&height=1420&nologo=true"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return BytesIO(response.content)
    except:
        return None
    return None

def gerar_pdf_pro(plano, conteudo_completo, imagem_capa_bytes):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    # --- 1. CAPA VISUAL ---
    pdf.add_page()
    
    # Se tiver imagem, coloca ela ocupando quase toda a página
    if imagem_capa_bytes:
        pdf.image(imagem_capa_bytes, x=0, y=0, w=210, h=297) # A4 Full size background
        
    # Título sobreposto (Fundo branco semi-transparente simulado ou caixa de texto)
    pdf.set_y(150)
    pdf.set_font("Helvetica", "B", 36)
    pdf.set_text_color(255, 255, 255) # Texto Branco
    # Sombra preta para leitura
    with pdf.local_context(fill_opacity=0.5):
        pdf.set_fill_color(0, 0, 0)
        pdf.cell(0, 20, "", ln=1, fill=True) 
        
    pdf.set_y(150)
    pdf.multi_cell(0, 15, limpar_texto(plano['titulo_livro']).upper(), align="C")
    
    pdf.set_y(260)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Autor: {limpar_texto(plano['autor_ficticio'])}", align="C")

    # --- 2. SUMÁRIO ---
    pdf.add_page()
    pdf.set_text_color(0, 0, 0) # Volta para preto
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 20, "SUMÁRIO", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Helvetica", "", 12)
    for cap in plano['estrutura']:
        titulo_limpo = limpar_texto(cap['titulo'])
        pdf.cell(0, 10, f"{cap['capitulo']}. {titulo_limpo}", ln=True)
        # Se tiver subtópicos, lista eles (opcional, simplificado aqui)

    # --- 3. CONTEÚDO (O GROSSO DO LIVRO) ---
    for capitulo in conteudo_completo:
        pdf.add_page()
        
        # Título do Capítulo Estilizado
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(44, 62, 80) # Azul escuro
        pdf.multi_cell(0, 15, limpar_texto(capitulo['titulo']))
        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y()) # Linha separadora
        pdf.ln(10)
        
        # Texto do Capítulo
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(0, 0, 0)
        
        # Tratamento simples de markdown para PDF
        texto_bruto = capitulo['texto']
        paragrafos = texto_bruto.split('\n')
        
        for p in paragrafos:
            p = limpar_texto(p)
            if not p.strip():
                continue
            
            if p.startswith('#'): # Subtitulos
                pdf.ln(5)
                pdf.set_font("Helvetica", "B", 14)
                pdf.set_text_color(230, 126, 34) # Laranja
                pdf.multi_cell(0, 10, p.replace('#', '').strip())
                pdf.set_font("Helvetica", "", 12)
                pdf.set_text_color(0, 0, 0)
            else:
                pdf.multi_cell(0, 7, p)
                pdf.ln(3)

    return pdf.output(dest="S").encode("latin-1") # Retorna bytes para download

# --- LÓGICA PRINCIPAL ---
tema = st.text_input("Sobre o que é o livro?", placeholder="Ex: Guia Completo de Investimentos")
col1, col2 = st.columns(2)
with col1:
    # Aumentei o limite para 200, mas atenção ao tempo de processamento!
    paginas_alvo = st.slider("Meta de Páginas (Aprox):", 10, 200, 30)
with col2:
    densidade = st.slider("Densidade do Conteúdo (Detalhe):", 1, 5, 3, help="5 = Capítulos muito longos e detalhados")

if st.button("🚀 INICIAR PRODUÇÃO DO LIVRO"):
    if not api_key or not tema:
        st.error("Preencha a API Key e o Tema!")
    else:
        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        status = st.status("🏗️ Iniciando a engenharia do livro...", expanded=True)
        
        try:
            # 1. PLANEJAMENTO EXPANDIDO (O Segredo das 200 páginas)
            # Para ter muitas páginas, precisamos de MUITOS capítulos.
            num_capitulos = int(paginas_alvo / 3) # Média de 3 páginas por capítulo
            if num_capitulos < 5: num_capitulos = 5
            
            status.write(f"🧠 Planejando estrutura para {num_capitulos} capítulos...")
            
            prompt_plan = f"""
            Crie a estrutura de um livro EXTREMAMENTE COMPLETO sobre: {tema}.
            O usuário quer um livro de {paginas_alvo} páginas.
            Para isso, preciso de EXATAMENTE {num_capitulos} capítulos no JSON.
            
            Estilo desejado: {estilo_texto}.
            Inclua também um 'prompt_imagem_capa' (em inglês) descrevendo uma capa épica para este livro.
            
            Retorne JSON puro com: 'titulo_livro', 'subtitulo', 'autor_ficticio', 'prompt_imagem_capa' e lista 'estrutura' (capitulo, titulo, descricao_detalhada).
            """
            
            res_plan = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt_plan}],
                temperature=0.7
            )
            
            texto_json = res_plan.choices[0].message.content.replace("```json","").replace("```","")
            plano = json.loads(texto_json)
            st.success(f"📖 Título Definido: {plano['titulo_livro']}")
            
            # 2. GERAÇÃO DA CAPA (Pollinations)
            status.write("🎨 Pintando a capa do livro com IA...")
            img_bytes = baixar_imagem_capa(plano.get('prompt_imagem_capa', f"Cover for book about {tema}"))
            if img_bytes:
                st.image(img_bytes, caption="Capa Gerada", width=200)
            
            # 3. ESCRITA EM LOOP (Com Densidade)
            conteudo_completo = []
            barra = status.progress(0)
            
            total = len(plano['estrutura'])
            
            for i, cap in enumerate(plano['estrutura']):
                status.write(f"✍️ Escrevendo Cap {cap['capitulo']}/{total}: {cap['titulo']}...")
                
                # Prompt para TEXTÃO
                prompt_write = f"""
                Escreva o CAPÍTULO {cap['capitulo']} do livro '{plano['titulo_livro']}'.
                Título do Capítulo: {cap['titulo']}
                O que abordar: {cap['descricao_detalhada']}
                
                REGRAS DE OURO PARA TEXTO LONGO E BONITO:
                1. Escreva um texto LONGO, profundo e detalhado (Mínimo 1000 palavras).
                2. Use subtítulos (iniciados com #) para quebrar o texto.
                3. Use listas com marcadores para exemplos.
                4. Estilo: {estilo_texto}.
                5. Não faça introduções curtas, aprofunde-se no tema.
                
                Retorne apenas o texto do corpo do capítulo.
                """
                
                try:
                    res_text = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": prompt_write}]
                    )
                    texto_cap = res_text.choices[0].message.content
                    conteudo_completo.append({"titulo": cap['titulo'], "texto": texto_cap})
                except Exception as e:
                    st.warning(f"Erro no cap {i}: {e}")
                
                barra.progress((i + 1) / total)

            # 4. DIAGRAMAÇÃO FINAL
            status.write("🖨️ Diagramando PDF com capa e rodapés...")
            pdf_bytes = gerar_pdf_pro(plano, conteudo_completo, img_bytes)
            
            status.update(label="✅ Livro Pronto!", state="complete", expanded=False)
            
            st.balloons()
            st.download_button(
                label=f"📥 BAIXAR LIVRO COMPLETO ({len(conteudo_completo)} Capítulos)",
                data=pdf_bytes,
                file_name=f"{limpar_texto(plano['titulo_livro'])}.pdf",
                mime="application/pdf"
            )

        except Exception as e:
            st.error(f"Erro fatal: {e}")