from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

PROMPT_BASE = """
Voce e um assistente juridico (Brasil) e deve redigir uma PETICAO INICIAL completa, formal e bem estruturada.

REGRAS CRITICAS (obrigatorias):
- NAO invente fatos, datas, valores, documentos, nomes, numeros de processo, jurisprudencia especifica, nem artigos de lei especificos se nao forem fornecidos.
- Use somente as informacoes recebidas no JSON do caso.
- Se faltar qualquer dado essencial, use exatamente: [PREENCHER].
- NUNCA substitua por [PREENCHER] um dado que esteja explicitamente presente no JSON.
- Nao crie provas que nao foram informadas.
- Nao afirme circunstancias medicas, economicas ou tecnicas nao descritas.
- Mantenha coerencia interna entre fatos, fundamentos e pedidos.

FORMATO DA SAIDA:
- Linguagem juridica formal, clara e objetiva.
- Texto puro (sem Markdown), pronto para exportar em DOCX.
- Pedidos sempre numerados.
- Evite paragrafos longos e repeticao.

ESTRUTURA BASE MINIMA (sempre presente):
0. ENDERECAMENTO
1. QUALIFICACAO DAS PARTES
2. DOS FATOS
3. DO DIREITO
4. DOS PEDIDOS
5. DO VALOR DA CAUSA
6. DAS PROVAS
7. REQUERIMENTOS FINAIS
8. FECHAMENTO:
   "Termos em que, pede deferimento."
   Local e data: [PREENCHER]
   Assinatura e OAB: [PREENCHER]

REGRAS DE ADAPTACAO:
- Se houver secoes personalizadas em `estrutura_peticao`, priorize a ordem indicada.
- As secoes personalizadas complementam a estrutura base minima; nao a substituem.
- Se houver pedido de tutela de urgencia, inclua o subtopico "DA TUTELA DE URGENCIA" dentro de "DO DIREITO".
- Use os pedidos de `pedidos` e `pedidos_detalhados` sem criar pedidos nao informados.
- Considere os parametros finais (gratuidade, prioridade, audiencia) apenas quando informados.
- Trate `campos_area_especificos` como fonte prioritaria para especificidade tecnica da area do direito selecionada.
""".strip()


TIPO_ACAO_GUIDE: dict[str, str] = {
    "Indenizacao por danos morais": """
FOCO DA ACAO: RESPONSABILIDADE CIVIL / DANO MORAL
- Descrever conduta, dano e nexo causal com base estrita nos fatos informados.
- Fundamentar de forma generica e segura, sem citar base especifica nao fornecida.
- Nos pedidos, contemplar condenacao em danos morais apenas se constar nos dados.
""".strip(),
    "Cobranca": """
FOCO DA ACAO: COBRANCA
- Destacar origem da obrigacao, vencimento e inadimplemento.
- Organizar fatos financeiros de forma cronologica e objetiva.
- Nos pedidos, incluir principal e consectarios somente quando constarem nos dados.
""".strip(),
    "Obrigacao de fazer": """
FOCO DA ACAO: OBRIGACAO DE FAZER
- Evidenciar a obrigacao descumprida e a necessidade de cumprimento especifico.
- Se houver urgencia, justificar risco e utilidade da medida conforme os fatos.
- Multa diaria (astreintes) somente com [PREENCHER] quando faltar parametro.
""".strip(),
    "Rescisao contratual": """
FOCO DA ACAO: RESCISAO CONTRATUAL
- Explicar o contrato, o descumprimento e os efeitos praticos.
- Tratar resolucao contratual de forma generica, sem invencao de clausulas.
- Pedidos de devolucao/indenizacao apenas quando houver suporte nos dados.
""".strip(),
    "Alimentos": """
FOCO DA ACAO: ALIMENTOS
- Destacar necessidade, possibilidade e proporcionalidade com o que foi informado.
- Evitar fixar valor sem dado concreto; usar [PREENCHER] quando necessario.
- Pedidos devem contemplar fixacao provisoria/definitiva apenas se indicado no caso.
""".strip(),
    "Guarda e convivencia": """
FOCO DA ACAO: GUARDA E CONVIVENCIA
- Priorizar interesse da crianca/adolescente conforme os fatos narrados.
- Organizar pedido de guarda e regime de convivencia de modo objetivo.
- Nao criar fatos sobre risco, violencia ou alienacao sem informacao expressa.
""".strip(),
    "Divorcio": """
FOCO DA ACAO: DIVORCIO
- Manter redacao objetiva sobre dissolucao do vinculo.
- Tratar partilha, guarda, alimentos e nome conforme dados disponiveis.
- Quando faltar elemento essencial de partilha ou filhos, usar [PREENCHER].
""".strip(),
    "Usucapiao": """
FOCO DA ACAO: USUCAPIAO
- Descrever posse, lapso temporal e caracteristicas da ocupacao conforme informado.
- Nao presumir metragem, confrontantes ou matricula sem dados.
- Pontos registrarios ausentes devem ser marcados com [PREENCHER].
""".strip(),
    "Mandado de seguranca": """
FOCO DA ACAO: MANDADO DE SEGURANCA
- Destacar ato coator, autoridade e direito liquido e certo conforme os dados.
- Delimitar pedido liminar apenas quando houver elementos no caso.
- Nao inventar prova pre-constituida nao mencionada.
""".strip(),
    "Trabalhista - verbas rescisorias": """
FOCO DA ACAO: TRABALHISTA (VERBAS RESCISORIAS)
- Organizar narrativa contratual, ruptura e verbas postuladas.
- Nao inventar jornada, salario, datas ou parcelas.
- Pedidos devem respeitar estritamente as verbas informadas.
""".strip(),
    "Previdenciaria - concessao/revisao": """
FOCO DA ACAO: PREVIDENCIARIA
- Delimitar beneficio pretendido e razao de concessao/revisao.
- Nao criar tempo de contribuicao, DER, DIB ou CNIS nao informado.
- Campos tecnicos ausentes devem constar como [PREENCHER].
""".strip(),
    "Execucao": """
FOCO DA ACAO: EXECUCAO
- Explicitar titulo e inadimplemento conforme dados fornecidos.
- Evitar detalhar memoria de calculo sem elementos suficientes.
- Medidas executivas devem ser objetivas e lastreadas no que foi informado.
""".strip(),
    "Outro": """
FOCO DA ACAO: GENERICO
- Adaptar linguagem e estrutura ao caso concreto informado.
- Se a classe da acao estiver indefinida, manter [PREENCHER] para elementos essenciais.
""".strip(),
}


AREA_DIREITO_GUIDE: dict[str, str] = {
    "Civil": """
FOCO DA AREA: CIVIL
- Priorizar relacao obrigacional, responsabilidade civil ou tutela patrimonial conforme os fatos.
- Diferenciar claramente fatos, fundamentos e pedidos para evitar contradicoes.
""".strip(),
    "Consumidor": """
FOCO DA AREA: CONSUMIDOR
- Evidenciar vulnerabilidade do consumidor e falha na prestacao de produto/servico quando houver dados.
- Tratar inversao do onus da prova somente se pedida ou justificada pelos fatos.
""".strip(),
    "Trabalhista": """
FOCO DA AREA: TRABALHISTA
- Organizar narrativa contratual (admissao, funcao, jornada, ruptura) com base estrita nos dados.
- Delimitar pedidos de verbas sem criar rubricas ou valores nao informados.
""".strip(),
    "Previdenciario": """
FOCO DA AREA: PREVIDENCIARIO
- Delimitar com precisao o beneficio e os requisitos informados.
- Evitar inferencias tecnicas (DER/DIB/carencia) sem dados objetivos.
""".strip(),
    "Tributario": """
FOCO DA AREA: TRIBUTARIO
- Identificar o tributo, periodo e ato impugnado conforme dados disponiveis.
- Pedidos de repeticao/compensacao so quando houver base factual informada.
""".strip(),
    "Empresarial": """
FOCO DA AREA: EMPRESARIAL
- Destacar contexto negocial e impactos operacionais/financeiros do conflito.
- Evitar generalidades excessivas quando houver clausulas ou obrigacoes especificas informadas.
""".strip(),
    "Familia e Sucessoes": """
FOCO DA AREA: FAMILIA E SUCESSOES
- Preservar linguagem tecnica sensivel ao contexto familiar/sucessorio.
- Priorizar interesse de incapazes quando o caso envolver menores ou vulneraveis.
""".strip(),
    "Administrativo": """
FOCO DA AREA: ADMINISTRATIVO
- Delimitar ato administrativo, autoridade e ilegalidade alegada sem extrapolar os dados.
- Fundamentar pedidos de urgencia de modo objetivo, apenas quando houver suporte fatico.
""".strip(),
    "Outro": """
FOCO DA AREA: GENERICO
- Manter estrutura tecnica e adaptar a redacao ao objeto concreto informado no caso.
""".strip(),
}


def _normalizar_texto(valor: Any) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", texto).strip().lower()


def _valor_caminho(dados: dict[str, Any], *caminho: str, default: Any = "") -> Any:
    atual: Any = dados
    for chave in caminho:
        if not isinstance(atual, dict):
            return default
        if chave not in atual:
            return default
        atual = atual[chave]
    return atual


def _primeiro_texto(*valores: Any) -> str:
    for valor in valores:
        texto = str(valor or "").strip()
        if texto:
            return texto
    return ""


def _coletar_lista(valor: Any) -> list[str]:
    if valor is None:
        return []

    if isinstance(valor, (list, tuple, set)):
        itens_brutos = list(valor)
    else:
        texto = str(valor).replace("\r", "\n").strip()
        if not texto:
            return []
        if "\n" in texto:
            itens_brutos = texto.splitlines()
        elif ";" in texto:
            itens_brutos = texto.split(";")
        else:
            itens_brutos = [texto]

    itens: list[str] = []
    vistos: set[str] = set()
    for item in itens_brutos:
        texto = str(item or "").strip()
        texto = re.sub(r"^\s*(?:[-*]|\u2022)+", "", texto).strip()
        if not texto:
            continue
        chave = _normalizar_texto(texto)
        if chave in vistos:
            continue
        vistos.add(chave)
        itens.append(texto)
    return itens


def _coletar_tipo_acao(dados: dict[str, Any]) -> str:
    return _primeiro_texto(
        _valor_caminho(dados, "tipo_acao", default=""),
        _valor_caminho(dados, "contexto_processual", "tipo_acao", default=""),
        _valor_caminho(dados, "contexto_processual", "classe_acao", default=""),
        _valor_caminho(dados, "campos_area_especificos", "valores", "subtipo_familia", default=""),
        _valor_caminho(dados, "campos_area_especificos", "valores", "beneficio_pretendido", default=""),
    )


def _normalize_tipo_acao(tipo: str | None) -> str:
    if not tipo:
        return "Outro"

    chave = _normalizar_texto(tipo)
    if not chave:
        return "Outro"

    regras: list[tuple[tuple[str, ...], str]] = [
        (("indeniz", "moral"), "Indenizacao por danos morais"),
        (("cobranc",), "Cobranca"),
        (("obrigacao", "fazer"), "Obrigacao de fazer"),
        (("rescis", "contrat"), "Rescisao contratual"),
        (("aliment",), "Alimentos"),
        (("guarda",), "Guarda e convivencia"),
        (("convivencia",), "Guarda e convivencia"),
        (("divor",), "Divorcio"),
        (("usucap",), "Usucapiao"),
        (("mandado", "segur"), "Mandado de seguranca"),
        (("trabalh", "rescis"), "Trabalhista - verbas rescisorias"),
        (("rescisor",), "Trabalhista - verbas rescisorias"),
        (("previd",), "Previdenciaria - concessao/revisao"),
        (("aposent",), "Previdenciaria - concessao/revisao"),
        (("auxilio",), "Previdenciaria - concessao/revisao"),
        (("pensao",), "Previdenciaria - concessao/revisao"),
        (("bpc",), "Previdenciaria - concessao/revisao"),
        (("loas",), "Previdenciaria - concessao/revisao"),
        (("execu",), "Execucao"),
    ]

    for termos, rotulo in regras:
        if all(termo in chave for termo in termos):
            return rotulo

    for nome in TIPO_ACAO_GUIDE:
        if _normalizar_texto(nome) == chave:
            return nome

    return "Outro"


def _coletar_area_direito(dados: dict[str, Any]) -> str:
    return _primeiro_texto(
        _valor_caminho(dados, "contexto_processual", "area_direito", default=""),
        _valor_caminho(dados, "area_direito", default=""),
        _valor_caminho(dados, "campos_area_especificos", "area", default=""),
    )


def _normalize_area_direito(area: str | None) -> str:
    if not area:
        return "Outro"

    chave = _normalizar_texto(area)
    if not chave:
        return "Outro"

    for nome in AREA_DIREITO_GUIDE:
        if _normalizar_texto(nome) == chave:
            return nome

    aliases: list[tuple[tuple[str, ...], str]] = [
        (("civil",), "Civil"),
        (("consum",), "Consumidor"),
        (("trabalh",), "Trabalhista"),
        (("previd",), "Previdenciario"),
        (("tribut",), "Tributario"),
        (("empres",), "Empresarial"),
        (("famil",), "Familia e Sucessoes"),
        (("sucess",), "Familia e Sucessoes"),
        (("administr",), "Administrativo"),
    ]
    for termos, area_norm in aliases:
        if all(termo in chave for termo in termos):
            return area_norm

    return "Outro"


def _inferir_tipo_acao_por_area(area_norm: str) -> str:
    mapa = {
        "Trabalhista": "Trabalhista - verbas rescisorias",
        "Previdenciario": "Previdenciaria - concessao/revisao",
    }
    return mapa.get(area_norm, "Outro")


def _to_bool(valor: Any) -> bool:
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return valor != 0
    if isinstance(valor, str):
        return _normalizar_texto(valor) in {"1", "true", "sim", "yes", "y", "on"}
    return False


def _formatar_lista(itens: list[str], fallback: str) -> str:
    if not itens:
        return fallback
    return " | ".join(itens)


def _resumir_campos_area(campos_area: Any) -> tuple[str, str]:
    if not isinstance(campos_area, dict):
        return "", "nenhum informado"

    area = _primeiro_texto(campos_area.get("area", ""))
    valores_raw = campos_area.get("valores", {})
    rotulos_raw = campos_area.get("rotulos", {})
    if not isinstance(valores_raw, dict):
        return area, "nenhum informado"

    pares: list[str] = []
    for campo_id, valor in valores_raw.items():
        if isinstance(valor, list):
            valor_texto = ", ".join(str(item).strip() for item in valor if str(item).strip())
        else:
            valor_texto = str(valor).strip()

        if not valor_texto:
            continue

        if isinstance(rotulos_raw, dict):
            rotulo = str(rotulos_raw.get(campo_id, campo_id))
        else:
            rotulo = str(campo_id)
        pares.append(f"{rotulo}: {valor_texto}")

    return area, _formatar_lista(pares, "nenhum informado")


def _montar_bloco_personalizacao(dados: dict[str, Any], tipo_raw: str, tipo_norm: str) -> str:
    area = _primeiro_texto(
        _valor_caminho(dados, "contexto_processual", "area_direito", default=""),
        _valor_caminho(dados, "area_direito", default=""),
    )
    rito = _primeiro_texto(
        _valor_caminho(dados, "contexto_processual", "rito", default=""),
        _valor_caminho(dados, "rito", default=""),
    )
    comarca = _primeiro_texto(
        _valor_caminho(dados, "contexto_processual", "comarca_uf", default=""),
        _valor_caminho(dados, "comarca_uf", default=""),
    )
    foro_vara = _primeiro_texto(
        _valor_caminho(dados, "contexto_processual", "foro_vara", default=""),
        _valor_caminho(dados, "foro_vara", default=""),
    )

    estrutura = _valor_caminho(dados, "estrutura_peticao", default={})
    if not isinstance(estrutura, dict):
        estrutura = {}

    secoes_sugeridas = _coletar_lista(estrutura.get("secoes_sugeridas", []))
    secoes_extras = _coletar_lista(estrutura.get("secoes_extras", []))
    nivel_detalhamento = _primeiro_texto(estrutura.get("nivel_detalhamento", ""), "Padrao")

    fundamentacao = _valor_caminho(dados, "fundamentacao", default={})
    if not isinstance(fundamentacao, dict):
        fundamentacao = {}

    temas_juridicos = _coletar_lista(fundamentacao.get("temas_juridicos", []))
    fundamentos_legais = _coletar_lista(fundamentacao.get("fundamentos_legais", []))

    narrativa = _valor_caminho(dados, "narrativa", default={})
    if not isinstance(narrativa, dict):
        narrativa = {}
    provas = _coletar_lista(narrativa.get("provas_documentos", []))

    pedidos = _coletar_lista(_valor_caminho(dados, "pedidos_detalhados", "lista_final", default=[]))
    if not pedidos:
        pedidos = _coletar_lista(_valor_caminho(dados, "pedidos", default=[]))

    parametros = _valor_caminho(dados, "parametros_finais", default={})
    if not isinstance(parametros, dict):
        parametros = {}

    tutela_urgencia = _to_bool(parametros.get("tutela_urgencia"))
    justica_gratuita = _to_bool(parametros.get("justica_gratuita"))
    prioridade = _to_bool(parametros.get("prioridade_tramitacao"))
    audiencia = _to_bool(parametros.get("audiencia_conciliacao"))

    observacoes = _primeiro_texto(
        _valor_caminho(dados, "observacoes_estrategicas", default=""),
        _valor_caminho(dados, "observacoes", default=""),
    )
    area_campos, resumo_campos_area = _resumir_campos_area(
        _valor_caminho(dados, "campos_area_especificos", default={})
    )

    linhas = [
        f"- Tipo de acao informado: {tipo_raw or '[PREENCHER]'}",
        f"- Tipo de acao classificado para orientacao: {tipo_norm}",
        f"- Area do direito: {area or '[PREENCHER]'}",
        f"- Campos especificos da area ({area_campos or area or '[PREENCHER]'}): {resumo_campos_area}",
        f"- Rito/procedimento: {rito or '[PREENCHER]'}",
        f"- Comarca: {comarca or '[PREENCHER]'}",
        f"- Foro/vara: {foro_vara or '[PREENCHER]'}",
        f"- Nivel de detalhamento desejado: {nivel_detalhamento}",
        f"- Ordem de secoes sugeridas: {_formatar_lista(secoes_sugeridas, 'usar estrutura base minima')}",
        f"- Secoes extras solicitadas: {_formatar_lista(secoes_extras, 'nenhuma')}",
        f"- Temas juridicos para priorizar: {_formatar_lista(temas_juridicos, 'nao informados')}",
        f"- Fundamentos legais informados: {_formatar_lista(fundamentos_legais, 'nao informados')}",
        f"- Pedidos a contemplar: {_formatar_lista(pedidos, 'nao informados')}",
        f"- Provas informadas: {_formatar_lista(provas, 'nao informadas')}",
        f"- Tutela de urgencia: {'sim' if tutela_urgencia else 'nao'}",
        f"- Justica gratuita: {'sim' if justica_gratuita else 'nao'}",
        f"- Prioridade de tramitacao: {'sim' if prioridade else 'nao'}",
        f"- Audiencia de conciliacao: {'sim' if audiencia else 'nao'}",
    ]

    if observacoes:
        linhas.append(f"- Observacoes estrategicas do usuario: {observacoes}")

    return "\n".join(linhas)


def montar_prompt(dados: dict[str, Any]) -> str:
    dados = dados if isinstance(dados, dict) else {}

    area_raw = _coletar_area_direito(dados)
    area_norm = _normalize_area_direito(area_raw)

    tipo_acao_raw = _coletar_tipo_acao(dados)
    tipo_acao = _normalize_tipo_acao(tipo_acao_raw)
    if tipo_acao == "Outro":
        tipo_inferido = _inferir_tipo_acao_por_area(area_norm)
        if tipo_inferido != "Outro":
            tipo_acao = tipo_inferido

    guia = TIPO_ACAO_GUIDE.get(tipo_acao, TIPO_ACAO_GUIDE["Outro"])
    guia_area = AREA_DIREITO_GUIDE.get(area_norm, AREA_DIREITO_GUIDE["Outro"])
    bloco_personalizacao = _montar_bloco_personalizacao(dados, tipo_acao_raw, tipo_acao)

    dados_json = json.dumps(dados, ensure_ascii=False, indent=2)
    return f"""{PROMPT_BASE}

ORIENTACAO ESPECIFICA PELA AREA DO DIREITO:
Area: {area_norm}
{guia_area}

ORIENTACAO ESPECIFICA PELO TIPO DE ACAO:
Tipo: {tipo_acao}
{guia}

INSTRUCOES DE PERSONALIZACAO DO CASO:
{bloco_personalizacao}

DADOS DO CASO (JSON):
{dados_json}

TAREFA:
Gere a peticao completa seguindo as regras criticas, a estrutura base minima e as personalizacoes acima.

CHECKLIST FINAL (auto-validacao antes de responder):
- Nao inventar fatos/leis/documentos.
- Usar [PREENCHER] quando faltar dado essencial.
- Nao trocar dado existente por [PREENCHER].
- Incluir apenas provas informadas ou formula generica "se cabivel" quando nao houver provas.
- Pedidos enumerados e alinhados ao JSON.
- Retornar somente o texto final da peticao (sem markdown e sem explicacoes adicionais).
"""


# Backward-compatible aliases for earlier app versions.
def build_case_payload(**kwargs: Any) -> dict[str, Any]:
    return dict(kwargs)


def build_prompt(case_payload: dict[str, Any]) -> str:
    return montar_prompt(case_payload)
