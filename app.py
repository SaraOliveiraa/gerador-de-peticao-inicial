from __future__ import annotations

import os
import re
import html
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from exporters.docx_exporter import texto_para_docx_bytes
from services.gemini_service import GeminiServiceError, gerar_peticao
from services.prompt_builder import montar_prompt

AREAS_DIREITO = [
    "Civil",
    "Consumidor",
    "Trabalhista",
    "Previdenciário",
    "Tributário",
    "Empresarial",
    "Família e Sucessões",
    "Administrativo",
    "Outro",
]

ALIAS_AREA_CAMPOS = {
    "Previdenciário": "Previdenciario",
    "Tributário": "Tributario",
    "Família e Sucessões": "Familia e Sucessoes",
}

RITOS_PROCESSUAIS = [
    "Comum",
    "Juizado Especial",
    "Procedimento Especial",
    "Cumprimento de Sentença",
    "Execução",
    "Outro",
]

TEMAS_JURIDICOS_COMUNS = [
    "Responsabilidade civil",
    "Inadimplemento contratual",
    "Boa-fé objetiva",
    "Dano moral",
    "Dano material",
    "Inversão do ônus da prova",
    "CDC",
    "Tutela de urgência",
    "Justiça gratuita",
    "Prescrição/decadência",
]

PEDIDOS_BASE = [
    "Citação da parte ré",
    "Procedência total",
    "Procedência parcial",
    "Danos morais",
    "Danos materiais",
    "Obrigação de fazer",
    "Obrigação de não fazer",
    "Tutela de urgência",
    "Justiça gratuita",
    "Condenação em custas e honorários",
    "Produção de provas",
]

SECOES_SUGERIDAS = [
    "Dos fatos",
    "Da competência",
    "Do direito",
    "Da tutela de urgência",
    "Dos pedidos",
    "Do valor da causa",
    "Dos requerimentos finais",
]

ETAPAS_FLUXO = [
    "Contexto Processual",
    "Campos da Área",
    "Partes",
    "Fatos e Provas",
    "Fundamentação",
    "Pedidos",
    "Finalização e Geração",
]

CHAVES_FORMULARIO_BASE = [
    "area_direito",
    "tipo_acao",
    "rito",
    "comarca_uf",
    "foro_vara",
    "autor_nome",
    "autor_doc",
    "autor_end",
    "autor_qualificacao",
    "reu_nome",
    "reu_doc",
    "reu_end",
    "reu_qualificacao",
    "partes_adicionais_raw",
    "fatos",
    "cronologia_raw",
    "provas_raw",
    "teses_juridicas",
    "temas_comuns",
    "fundamentos_legais_raw",
    "temas_custom_raw",
    "pedidos_base",
    "pedidos_custom_raw",
    "secoes_sugeridas",
    "secoes_extras_raw",
    "valor_causa",
    "nivel_detalhamento",
    "tem_tutela_urgencia",
    "tem_gratuidade",
    "tem_prioridade",
    "quer_audiencia",
    "obs_estrategicas",
]

CAMPOS_POR_AREA: dict[str, list[dict[str, Any]]] = {
    "Civil": [
        {
            "id": "natureza_relacao_juridica",
            "label": "Natureza da relação jurídica",
            "widget": "text",
            "placeholder": "Ex.: Contrato de prestação de serviços",
        },
        {
            "id": "bem_ou_obrigacao_discutida",
            "label": "Bem/obrigação discutida",
            "widget": "text",
            "placeholder": "Ex.: Restituição de valores pagos",
        },
        {
            "id": "inadimplemento_ou_ilicito",
            "label": "Inadimplemento ou ato ilícito",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Descreva objetivamente o descumprimento.",
        },
        {
            "id": "tentativa_extrajudicial",
            "label": "Tentativas extrajudiciais",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Negociações, notificações ou acordos frustrados.",
        },
    ],
    "Consumidor": [
        {
            "id": "produto_servico",
            "label": "Produto ou serviço envolvido",
            "widget": "text",
            "placeholder": "Ex.: Plano de internet residencial",
        },
        {
            "id": "falha_prestacao",
            "label": "Falha na prestação/vício",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Descreva a falha e impacto no consumidor.",
        },
        {
            "id": "protocolos_atendimento",
            "label": "Protocolos/atendimento (opcional)",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Um protocolo por linha.",
        },
        {
            "id": "inversao_onus_prova",
            "label": "Solicitar inversão do ônus da prova",
            "widget": "checkbox",
        },
    ],
    "Trabalhista": [
        {
            "id": "periodo_contrato",
            "label": "Período contratual",
            "widget": "text",
            "placeholder": "Ex.: 02/2020 a 11/2025",
        },
        {
            "id": "funcao_salario",
            "label": "Função e salário",
            "widget": "text",
            "placeholder": "Ex.: Analista - R$ 3.500,00",
        },
        {
            "id": "jornada_praticada",
            "label": "Jornada praticada",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Descreva horários, intervalos e extras.",
        },
        {
            "id": "verbas_pretendidas",
            "label": "Verbas trabalhistas pretendidas",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Uma verba por linha.",
        },
    ],
    "Previdenciario": [
        {
            "id": "beneficio_pretendido",
            "label": "Beneficio pretendido",
            "widget": "select",
            "options": [
                "Aposentadoria por idade",
                "Aposentadoria por tempo de contribuicao",
                "Auxilio-doenca",
                "BPC/LOAS",
                "Pensao por morte",
                "Outro",
            ],
        },
        {
            "id": "nb_ou_requerimento",
            "label": "NB/protocolo administrativo (opcional)",
            "widget": "text",
            "placeholder": "Ex.: 1234567890",
        },
        {
            "id": "der_dib",
            "label": "DER/DIB (se houver)",
            "widget": "text",
            "placeholder": "Ex.: DER 10/01/2026",
        },
        {
            "id": "tempo_contribuicao",
            "label": "Tempo de contribuicao e qualidade de segurado",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Resumo dos periodos e contribuicoes.",
        },
    ],
    "Tributario": [
        {
            "id": "tributo_discutido",
            "label": "Tributo discutido",
            "widget": "text",
            "placeholder": "Ex.: ICMS, ISS, IRPJ",
        },
        {
            "id": "periodo_apuracao",
            "label": "Periodo de apuracao",
            "widget": "text",
            "placeholder": "Ex.: 01/2022 a 12/2023",
        },
        {
            "id": "ato_fiscal_impugnado",
            "label": "Ato fiscal/lancamento impugnado",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Descreva auto de infracao, notificacao etc.",
        },
        {
            "id": "pedido_restituicao_compensacao",
            "label": "Incluir pedido de restituicao/compensacao",
            "widget": "checkbox",
        },
    ],
    "Empresarial": [
        {
            "id": "tipo_relacao_empresarial",
            "label": "Tipo de relacao empresarial",
            "widget": "select",
            "options": [
                "Contrato mercantil",
                "Societario",
                "Titulos de credito",
                "Propriedade intelectual",
                "Outro",
            ],
        },
        {
            "id": "clausulas_relevantes",
            "label": "Clausulas/obrigacoes relevantes",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Itens-chave do instrumento contratual/societario.",
        },
        {
            "id": "impacto_negocio",
            "label": "Impacto no negocio",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Danos operacionais, financeiros ou reputacionais.",
        },
        {
            "id": "tentativas_negociacao",
            "label": "Tentativas de negociacao pre-processual",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Resumo das tratativas e respostas.",
        },
    ],
    "Familia e Sucessoes": [
        {
            "id": "subtipo_familia",
            "label": "Subtipo da demanda",
            "widget": "select",
            "options": [
                "Alimentos",
                "Guarda e convivencia",
                "Divorcio",
                "Uniao estavel",
                "Inventario/sucessao",
                "Outro",
            ],
        },
        {
            "id": "existem_filhos_menores",
            "label": "Existem filhos menores envolvidos",
            "widget": "checkbox",
        },
        {
            "id": "regime_bens",
            "label": "Regime de bens (se aplicavel)",
            "widget": "select",
            "options": [
                "Comunhao parcial",
                "Comunhao universal",
                "Separacao convencional",
                "Separacao obrigatoria",
                "Participacao final nos aquestos",
                "Nao informado",
            ],
        },
        {
            "id": "pedido_familiar_central",
            "label": "Pedido familiar/sucessorio central",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Ex.: guarda unilateral com convivio assistido.",
        },
    ],
    "Administrativo": [
        {
            "id": "orgao_autoridade",
            "label": "Orgao/autoridade envolvida",
            "widget": "text",
            "placeholder": "Ex.: INSS, Prefeitura, Receita Federal",
        },
        {
            "id": "ato_administrativo",
            "label": "Ato administrativo questionado",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Descreva ato, data e efeitos concretos.",
        },
        {
            "id": "fase_admin",
            "label": "Fase do processo administrativo",
            "widget": "text",
            "placeholder": "Ex.: indeferimento em 1a instancia administrativa",
        },
        {
            "id": "pedido_liminar_area",
            "label": "Necessidade de medida liminar especifica",
            "widget": "checkbox",
        },
    ],
    "Outro": [
        {
            "id": "contexto_setorial",
            "label": "Contexto tecnico/setorial da causa",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Explique o contexto especializado do caso.",
        },
        {
            "id": "objeto_principal",
            "label": "Objeto principal da pretensao",
            "widget": "text",
            "placeholder": "Ex.: Declaracao de nulidade de clausula X",
        },
        {
            "id": "riscos_sensiveis",
            "label": "Riscos/pontos sensiveis",
            "widget": "textarea",
            "height": 90,
            "placeholder": "Aspectos que exigem cuidado na redacao.",
        },
    ],
}


def _somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _formatar_cpf(digitos: str) -> str:
    if len(digitos) <= 3:
        return digitos
    if len(digitos) <= 6:
        return f"{digitos[:3]}.{digitos[3:]}"
    if len(digitos) <= 9:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:]}"
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:11]}"


def _formatar_cnpj(digitos: str) -> str:
    if len(digitos) <= 2:
        return digitos
    if len(digitos) <= 5:
        return f"{digitos[:2]}.{digitos[2:]}"
    if len(digitos) <= 8:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:]}"
    if len(digitos) <= 12:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:]}"
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:14]}"


def _formatar_cpf_cnpj(valor: str) -> str:
    digitos = _somente_digitos(valor)
    if len(digitos) <= 11:
        return _formatar_cpf(digitos[:11])
    return _formatar_cnpj(digitos[:14])


def _formatar_moeda_br(valor: str) -> str:
    digitos = _somente_digitos(valor)
    if not digitos:
        return ""
    centavos = int(digitos)
    inteiro = centavos // 100
    resto = centavos % 100
    inteiro_formatado = f"{inteiro:,}".replace(",", ".")
    return f"R$ {inteiro_formatado},{resto:02d}"


def _linhas_para_lista(texto: str) -> list[str]:
    itens: list[str] = []
    for linha in (texto or "").splitlines():
        item = linha.strip()
        if item.startswith("-"):
            item = item[1:].strip()
        if item:
            itens.append(item)
    return itens


def _mesclar_itens(*colecoes: list[str]) -> list[str]:
    resultado: list[str] = []
    vistos: set[str] = set()

    for colecao in colecoes:
        for item in colecao:
            texto = (item or "").strip()
            if not texto:
                continue
            chave = texto.casefold()
            if chave in vistos:
                continue
            vistos.add(chave)
            resultado.append(texto)

    return resultado


def _slug(valor: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (valor or "").lower()).strip("_")


def _chave_campo_area(area: str, campo_id: str) -> str:
    return f"area_{_slug(area)}_{_slug(campo_id)}"


def _resolver_area_campos(area: str) -> str:
    area_normalizada = (area or "").strip()
    area_mapeada = ALIAS_AREA_CAMPOS.get(area_normalizada, area_normalizada)
    return area_mapeada if area_mapeada in CAMPOS_POR_AREA else "Outro"


def _clonar_valor_snapshot(valor: Any) -> Any:
    if isinstance(valor, list):
        return valor.copy()
    if isinstance(valor, dict):
        return valor.copy()
    if isinstance(valor, set):
        return set(valor)
    if isinstance(valor, tuple):
        return tuple(valor)
    return valor


def _listar_todas_chaves_formulario() -> list[str]:
    chaves = list(CHAVES_FORMULARIO_BASE)
    for area, campos in CAMPOS_POR_AREA.items():
        for campo in campos:
            campo_id = str(campo.get("id", "")).strip()
            if campo_id:
                chaves.append(_chave_campo_area(area, campo_id))

    dedup: list[str] = []
    vistos: set[str] = set()
    for chave in chaves:
        if chave in vistos:
            continue
        vistos.add(chave)
        dedup.append(chave)
    return dedup


def _salvar_snapshot_formulario() -> None:
    snapshot = st.session_state.get("_form_snapshot", {})
    if not isinstance(snapshot, dict):
        snapshot = {}

    for chave in _listar_todas_chaves_formulario():
        if chave in st.session_state:
            snapshot[chave] = _clonar_valor_snapshot(st.session_state[chave])

    st.session_state["_form_snapshot"] = snapshot


def _restaurar_snapshot_formulario() -> None:
    snapshot = st.session_state.get("_form_snapshot", {})
    if not isinstance(snapshot, dict):
        return

    for chave, valor in snapshot.items():
        if chave not in st.session_state:
            st.session_state[chave] = _clonar_valor_snapshot(valor)


def _renderizar_campo_area(area: str, campo: dict[str, Any]) -> None:
    campo_id = str(campo.get("id", "")).strip()
    if not campo_id:
        return

    chave = _chave_campo_area(area, campo_id)
    rotulo = str(campo.get("label", campo_id))
    tipo_widget = str(campo.get("widget", "text")).strip().lower()
    placeholder = str(campo.get("placeholder", ""))
    ajuda = campo.get("help")
    altura = int(campo.get("height", 90))

    if tipo_widget == "textarea":
        st.text_area(rotulo, key=chave, height=altura, placeholder=placeholder, help=ajuda)
        return

    if tipo_widget == "select":
        opcoes = [str(item) for item in campo.get("options", [])]
        st.selectbox(rotulo, opcoes or ["[PREENCHER]"], key=chave, help=ajuda)
        return

    if tipo_widget == "multiselect":
        opcoes = [str(item) for item in campo.get("options", [])]
        st.multiselect(rotulo, opcoes, key=chave, help=ajuda)
        return

    if tipo_widget == "checkbox":
        st.checkbox(rotulo, key=chave, help=ajuda)
        return

    st.text_input(rotulo, key=chave, placeholder=placeholder, help=ajuda)


def _renderizar_bloco_area(area: str) -> None:
    area_campos = _resolver_area_campos(area)
    campos = CAMPOS_POR_AREA.get(area_campos, CAMPOS_POR_AREA["Outro"])
    st.caption(f"Campos especificos para a area selecionada: {area}")
    for campo in campos:
        _renderizar_campo_area(area_campos, campo)


def _coletar_campos_area_especificos(area: str) -> dict[str, Any]:
    area_campos = _resolver_area_campos(area)
    campos = CAMPOS_POR_AREA.get(area_campos, CAMPOS_POR_AREA["Outro"])
    rotulos: dict[str, str] = {}
    valores: dict[str, Any] = {}

    for campo in campos:
        campo_id = str(campo.get("id", "")).strip()
        if not campo_id:
            continue

        rotulos[campo_id] = str(campo.get("label", campo_id))
        chave = _chave_campo_area(area_campos, campo_id)
        valor = st.session_state.get(chave)

        if isinstance(valor, str):
            valor = valor.strip()
            if not valor:
                continue
        elif isinstance(valor, list):
            valor = [str(item).strip() for item in valor if str(item).strip()]
            if not valor:
                continue
        elif isinstance(valor, bool):
            if not valor:
                continue
        elif valor is None:
            continue

        valores[campo_id] = valor

    return {
        "area": area,
        "rotulos": rotulos,
        "valores": valores,
    }


def _sanitizar_nome_arquivo(texto: str) -> str:
    nome = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", texto or "")
    nome = re.sub(r"\s+", " ", nome).strip(" .")
    return nome


def _nome_arquivo_docx(autor_nome: str) -> str:
    nome_autor = _sanitizar_nome_arquivo(autor_nome)
    if not nome_autor:
        nome_autor = "[NOME DO AUTOR]"
    return f"Petição Inicial - {nome_autor}.docx"


def _aplicar_mascara_documento(campo: str) -> None:
    st.session_state[campo] = _formatar_cpf_cnpj(st.session_state.get(campo, ""))


def _aplicar_mascara_moeda(campo: str) -> None:
    st.session_state[campo] = _formatar_moeda_br(st.session_state.get(campo, ""))


def _aplicar_mascaras_formulario() -> None:
    _aplicar_mascara_documento("autor_doc")
    _aplicar_mascara_documento("reu_doc")
    _aplicar_mascara_moeda("valor_causa")


def _coletar_payload() -> dict[str, Any]:
    area_direito = st.session_state.get("area_direito", "Outro")
    campos_area_especificos = _coletar_campos_area_especificos(area_direito)

    pedidos_custom = _linhas_para_lista(st.session_state.get("pedidos_custom_raw", ""))
    pedidos_base = st.session_state.get("pedidos_base", [])
    pedidos_lista_final = _mesclar_itens(pedidos_base, pedidos_custom)

    fundamentos_legais = _linhas_para_lista(st.session_state.get("fundamentos_legais_raw", ""))
    provas_documentos = _linhas_para_lista(st.session_state.get("provas_raw", ""))
    cronologia = _linhas_para_lista(st.session_state.get("cronologia_raw", ""))
    partes_adicionais = _linhas_para_lista(st.session_state.get("partes_adicionais_raw", ""))
    secoes_extras = _linhas_para_lista(st.session_state.get("secoes_extras_raw", ""))

    temas_custom = _linhas_para_lista(st.session_state.get("temas_custom_raw", ""))
    temas_comuns = st.session_state.get("temas_comuns", [])
    temas_juridicos = _mesclar_itens(temas_comuns, temas_custom)

    autor = {
        "nome": st.session_state.get("autor_nome", ""),
        "documento": st.session_state.get("autor_doc", ""),
        "endereco": st.session_state.get("autor_end", ""),
        "qualificacao": st.session_state.get("autor_qualificacao", ""),
    }

    reu = {
        "nome": st.session_state.get("reu_nome", ""),
        "documento": st.session_state.get("reu_doc", ""),
        "endereco": st.session_state.get("reu_end", ""),
        "qualificacao": st.session_state.get("reu_qualificacao", ""),
    }

    dados = {
        "contexto_processual": {
            "area_direito": area_direito,
            "tipo_acao": st.session_state.get("tipo_acao", ""),
            "rito": st.session_state.get("rito", ""),
            "comarca_uf": st.session_state.get("comarca_uf", ""),
            "foro_vara": st.session_state.get("foro_vara", ""),
        },
        "campos_area_especificos": campos_area_especificos,
        "partes": {
            "autor": autor,
            "reu": reu,
            "partes_adicionais": partes_adicionais,
        },
        "narrativa": {
            "fatos": st.session_state.get("fatos", ""),
            "cronologia": cronologia,
            "provas_documentos": provas_documentos,
        },
        "fundamentacao": {
            "teses_juridicas": st.session_state.get("teses_juridicas", ""),
            "temas_juridicos": temas_juridicos,
            "fundamentos_legais": fundamentos_legais,
        },
        "pedidos": pedidos_lista_final,
        "pedidos_detalhados": {
            "base_selecionados": pedidos_base,
            "personalizados": pedidos_custom,
            "lista_final": pedidos_lista_final,
        },
        "estrutura_peticao": {
            "secoes_sugeridas": st.session_state.get("secoes_sugeridas", []),
            "secoes_extras": secoes_extras,
            "nivel_detalhamento": st.session_state.get("nivel_detalhamento", "Padrao"),
        },
        "parametros_finais": {
            "valor_causa": st.session_state.get("valor_causa", ""),
            "tutela_urgencia": st.session_state.get("tem_tutela_urgencia", False),
            "justica_gratuita": st.session_state.get("tem_gratuidade", False),
            "prioridade_tramitacao": st.session_state.get("tem_prioridade", False),
            "audiencia_conciliacao": st.session_state.get("quer_audiencia", True),
        },
        "observacoes_estrategicas": st.session_state.get("obs_estrategicas", ""),
        "autor": autor,
        "reu": reu,
        "tipo_acao": st.session_state.get("tipo_acao", ""),
        "fatos": st.session_state.get("fatos", ""),
        "valor_causa": st.session_state.get("valor_causa", ""),
    }

    return dados


def _campo_preenchido(chave: str) -> bool:
    valor = st.session_state.get(chave)
    if isinstance(valor, str):
        return bool(valor.strip())
    if isinstance(valor, list):
        return len(valor) > 0
    if isinstance(valor, bool):
        return valor
    return valor is not None


def _linhas_com_texto(chave: str) -> list[str]:
    return _linhas_para_lista(st.session_state.get(chave, ""))


def _obter_etapa_idx() -> int:
    if "etapa_idx" not in st.session_state:
        st.session_state.etapa_idx = 0
    idx = int(st.session_state.etapa_idx)
    return max(0, min(idx, len(ETAPAS_FLUXO) - 1))


def _definir_etapa_idx(idx: int) -> None:
    st.session_state.etapa_idx = max(0, min(int(idx), len(ETAPAS_FLUXO) - 1))


def _campos_obrigatorios_da_etapa(etapa: str) -> list[tuple[str, str]]:
    obrigatorios: dict[str, list[tuple[str, str]]] = {
        "Contexto Processual": [
            ("tipo_acao", "Tipo da ação"),
            ("comarca_uf", "Comarca / UF"),
        ],
        "Partes": [
            ("autor_nome", "Nome do autor"),
            ("autor_doc", "CPF/CNPJ do autor"),
            ("autor_end", "Endereço do autor"),
            ("reu_nome", "Nome do réu"),
            ("reu_doc", "CPF/CNPJ do réu"),
            ("reu_end", "Endereço do réu"),
        ],
        "Fatos e Provas": [
            ("fatos", "Fatos principais"),
        ],
        "Fundamentação": [
            ("teses_juridicas", "Teses jurídicas"),
        ],
        "Finalização e Geração": [
            ("valor_causa", "Valor da causa"),
        ],
    }
    return obrigatorios.get(etapa, [])


def _validar_etapa(etapa: str) -> list[str]:
    faltantes: list[str] = []

    for chave, rotulo in _campos_obrigatorios_da_etapa(etapa):
        if not _campo_preenchido(chave):
            faltantes.append(rotulo)

    if etapa == "Pedidos":
        pedidos_base = st.session_state.get("pedidos_base", [])
        pedidos_custom = _linhas_com_texto("pedidos_custom_raw")
        if not pedidos_base and not pedidos_custom:
            faltantes.append("Selecione ao menos um pedido (base ou personalizado)")

    return faltantes


def _validar_essenciais_para_geracao() -> list[str]:
    etapas_relevantes = [
        "Contexto Processual",
        "Partes",
        "Fatos e Provas",
        "Fundamentação",
        "Pedidos",
        "Finalização e Geração",
    ]
    faltantes: list[str] = []
    for etapa in etapas_relevantes:
        faltantes.extend(_validar_etapa(etapa))

    dedup: list[str] = []
    vistos: set[str] = set()
    for item in faltantes:
        chave = item.casefold()
        if chave in vistos:
            continue
        vistos.add(chave)
        dedup.append(item)
    return dedup


def _calcular_progresso_preenchimento() -> float:
    campos_referencia = [
        "area_direito",
        "tipo_acao",
        "comarca_uf",
        "autor_nome",
        "reu_nome",
        "fatos",
        "pedidos_base",
        "teses_juridicas",
    ]
    preenchidos = sum(1 for campo in campos_referencia if _campo_preenchido(campo))
    return preenchidos / len(campos_referencia)


def _menu_fluxo_lateral() -> tuple[str, int]:
    with st.sidebar:
        st.markdown("### Painel do Caso")
        st.caption("Navegue por etapas para montar a petição.")

        st.selectbox(
            "Área do direito",
            AREAS_DIREITO,
            key="area_direito",
        )

        etapa_idx_atual = _obter_etapa_idx()
        st.markdown("### Fluxo de Preenchimento")

        linhas_fluxo: list[str] = []
        for idx, etapa_nome in enumerate(ETAPAS_FLUXO):
            if idx < etapa_idx_atual:
                classe = "concluida"
                marcador = "✓"
            elif idx == etapa_idx_atual:
                classe = "atual"
                marcador = str(idx + 1)
            else:
                classe = "pendente"
                marcador = str(idx + 1)

            linhas_fluxo.append(
                (
                    f'<div class="fluxo-item {classe}">'
                    f'<span class="fluxo-badge">{html.escape(marcador)}</span>'
                    f'<span class="fluxo-text">{html.escape(etapa_nome)}</span>'
                    "</div>"
                )
            )

        st.markdown(f'<div class="fluxo-tracker">{"".join(linhas_fluxo)}</div>', unsafe_allow_html=True)
        st.caption("Apenas acompanhamento visual. Use os botões Voltar/Avançar para mudar de etapa.")

        progresso = _calcular_progresso_preenchimento()
        st.progress(progresso)
        st.caption(f"Preenchimento-base: {int(progresso * 100)}%")

    return ETAPAS_FLUXO[etapa_idx_atual], etapa_idx_atual


def _aplicar_estilo_preto_dourado() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background:
                    radial-gradient(1200px 520px at -8% -8%, rgba(214, 170, 71, 0.22), rgba(0, 0, 0, 0) 55%),
                    radial-gradient(900px 420px at 108% 4%, rgba(127, 98, 29, 0.25), rgba(0, 0, 0, 0) 52%),
                    linear-gradient(180deg, #171717 0%, #101010 100%);
                color: #fbfbfb;
            }

            .main .block-container {
                max-width: 1220px;
                padding-top: 1rem;
                padding-bottom: 2.4rem;
            }

            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #1a1a1a 0%, #121212 100%);
                border-right: 1px solid rgba(216, 171, 73, 0.28);
            }

            [data-testid="stSidebar"] .block-container {
                padding-top: 1rem;
            }

            .fluxo-tracker {
                margin-top: 0.45rem;
                border: 1px solid rgba(216, 171, 73, 0.24);
                border-radius: 14px;
                padding: 0.45rem 0.4rem;
                background: #1b1b1b;
            }

            .fluxo-item {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                margin: 3px 0;
                padding: 0.42rem 0.45rem;
                border-radius: 10px;
                border: 1px solid transparent;
                transition: none;
            }

            .fluxo-item.pendente {
                color: #ececec;
                background: rgba(255, 255, 255, 0.04);
            }

            .fluxo-item.concluida {
                color: #d6ffe2;
                border-color: rgba(115, 196, 138, 0.35);
                background: rgba(89, 180, 112, 0.14);
            }

            .fluxo-item.atual {
                color: #241a05;
                border-color: rgba(255, 230, 166, 0.45);
                background: linear-gradient(135deg, #d0a64b, #f6dea6);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.24);
            }

            .fluxo-badge {
                width: 1.22rem;
                height: 1.22rem;
                border-radius: 999px;
                border: 1px solid rgba(216, 171, 73, 0.35);
                display: inline-flex;
                align-items: center;
                justify-content: center;
                font-size: 0.72rem;
                font-weight: 700;
                color: #f5dc9c;
                background: rgba(216, 171, 73, 0.12);
                flex: 0 0 1.22rem;
            }

            .fluxo-item.concluida .fluxo-badge {
                border-color: rgba(115, 196, 138, 0.55);
                color: #d6ffe2;
                background: rgba(89, 180, 112, 0.2);
            }

            .fluxo-item.atual .fluxo-badge {
                border-color: rgba(44, 32, 7, 0.35);
                color: #2a1f05;
                background: rgba(255, 244, 216, 0.5);
            }

            .fluxo-text {
                font-size: 0.9rem;
                font-weight: 600;
                line-height: 1.2;
            }

            [data-testid="stAppViewContainer"] * {
                font-family: "Montserrat", "Trebuchet MS", sans-serif;
            }

            h1, h2, h3, label, p, span {
                color: #fbfbfb !important;
            }

            div[data-testid="stCaptionContainer"] p {
                color: #d0d0d0 !important;
            }

            div[data-testid="stForm"] {
                background: linear-gradient(180deg, rgba(35, 35, 35, 0.96), rgba(20, 20, 20, 0.96));
                border: 1px solid rgba(216, 171, 73, 0.42);
                border-radius: 20px;
                padding: 1.3rem;
                backdrop-filter: blur(8px);
                box-shadow: 0 18px 34px rgba(0, 0, 0, 0.35);
            }

            .hero-shell {
                position: relative;
                overflow: hidden;
                border-radius: 20px;
                border: 1px solid rgba(216, 171, 73, 0.42);
                background: linear-gradient(135deg, rgba(39, 39, 39, 0.95), rgba(20, 20, 20, 0.96));
                padding: 1.15rem 1.25rem 1rem 1.25rem;
                margin-bottom: 0.85rem;
                box-shadow: 0 14px 28px rgba(0, 0, 0, 0.3);
            }

            .hero-shell::after {
                content: "";
                position: absolute;
                inset: -1px;
                background: radial-gradient(circle at 88% 15%, rgba(246, 217, 139, 0.18), rgba(0, 0, 0, 0) 45%);
                pointer-events: none;
            }

            .hero-title {
                position: relative;
                z-index: 1;
                margin: 0;
                font-size: 2rem;
                font-weight: 750;
                letter-spacing: 0.2px;
                color: #f6d98b !important;
                line-height: 1.15;
            }

            .hero-subtitle {
                position: relative;
                z-index: 1;
                margin-top: 0.35rem;
                color: #e2e2e2;
                font-size: 0.95rem;
                max-width: 74ch;
            }

            .hero-chip-row {
                position: relative;
                z-index: 1;
                display: flex;
                flex-wrap: wrap;
                gap: 0.45rem;
                margin-top: 0.8rem;
            }

            .hero-chip {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                border: 1px solid rgba(216, 171, 73, 0.45);
                background: rgba(255, 224, 139, 0.08);
                color: #ffe9b4;
                font-size: 0.8rem;
                letter-spacing: 0.15px;
                padding: 0.24rem 0.62rem;
            }

            .hero-chip.status-ok {
                border-color: rgba(115, 196, 138, 0.7);
                background: rgba(89, 180, 112, 0.14);
                color: #c8ffd6;
            }

            .hero-chip.status-warn {
                border-color: rgba(232, 150, 65, 0.7);
                background: rgba(232, 150, 65, 0.15);
                color: #ffd8ac;
            }

            .secao-titulo {
                display: flex;
                align-items: center;
                gap: 0.55rem;
                margin-top: 1.1rem;
                margin-bottom: 0.6rem;
                font-weight: 700;
                letter-spacing: 0.22px;
                color: #f6d98b;
                font-size: 1rem;
            }

            .secao-indice {
                width: 1.6rem;
                height: 1.6rem;
                border-radius: 999px;
                border: 1px solid rgba(216, 171, 73, 0.65);
                background: rgba(216, 171, 73, 0.16);
                display: inline-flex;
                align-items: center;
                justify-content: center;
                color: #ffe8b8;
                font-size: 0.77rem;
                font-weight: 700;
                flex: 0 0 1.6rem;
            }

            .secao-linha {
                flex: 1;
                height: 1px;
                background: linear-gradient(90deg, rgba(216, 171, 73, 0.55), rgba(216, 171, 73, 0.04));
            }

            div[data-baseweb="input"] > div,
            div[data-baseweb="textarea"] > div,
            div[data-baseweb="select"] > div {
                background-color: #232323;
                border: 1px solid #725c2a;
                border-radius: 12px;
                min-height: 44px;
                transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease;
            }

            div[data-baseweb="input"] > div:focus-within,
            div[data-baseweb="textarea"] > div:focus-within,
            div[data-baseweb="select"] > div:focus-within {
                border-color: #d8ab49;
                box-shadow: 0 0 0 1px #d8ab49, 0 0 0 4px rgba(216, 171, 73, 0.16);
                transform: translateY(-1px);
            }

            input, textarea {
                color: #fcfcfc !important;
                font-size: 0.95rem !important;
            }

            textarea {
                line-height: 1.44 !important;
            }

            input::placeholder, textarea::placeholder {
                color: #b3b3b3 !important;
            }

            div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
                background-color: rgba(216, 171, 73, 0.14);
                border: 1px solid rgba(216, 171, 73, 0.5);
                color: #f5dc9c;
            }

            div[data-testid="stFormSubmitButton"] > button,
            div[data-testid="stDownloadButton"] > button {
                background: linear-gradient(135deg, #d0a64b, #f6dea6);
                color: #1d1502 !important;
                font-weight: 700;
                border: 1px solid rgba(255, 230, 166, 0.45);
                border-radius: 999px;
                padding: 0.58rem 1.32rem;
                box-shadow: 0 10px 22px rgba(0, 0, 0, 0.34);
                transition: transform .18s ease, filter .18s ease, box-shadow .18s ease;
            }

            div[data-testid="stFormSubmitButton"] > button:hover,
            div[data-testid="stDownloadButton"] > button:hover {
                filter: brightness(1.03);
                transform: translateY(-2px);
                box-shadow: 0 14px 28px rgba(0, 0, 0, 0.38);
            }

            div[data-testid="stAlert"] {
                border-radius: 12px;
                border: 1px solid rgba(216, 171, 73, 0.35);
            }

            .preview-bloco {
                margin-top: 1.25rem;
                margin-bottom: 0.5rem;
                border-radius: 14px;
                border: 1px solid rgba(216, 171, 73, 0.34);
                background: linear-gradient(180deg, rgba(38, 38, 38, 0.88), rgba(22, 22, 22, 0.9));
                padding: 0.62rem 0.85rem;
                color: #f6dea6;
                font-weight: 650;
            }

            @media (max-width: 900px) {
                .main .block-container {
                    padding-top: 0.7rem;
                    padding-bottom: 1.4rem;
                }

                .hero-title {
                    font-size: 1.45rem;
                }

                .hero-subtitle {
                    font-size: 0.87rem;
                }

                div[data-testid="stForm"] {
                    padding: 0.95rem;
                    border-radius: 16px;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_cabecalho_moderno(area: str, modelo: str, api_configurada: bool) -> None:
    area_esc = html.escape(area or "Outro")
    modelo_esc = html.escape(modelo or "[PREENCHER]")
    status_label = "Chave API configurada" if api_configurada else "Chave API ausente"
    status_css = "status-ok" if api_configurada else "status-warn"

    st.markdown(
        f"""
        <section class="hero-shell">
            <h1 class="hero-title">Gerador de Petição Inicial</h1>
            <p class="hero-subtitle">
                Fluxo inteligente para montar petições iniciais com campos dinâmicos por área do direito.
            </p>
            <div class="hero-chip-row">
                <span class="hero-chip">Área: {area_esc}</span>
                <span class="hero-chip">Modelo: {modelo_esc}</span>
                <span class="hero-chip {status_css}">{status_label}</span>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _titulo_secao(texto: str) -> None:
    texto_limpo = (texto or "").strip()
    match = re.match(r"^(\d+)\)\s*(.*)$", texto_limpo)
    if match:
        indice = html.escape(match.group(1))
        titulo = html.escape(match.group(2).strip())
        indice_html = f'<span class="secao-indice">{indice}</span>'
    else:
        titulo = html.escape(texto_limpo)
        indice_html = ""

    st.markdown(
        f'<div class="secao-titulo">{indice_html}<span>{titulo}</span><span class="secao-linha"></span></div>',
        unsafe_allow_html=True,
    )


load_dotenv()

st.set_page_config(page_title="Gerador de Peticao Inicial (Gemini)", layout="wide")
_aplicar_estilo_preto_dourado()
_restaurar_snapshot_formulario()

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
etapa_atual, etapa_idx = _menu_fluxo_lateral()
area_selecionada = st.session_state.get("area_direito", AREAS_DIREITO[0])
_render_cabecalho_moderno(area=area_selecionada, modelo=gemini_model, api_configurada=bool(api_key))
if not api_key:
    st.warning("Configure sua chave no .env (GEMINI_API_KEY ou GOOGLE_API_KEY) antes de gerar.")

voltar_etapa = False
avancar_etapa = False
gerar = False

with st.form("form_peticao"):
    st.caption(f"Etapa atual: {etapa_atual}")
    campos_obrigatorios_etapa = _campos_obrigatorios_da_etapa(etapa_atual)
    if campos_obrigatorios_etapa:
        rotulos = ", ".join(rotulo for _, rotulo in campos_obrigatorios_etapa)
        st.caption(f"Obrigatórios nesta etapa: {rotulos}")
    elif etapa_atual == "Pedidos":
        st.caption("Obrigatório nesta etapa: ao menos um pedido (base ou personalizado).")

    if etapa_atual == "Contexto Processual":
        _titulo_secao("1) Contexto Processual")
        st.caption(f"Área selecionada: {area_selecionada}")
        ctx1, ctx2 = st.columns(2)

        with ctx1:
            st.text_input("Tipo da ação", key="tipo_acao", placeholder="Ex.: Revisional de contrato")
        with ctx2:
            st.selectbox("Rito/Procedimento", RITOS_PROCESSUAIS, key="rito")

        ctx3, ctx4 = st.columns(2)
        with ctx3:
            st.text_input("Comarca / UF", key="comarca_uf", placeholder="Ex.: São Paulo/SP")
        with ctx4:
            st.text_input("Foro / Vara (opcional)", key="foro_vara", placeholder="Ex.: 2ª Vara Cível")

    elif etapa_atual == "Campos da Área":
        _titulo_secao("2) Campos Específicos da Área")
        _renderizar_bloco_area(area_selecionada)

    elif etapa_atual == "Partes":
        _titulo_secao("3) Partes")
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Autor")
            st.text_input("Nome", key="autor_nome", placeholder="Ex.: Maria da Silva")
            st.text_input(
                "CPF/CNPJ",
                key="autor_doc",
                placeholder="000.000.000-00 ou 00.000.000/0000-00",
            )
            st.text_input(
                "Endereço",
                key="autor_end",
                placeholder="Rua, número, bairro, cidade/UF",
            )
            st.text_area(
                "Qualificação adicional (opcional)",
                key="autor_qualificacao",
                height=90,
                placeholder="Profissão, estado civil, nacionalidade, e-mail etc.",
            )

        with col2:
            st.subheader("Réu")
            st.text_input("Nome / Razão social", key="reu_nome", placeholder="Ex.: Empresa XYZ LTDA")
            st.text_input(
                "CPF/CNPJ do réu",
                key="reu_doc",
                placeholder="000.000.000-00 ou 00.000.000/0000-00",
            )
            st.text_input(
                "Endereço do réu",
                key="reu_end",
                placeholder="Rua, número, bairro, cidade/UF",
            )
            st.text_area(
                "Qualificação adicional do réu (opcional)",
                key="reu_qualificacao",
                height=90,
                placeholder="Dados empresariais, representação, e-mail etc.",
            )

        st.text_area(
            "Partes adicionais (opcional, uma por linha)",
            key="partes_adicionais_raw",
            height=90,
            placeholder="Ex.: Litisconsorte ativo | Nome | CPF/CNPJ | Endereço",
        )

    elif etapa_atual == "Fatos e Provas":
        _titulo_secao("4) Narrativa Fática")
        st.text_area(
            "Fatos principais",
            key="fatos",
            height=180,
            placeholder="Descreva os fatos de forma cronológica e objetiva.",
        )
        st.text_area(
            "Cronologia detalhada (opcional, um evento por linha)",
            key="cronologia_raw",
            height=100,
            placeholder="Ex.: 10/01/2026 - Contrato assinado",
        )
        st.text_area(
            "Documentos e provas (opcional, um item por linha)",
            key="provas_raw",
            height=100,
            placeholder="Ex.: Contrato, comprovantes de pagamento, trocas de e-mail",
        )

    elif etapa_atual == "Fundamentação":
        _titulo_secao("5) Fundamentação Jurídica")
        st.text_area(
            "Teses jurídicas (linha de argumentação)",
            key="teses_juridicas",
            height=130,
            placeholder="Quais pontos jurídicos devem ser defendidos na petição.",
        )

        fun1, fun2 = st.columns(2)
        with fun1:
            st.multiselect("Temas jurídicos comuns", TEMAS_JURIDICOS_COMUNS, key="temas_comuns")
        with fun2:
            st.text_area(
                "Fundamentos legais (opcional, um por linha)",
                key="fundamentos_legais_raw",
                height=120,
                placeholder="Ex.: Art. 186 do CC; Art. 6, VIII, do CDC",
            )

        st.text_area(
            "Temas jurídicos adicionais (opcional, um por linha)",
            key="temas_custom_raw",
            height=90,
            placeholder="Ex.: Teoria do adimplemento substancial",
        )

    elif etapa_atual == "Pedidos":
        _titulo_secao("6) Pedidos")
        ped1, ped2 = st.columns(2)
        with ped1:
            st.multiselect("Pedidos base", PEDIDOS_BASE, key="pedidos_base")
        with ped2:
            st.text_area(
                "Pedidos personalizados (um por linha)",
                key="pedidos_custom_raw",
                height=150,
                placeholder="Ex.: Condenação ao pagamento de R$ 15.000,00 a título de dano moral",
            )

    elif etapa_atual == "Finalização e Geração":
        _titulo_secao("7) Estrutura da Peça e Parâmetros Finais")
        fim1, fim2 = st.columns(2)

        with fim1:
            st.multiselect(
                "Seções sugeridas para organizar a petição",
                SECOES_SUGERIDAS,
                default=[
                    "Dos fatos",
                    "Do direito",
                    "Dos pedidos",
                    "Do valor da causa",
                    "Dos requerimentos finais",
                ],
                key="secoes_sugeridas",
            )
            st.text_area(
                "Seções extras personalizadas (opcional, uma por linha)",
                key="secoes_extras_raw",
                height=100,
                placeholder="Ex.: Da inversão do ônus da prova",
            )

        with fim2:
            st.text_input(
                "Valor da causa (se souber)",
                key="valor_causa",
                placeholder="Digite apenas números. Ex.: 125000 -> R$ 1.250,00",
            )
            st.radio(
                "Nível de detalhamento",
                ["Enxuto", "Padrão", "Aprofundado"],
                index=1,
                horizontal=True,
                key="nivel_detalhamento",
            )
            st.checkbox("Incluir pedido de tutela de urgência", key="tem_tutela_urgencia")
            st.checkbox("Incluir pedido de justiça gratuita", key="tem_gratuidade")
            st.checkbox("Incluir prioridade de tramitação", key="tem_prioridade")
            st.checkbox("Manifestar interesse em audiência de conciliação", key="quer_audiencia", value=True)

        st.text_area(
            "Observações estratégicas para a redação (opcional)",
            key="obs_estrategicas",
            height=100,
            placeholder="Diretrizes de linguagem, foco, riscos e pontos sensíveis.",
        )

    if etapa_atual == "Finalização e Geração":
        nav1, nav2 = st.columns(2)
        with nav1:
            voltar_etapa = st.form_submit_button("Voltar")
        with nav2:
            gerar = st.form_submit_button("Gerar petição", on_click=_aplicar_mascaras_formulario)
    else:
        nav1, nav2 = st.columns(2)
        with nav1:
            voltar_etapa = st.form_submit_button("Voltar", disabled=etapa_idx == 0)
        with nav2:
            avancar_etapa = st.form_submit_button("Avançar")

_salvar_snapshot_formulario()

if "peticao_texto" not in st.session_state:
    st.session_state.peticao_texto = ""

if voltar_etapa:
    _definir_etapa_idx(etapa_idx - 1)
    st.rerun()

if avancar_etapa:
    faltantes_etapa = _validar_etapa(etapa_atual)
    if faltantes_etapa:
        itens = "\n".join(f"- {item}" for item in faltantes_etapa)
        st.error(f"Preencha os campos obrigatórios antes de avançar:\n{itens}")
    else:
        _definir_etapa_idx(etapa_idx + 1)
        st.rerun()

if gerar:
    _restaurar_snapshot_formulario()
    faltantes_geracao = _validar_essenciais_para_geracao()
    if faltantes_geracao:
        itens = "\n".join(f"- {item}" for item in faltantes_geracao)
        st.error(f"Não é possível gerar ainda. Campos principais obrigatórios pendentes:\n{itens}")
    else:
        dados = _coletar_payload()
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
    st.markdown('<div class="preview-bloco">Prévia da petição gerada</div>', unsafe_allow_html=True)
    st.text_area("Texto gerado", st.session_state.peticao_texto, height=420)
    nome_arquivo_docx = _nome_arquivo_docx(st.session_state.get("autor_nome", ""))

    docx_bytes = texto_para_docx_bytes(
        titulo="PETICAO INICIAL",
        texto=st.session_state.peticao_texto,
    )

    st.download_button(
        "Baixar .docx",
        data=docx_bytes,
        file_name=nome_arquivo_docx,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
