from __future__ import annotations

import textwrap
from typing import Iterable


def _normalizar_linha_pdf(texto: str) -> str:
    # PDF basico com Helvetica usa WinAnsi/latin-1.
    return (texto or "").encode("latin-1", "replace").decode("latin-1")


def _escapar_texto_pdf(texto: str) -> str:
    texto = _normalizar_linha_pdf(texto)
    return (
        texto.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _quebrar_linhas(texto: str, largura: int = 95) -> list[str]:
    linhas: list[str] = []
    for linha in (texto or "").splitlines():
        limpa = linha.strip()
        if not limpa:
            linhas.append("")
            continue
        linhas.extend(textwrap.wrap(limpa, width=largura) or [""])
    return linhas


def _dividir_paginas(linhas: Iterable[str], max_linhas_por_pagina: int = 52) -> list[list[str]]:
    paginas: list[list[str]] = []
    atual: list[str] = []

    for linha in linhas:
        atual.append(linha)
        if len(atual) >= max_linhas_por_pagina:
            paginas.append(atual)
            atual = []

    if atual or not paginas:
        paginas.append(atual)

    return paginas


def _montar_conteudo_pagina(linhas: list[str], primeira_pagina: bool, titulo: str) -> bytes:
    comandos: list[str] = ["BT"]
    y_inicial = 800

    if primeira_pagina:
        comandos.append("/F1 16 Tf")
        comandos.append(f"1 0 0 1 40 {y_inicial} Tm")
        comandos.append(f"({_escapar_texto_pdf(titulo)}) Tj")
        comandos.append("/F1 12 Tf")
        comandos.append("0 -22 Td")
    else:
        comandos.append("/F1 12 Tf")
        comandos.append(f"1 0 0 1 40 {y_inicial} Tm")

    if not linhas:
        comandos.append("( ) Tj")
    else:
        for idx, linha in enumerate(linhas):
            if idx > 0:
                comandos.append("0 -14 Td")
            comandos.append(f"({_escapar_texto_pdf(linha)}) Tj")

    comandos.append("ET")
    return "\n".join(comandos).encode("latin-1", "replace")


def texto_para_pdf_bytes(titulo: str, texto: str) -> bytes:
    titulo_pdf = _normalizar_linha_pdf(titulo or "PETICAO INICIAL")
    linhas = _quebrar_linhas(texto or "")
    paginas_linhas = _dividir_paginas(linhas)

    objetos: list[bytes | None] = [None]
    objetos.append(b"<< /Type /Catalog /Pages 2 0 R >>")  # 1
    objetos.append(b"<< /Type /Pages /Count 0 /Kids [] >>")  # 2 (atualizado depois)
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")  # 3

    kids_refs: list[str] = []
    pagina_base = 4
    for idx, linhas_pagina in enumerate(paginas_linhas):
        pagina_obj = pagina_base + idx * 2
        conteudo_obj = pagina_obj + 1
        kids_refs.append(f"{pagina_obj} 0 R")

        stream = _montar_conteudo_pagina(
            linhas=linhas_pagina,
            primeira_pagina=idx == 0,
            titulo=titulo_pdf,
        )
        corpo_stream = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream"
        )
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {conteudo_obj} 0 R >>".encode("latin-1")
        )
        objetos.append(corpo_stream)

    objetos[2] = f"<< /Type /Pages /Count {len(paginas_linhas)} /Kids [{' '.join(kids_refs)}] >>".encode("latin-1")

    pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0] * len(objetos)

    for obj_num in range(1, len(objetos)):
        corpo = objetos[obj_num] or b""
        offsets[obj_num] = len(pdf)
        pdf += f"{obj_num} 0 obj\n".encode("latin-1")
        pdf += corpo + b"\n"
        pdf += b"endobj\n"

    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(objetos)}\n".encode("latin-1")
    pdf += b"0000000000 65535 f \n"
    for obj_num in range(1, len(objetos)):
        pdf += f"{offsets[obj_num]:010d} 00000 n \n".encode("latin-1")

    pdf += f"trailer\n<< /Size {len(objetos)} /Root 1 0 R >>\n".encode("latin-1")
    pdf += f"startxref\n{xref_pos}\n%%EOF".encode("latin-1")
    return pdf


# Backward-compatible alias used by earlier app versions.
def build_pdf_bytes(text: str, title: str = "PETICAO INICIAL") -> bytes:
    return texto_para_pdf_bytes(titulo=title, texto=text)

