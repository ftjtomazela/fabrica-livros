import streamlit as st
from openai import OpenAI
import json
import markdown
import re
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerador de Livros IA", page_icon="📚")

st.title("📚 Fábrica de Livros com IA")
st.write("Crie livros completos em PDF direto pelo celular.")

with st.sidebar:
    st.header("Configurações")
    api_key = st.text_input("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", type="password")
    st.info("Pegue sua chave em: console.groq.com")

def limpar_texto(texto):
    # Remove caracteres especiais que o PDF básico não entende
    return re.sub(r'[^\x00-\x7FáéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ ]+', '', texto)

def gerar_pdf_fpdf(plano, conteudo_md):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- CAPA ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 30)
    pdf.ln(60)
    pdf.multi_cell(0, 15, limpar_texto(plano['titulo_livro']).upper(), align="C")
    
    pdf.set_font("Helvetica", "I", 16)
    pdf.ln(10)
    pdf.multi_cell(0, 10, limpar_texto(plano['subtitulo']), align="C")
    
    pdf.set_font("Helvetica", "", 12)
    pdf.ln(100)
    pdf.cell(0, 10, f"Autor: {limpar_texto(plano['autor_ficticio'])}", align="C")
    
    # --- CONTEÚDO ---
    # Quebra o markdown em parágrafos simples para o PDF
    pdf.add_page()
    pdf.set_font("Helvetica", "", 12)
    
    linhas = conteudo_md.split('\n')
    for linha in linhas:
        linha_limpa = limpar_texto(linha)
        if linha.startswith('# '): # Título de capítulo
            pdf.ln(10)
            pdf.set_font("Helvetica", "B", 18)
            pdf.multi_cell(0, 10, linha_limpa.replace('# ', ''))
            pdf.set_font("Helvetica", "", 12)
            pdf.ln(5)
        elif linha.strip() == "---":
            pdf.add_page()
        else:
            pdf.multi_cell(0, 8, linha_limpa)
            pdf.ln(2)

    pdf.output("Livro_Final.pdf")
    return "Livro_Final.pdf"

# --- INTERFACE ---
tema = st.text_input("Sobre o que é o livro?", placeholder="Ex: Tráfego Pago")
paginas = st.slider("Número de páginas:", 5, 50, 15)

if st.button("🚀 Gerar Livro Agora"):
    if not api_key:
        st.error("Coloque sua API Key na lateral!")
    elif not tema:
        st.warning("Defina um tema.")
    else:
        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        status = st.empty()
        
        try:
            status.write("🧠 Planejando capítulos...")
            prompt_plan = f"Retorne APENAS um JSON com 'titulo_livro', 'subtitulo', 'autor_ficticio' e uma lista 'estrutura' (capitulo, titulo, descricao) para um livro sobre {tema} com {paginas} paginas."
            
            res_plan = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt_plan}]
            )
            plano = json.loads(res_plan.choices[0].message.content.replace("```json","").replace("```",""))
            
            livro_md = ""
            for cap in plano['estrutura']:
                status.write(f"✍️ Escrevendo: {cap['titulo']}...")
                res_write = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": f"Escreva o capítulo '{cap['titulo']}' do livro '{plano['titulo_livro']}'. Contexto: {cap['descricao']}."}]
                )
                livro_md += f"\n\n# {cap['titulo']}\n\n{res_write.choices[0].message.content}\n\n---\n"

            status.write("🎨 Gerando PDF...")
            arquivo_pdf = gerar_pdf_fpdf(plano, livro_md)
            
            with open(arquivo_pdf, "rb") as f:
                st.download_button("📥 Baixar Livro em PDF", f, "Meu_Livro_IA.pdf", "application/pdf")
            status.write("✅ Concluído!")

        except Exception as e:
            st.error(f"Erro: {e}")
