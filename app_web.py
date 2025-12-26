import streamlit as st
from openai import OpenAI
import json
import os
import time
import markdown
from xhtml2pdf import pisa
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerador de Livros IA", page_icon="📚")

st.title("📚 Fábrica de Livros com IA")
st.write("Crie livros completos em PDF direto pelo celular.")

# --- BARRA LATERAL (Configurações) ---
with st.sidebar:
    st.header("Configurações")
    api_key = st.text_input("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", type="password")
    st.info("Pegue sua chave em: console.groq.com")

# --- FUNÇÕES DE BASTIDORES ---
def limpar_texto(texto):
    return re.sub(r'[^\w\s,.?!:;\-\(\)áéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ0-9"\'/]', '', texto)

def gerar_pdf_final(plano, conteudo_md):
    # 1. HTML DA CAPA
    html_capa = f"""
    <div class="capa">
        <div class="titulo-principal">{plano['titulo_livro']}</div>
        <div class="subtitulo">{plano['subtitulo']}</div>
        <div class="divisor"></div>
        <div class="autor">Autor: {plano['autor_ficticio']}</div>
    </div>
    <pdf:nextpage />
    """
    
    # 2. HTML DO CONTEÚDO
    html_texto = markdown.markdown(limpar_texto(conteudo_md))
    
    # 3. CSS
    css = """
    <style>
        @page { size: A4; margin: 2cm; }
        body { font-family: Helvetica, sans-serif; }
        .capa { text-align: center; padding-top: 200px; }
        .titulo-principal { font-size: 35pt; font-weight: bold; color: #2c3e50; }
        .subtitulo { font-size: 18pt; color: #7f8c8d; margin-top: 10px; }
        .divisor { width: 50px; height: 5px; background: #e74c3c; margin: 30px auto; }
        h1 { color: #2980b9; page-break-before: always; border-bottom: 1px solid #ddd; }
        p { text-align: justify; line-height: 1.5; }
    </style>
    """
    
    html_final = f"<html><head><meta charset='utf-8'>{css}</head><body>{html_capa}{html_texto}</body></html>"
    
    # Gera PDF em memória
    output_filename = "Livro_Gerado.pdf"
    with open(output_filename, "wb") as f:
        pisa.CreatePDF(html_final, dest=f)
    return output_filename

# --- INTERFACE PRINCIPAL ---
tema = st.text_input("Sobre o que é o livro?", placeholder="Ex: Adestramento de cães")
paginas = st.slider("Número aproximado de páginas:", 5, 50, 15)

if st.button("🚀 Gerar Livro Agora"):
    if not api_key:
        st.error("Por favor, coloque sua API Key na barra lateral esquerda!")
    elif not tema:
        st.warning("Digite um tema para o livro.")
    else:
        # CONEXÃO
        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        status = st.empty()
        progresso = st.progress(0)

        try:
            # 1. PLANEJAMENTO
            status.write("🧠 Planejando capítulos e título...")
            prompt_plan = f"Crie um JSON com 'titulo_livro', 'subtitulo', 'autor_ficticio' e uma lista 'estrutura' (capitulo, titulo, descricao) para um livro sobre {tema} com {paginas} paginas. Retorne APENAS JSON."
            
            res_plan = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt_plan}]
            )
            plano = json.loads(res_plan.choices[0].message.content.replace("```json","").replace("```",""))
            st.success(f"Título criado: {plano['titulo_livro']}")
            progresso.progress(30)

            # 2. ESCRITA
            livro_md = ""
            total_caps = len(plano['estrutura'])
            
            for i, cap in enumerate(plano['estrutura']):
                status.write(f"✍️ Escrevendo: {cap['titulo']}...")
                prompt_write = f"Escreva o capítulo '{cap['titulo']}' do livro '{plano['titulo_livro']}'. Contexto: {cap['descricao']}. Seja detalhado."
                
                res_write = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt_write}]
                )
                texto_cap = res_write.choices[0].message.content
                livro_md += f"\n\n# {cap['titulo']}\n\n{texto_cap}\n\n"
                
                # Atualiza barra de progresso
                percentual = 30 + int((i+1) / total_caps * 50)
                progresso.progress(percentual)

            # 3. DIAGRAMAÇÃO
            status.write("🎨 Diagramando PDF e criando capa...")
            arquivo_pdf = gerar_pdf_final(plano, livro_md)
            progresso.progress(100)
            status.write("✅ Concluído!")

            # 4. BOTÃO DE DOWNLOAD
            with open(arquivo_pdf, "rb") as f:
                st.download_button(
                    label="📥 Baixar Livro em PDF",
                    data=f,
                    file_name="Meu_Livro_IA.pdf",
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"Ocorreu um erro: {e}")