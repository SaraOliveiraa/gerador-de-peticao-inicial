from __future__ import annotations

import json
from typing import Any

PROMPT_SISTEMA = """
Voce e um assistente juridico. Gere uma PETICAO INICIAL em portugues do Brasil, com linguagem formal.
Regras:
- NAO invente documentos, numeros, datas ou jurisprudencia especifica.
- Se faltar dado essencial, marque como [PREENCHER].
- Estruture exatamente com estes titulos:
  I. DOS FATOS
  II. DO DIREITO
  III. DOS PEDIDOS
  IV. DO VALOR DA CAUSA
  V. REQUERIMENTOS FINAIS
- Ao final, inclua: "Termos em que, pede deferimento.", local, data e assinatura.
""".strip()


def montar_prompt(dados: dict[str, Any]) -> str:
    dados_json = json.dumps(dados, ensure_ascii=False, indent=2)
    return f"""{PROMPT_SISTEMA}

DADOS DO CASO (JSON):
{dados_json}

Gere a peticao completa com base apenas nesses dados.
"""


# Backward-compatible aliases for earlier app versions.
def build_case_payload(**kwargs: Any) -> dict[str, Any]:
    return dict(kwargs)


def build_prompt(case_payload: dict[str, Any]) -> str:
    return montar_prompt(case_payload)
