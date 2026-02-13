# Gerador de Peticao Inicial (Streamlit + Gemini)

MVP com:
- formulario de cliente/reu + fatos + pedidos;
- chamada Gemini via SDK `google-genai`;
- preview do texto;
- download em `.docx`.

## Requisitos
- Python 3.10+

## Instalacao
```bash
pip install -r requirements.txt
```

## Chave da API
1. Copie `.env.example` para `.env`.
2. Preencha pelo menos uma variavel:
```env
GEMINI_API_KEY="COLE_SUA_CHAVE_AQUI"
```
Tambem funciona com `GOOGLE_API_KEY`.

## Execucao
```bash
streamlit run app.py
```

## Estrutura
```text
peticao-streamlit/
  app.py
  services/
    gemini_service.py
    prompt_builder.py
  exporters/
    docx_exporter.py
  .env.example
  requirements.txt
```
