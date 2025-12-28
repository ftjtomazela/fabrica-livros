import streamlit as st
import json
import re
import requests
import time
import tempfile
import os
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Fábrica de Livros (Direct)", page_icon="🌐", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #7d5fff; color: white; height: 3.5em; border-radius: 8px; }
    .status-box { padding: 15px; border: 1px solid #ddd; border-radius: 8px; background: #f3f0ff; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("🌐 Fábrica de Livros (Conexão Direta)")
st.info("Sistema operando em modo HTTP Direto (Sem erros de biblioteca).")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔑 Acesso")
    api_key = st.text_input("Sua API Key do Google:", type="password")
    st.markdown("[Criar Chave Grátis](https://aistudio.google.com/app/apikey)")
    st.divider()
    estilo = st.selectbox("Estilo do Texto:", 
        ["Didático e Simples", "Storytelling (História)", "Acadêmico", "Técnico e Direto"])

# --- FUNÇÃO DE CONEXÃO DIRETA (O SEGREDO) ---
def chamar_gemini(prompt, chave):
    """Envia o pedido direto para o Google via HTTP, ignorando bibliotecas com erro."""
    # Usa o modelo Gemini 1.5 Flash que é rápido e gratuito
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={chave}"
    
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        # Timeout de 60 segundos para garantir que textos longos não cortem
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        # Se o Google devolver erro (ex: chave inválida)
        if response.status_code != 200:
            return f"ERRO GOOGLE ({response.status_code}): {response.text}"
            
        resultado = response.json()
        
        # Tenta extrair o texto da resposta complexa do Google
        try:
            texto_retornado = resultado['candidates'][0]['content']['parts'][0]['text']
            return texto_retornado
        except KeyError:
            return "ERRO: O Google bloqueou a resposta (Conteúdo inseguro ou erro interno)."
            
    except Exception as e:
        return f"ERRO DE CONEXÃO: {e}"

# --- FUNÇÕES AUXILIARES ---
class PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')

def limpar_texto(texto):
    if not texto: return ""
    # Remove formatações Markdown (**negrito**, ## titulos)
    texto = texto.replace("**", "").replace("*", "").replace("##", "").replace("#", "")
    # Remove caracteres estranhos que quebram o PDF
    return re.sub(r'[^\x00-\x7FáéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ0-9.,:;?!()"\'-]', '', texto)

def baixar_imagem(prompt):
    # Gera imagem sem precisar de chave (Pollinations)
    prompt_safe = prompt.replace(' ', '%20')
    url = f"https://image.pollinations.ai/prompt/{prompt_safe}?width=1080&height=1420&nologo=true&seed=123"
    try:
        r = requests.get(url, timeout=15)
        return r.content if r.status_code == 200 else None
    except: return None

def gerar_pdf(plano, conteudo, img_bytes):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    # --- CAPA ---
    pdf.add_page()
    if img_bytes:
        # Salva imagem temporária para o PDF ler
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(img_bytes)
            path = f.name
        try: 
            pdf.image(path, x=0, y=0, w=210, h=297)
        except: pass
        try: os.remove(path)
        except: pass

    # Título na Capa
    pdf.set_y(150)
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_fill_color(0,0,0) # Fundo preto
    pdf.set_text_color(255,255,255) # Texto branco
    
    titulo = limpar_texto(plano.get('titulo_livro', 'Título')).upper()
    pdf.multi_cell(0, 15, titulo, align="C", fill=True)
    
    pdf.set_y(260)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Autor IA: {limpar_texto(plano.get('autor_ficticio', 'IA'))}", align="C", fill=True)
    
    # --- CONTEÚDO ---
    for cap in conteudo:
        pdf.add_page()
        
        # Título do Capítulo
        pdf.set_text_color(0,0,0)
        pdf.set_font("Helvetica", "B", 22)
        pdf.multi_cell(0, 10, limpar_texto(cap['titulo']))
        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(10)
        
        # Texto do Capítulo
        pdf.set_font("Helvetica", "", 12)
        
        # Se deu erro no texto, avisa
        texto_cap = cap['texto']
        if "ERRO" in texto_cap:
            pdf.set_text_color(255, 0, 0) # Vermelho
            pdf.multi_cell(0, 6, "Erro ao gerar este capítulo. Verifique a chave API.")
        else:
            pdf.set_text_color(0, 0, 0) # Preto
            pdf.multi_cell(0, 6, limpar_texto(texto_cap))
        
    return pdf.output(dest="S").encode("latin-1")

# --- APLICAÇÃO PRINCIPAL ---
tema = st.text_input("Sobre o que é o livro?", placeholder="Ex: História do Império Romano")
paginas = st.slider("Meta aproximada de páginas:", 10, 200, 30)

if st.button("🚀 INICIAR PRODUÇÃO"):
    if not api_key:
        st.error("⚠️ Cole sua API Key na barra lateral antes de começar!")
    elif not tema:
        st.warning("⚠️ Digite um tema para o livro.")
    else:
        # TESTE DE CONEXÃO INICIAL
        teste = chamar_gemini("Diga apenas a palavra 'Olá'", api_key)
        
        if "ERRO" in teste:
            st.error(f"❌ A chave API não funcionou. O Google respondeu: {teste}")
        else:
            status = st.status("✅ Conexão estabelecida! Iniciando...", expanded=True)
            
            try:
                # 1. PLANEJAMENTO
                caps_alvo = int(paginas / 2.5) # Define qtd de capitulos baseado nas páginas
                if caps_alvo < 4: caps_alvo = 4
                
                status.write(f"🧠 Planejando arquitetura para {caps_alvo} capítulos...")
                
                prompt_plan = f"""
                Você é um Editor Chefe. Crie um plano para um livro sobre: {tema}.
                Meta de tamanho: {paginas} páginas.
                Preciso de EXATAMENTE {caps_alvo} capítulos.
                
                Responda APENAS com este JSON válido (sem markdown, sem explicações):
                {{
                    "titulo_livro": "...",
                    "autor_ficticio": "...",
                    "prompt_imagem": "Descrição visual da capa em inglês...",
                    "estrutura": [
                        {{ "capitulo": 1, "titulo": "...", "descricao": "..." }}
                    ]
                }}
                """
                
                res_txt = chamar_gemini(prompt_plan, api_key)
                
                # Limpeza cirúrgica do JSON
                # O Google as vezes manda ```json no começo. Vamos limpar.
                json_str = res_txt.replace("```json", "").replace("```", "").strip()
                # Garante que pega só o objeto JSON {}
                inicio = json_str.find('{')
                fim = json_str.rfind('}') + 1
                plano = json.loads(json_str[inicio:fim])
                
                st.success(f"📘 Título Definido: {plano['titulo_livro']}")
                
                # 2. CAPA
                status.write("🎨 Pintando a capa do livro...")
                img_bytes = baixar_imagem(plano.get('prompt_imagem', tema))
                
                # 3. ESCRITA DOS CAPÍTULOS
                conteudo = []
                barra_progresso = status.progress(0)
                total_caps = len(plano['estrutura'])
                
                for i, cap in enumerate(plano['estrutura']):
                    status.write(f"✍️ Escrevendo Cap {cap['capitulo']}/{total_caps}: {cap['titulo']}...")
                    
                    prompt_cap = f"""
                    Escreva o CAPÍTULO {cap['capitulo']} do livro '{plano['titulo_livro']}'.
                    Título: '{cap['titulo']}'
                    O que deve ter: {cap['descricao']}.
                    
                    REGRAS OBRIGATÓRIAS:
                    1. Escreva um texto LONGO (mínimo 1000 palavras).
                    2. Use o estilo: {estilo}.
                    3. Seja muito detalhado e profundo.
                    4. NÃO use formatação Markdown (como ** ou ##), use apenas texto corrido e parágrafos.
                    """
                    
                    texto_gerado = chamar_gemini(prompt_cap, api_key)
                    
                    if "ERRO" in texto_gerado:
                        conteudo.append({"titulo": cap['titulo'], "texto": "[Erro de conexão neste capítulo]"})
                        time.sleep(2) # Pausa para recuperar fôlego
                    else:
                        conteudo.append({"titulo": cap['titulo'], "texto": texto_gerado})
                    
                    # Atualiza barra
                    barra_progresso.progress((i + 1) / total_caps)
                    
                # 4. DIAGRAMAÇÃO
                status.write("🖨️ Imprimindo arquivo PDF final...")
                pdf_bytes = gerar_pdf(plano, conteudo, img_bytes)
                
                status.update(label="✅ Livro Concluído com Sucesso!", state="complete", expanded=False)
                st.balloons()
                
                st.download_button(
                    label="📥 CLIQUE AQUI PARA BAIXAR SEU LIVRO",
                    data=pdf_bytes,
                    file_name="Meu_Livro_Completo.pdf",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"Ocorreu um erro inesperado: {e}")
                st.error("Dica: Verifique se o JSON gerado pelo Google veio correto.")
