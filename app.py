from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from exporters.docx_exporter import texto_para_docx_bytes
from services.gemini_service import GeminiServiceError, gerar_peticao
from services.prompt_builder import montar_prompt

load_dotenv()

st.set_page_config(page_title="Gerador de Peticao (Gemini)", layout="wide")
st.title("Gerador de Peticao Inicial (Gemini + Streamlit)")

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
if not api_key:
    st.warning("Configure sua chave no .env (GEMINI_API_KEY ou GOOGLE_API_KEY) antes de gerar.")
st.caption(f"Modelo atual: {gemini_model}")

with st.form("form_peticao"):
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Cliente (Autor)")
        autor_nome = st.text_input("Nome")
        autor_doc = st.text_input("CPF/CNPJ")
        autor_end = st.text_input("Endereco")

    with col2:
        st.subheader("Reu")
        reu_nome = st.text_input("Nome/Razao Social")
        reu_doc = st.text_input("CPF/CNPJ do Reu")
        reu_end = st.text_input("Endereco do Reu")

    st.subheader("Caso")
    tipo_acao = st.selectbox(
        "Tipo de acao",
        [
            "Indenizacao por danos morais",
            "Cobranca",
            "Obrigacao de fazer",
            "Rescisao contratual",
            "Outro",
        ],
    )
    fatos = st.text_area("Fatos (conte do jeito que aconteceu)", height=180)
    pedidos = st.multiselect(
        "Pedidos (marque os aplicaveis)",
        [
            "Danos morais",
            "Danos materiais",
            "Tutela de urgencia",
            "Gratuidade da justica",
            "Juros e correcao monetaria",
            "Citacao do reu",
            "Condenacao em custas e honorarios",
        ],
    )
    valor_causa = st.text_input("Valor da causa (se souber)")

    gerar = st.form_submit_button("Gerar peticao")

if "peticao_texto" not in st.session_state:
    st.session_state.peticao_texto = ""

if gerar:
    dados = {
        "autor": {"nome": autor_nome, "documento": autor_doc, "endereco": autor_end},
        "reu": {"nome": reu_nome, "documento": reu_doc, "endereco": reu_end},
        "tipo_acao": tipo_acao,
        "fatos": fatos,
        "pedidos": pedidos,
        "valor_causa": valor_causa,
    }

    prompt = montar_prompt(dados)

    with st.spinner("Gerando a peticao..."):
        try:
            texto = gerar_peticao(prompt, model=gemini_model)
            st.session_state.peticao_texto = texto
        except GeminiServiceError as exc:
            st.error(str(exc))
        except Exception as exc:  # pragma: no cover
            st.error(f"Erro inesperado ao gerar peticao: {exc}")

if st.session_state.peticao_texto:
    st.subheader("Previa")
    st.text_area("Texto gerado", st.session_state.peticao_texto, height=420)

    docx_bytes = texto_para_docx_bytes(
        titulo="PETICAO INICIAL",
        texto=st.session_state.peticao_texto,
    )

    st.download_button(
        "Baixar .docx",
        data=docx_bytes,
        file_name="peticao_inicial.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
