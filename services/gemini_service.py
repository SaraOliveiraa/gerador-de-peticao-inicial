from __future__ import annotations

import os

from google import genai

DEFAULT_MODEL = "gemini-2.5-flash"


# Define um tipo de erro específico para falhas de integração com o Gemini.
class GeminiServiceError(RuntimeError):
    """Raised when Gemini generation fails."""


# Envia o prompt ao Gemini e retorna o texto gerado, com tratamento de erros de cota e autenticação.
def gerar_peticao(prompt: str, model: str = DEFAULT_MODEL, api_key: str | None = None) -> str:
    """
    Gera texto usando Gemini.
    Requer GEMINI_API_KEY ou GOOGLE_API_KEY no ambiente.
    """
    key = (api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not key:
        raise GeminiServiceError("Configure GEMINI_API_KEY (ou GOOGLE_API_KEY) no ambiente.")

    chosen_model = (model or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL).strip()

    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=chosen_model,
            contents=prompt,
        )
    except Exception as exc:  # pragma: no cover
        raw_msg = str(exc)
        msg_lower = raw_msg.lower()
        if "resource_exhausted" in msg_lower or "quota" in msg_lower or "429" in msg_lower:
            raise GeminiServiceError(
                "Cota da API Gemini esgotada (HTTP 429 RESOURCE_EXHAUSTED). "
                "No Google AI Studio/Google Cloud, habilite faturamento no projeto da chave "
                "ou use outra chave/projeto com cota disponivel. "
                "Tambem pode testar outro modelo via GEMINI_MODEL no .env "
                "(ex.: gemini-2.5-flash)."
            ) from exc
        raise GeminiServiceError(f"Falha ao chamar Gemini ({chosen_model}): {raw_msg}") from exc

    text = (response.text or "").strip()
    if not text:
        raise GeminiServiceError("Gemini nao retornou texto.")
    return text


# Backward-compatible alias used by earlier app versions.
# Mantém compatibilidade com chamadas antigas que usam o nome em inglês.
def generate_petition(prompt: str, api_key: str | None = None, model: str | None = None) -> str:
    chosen_model = (model or DEFAULT_MODEL).strip()
    return gerar_peticao(prompt=prompt, model=chosen_model, api_key=api_key)
