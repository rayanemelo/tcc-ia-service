Instalar as dependencias:
```pip install -r requirements.txt```


Comando para rodar localmente:
```uvicorn app.main:app --reload```

## Provedores de IA

O servico suporta dois modos:

- `AI_PROVIDER=transformers` (padrao): roda o modelo Hugging Face direto no backend.
- `AI_PROVIDER=lmstudio`: usa um modelo servido pelo LM Studio via API local.

### Exemplo LM Studio

1. No LM Studio, carregue um modelo vision-language e inicie o servidor local.
2. Configure variaveis de ambiente:
```powershell
$env:AI_PROVIDER="lmstudio"
$env:LMSTUDIO_BASE_URL="http://127.0.0.1:1234"
$env:LMSTUDIO_CHAT_PATH="/v1/chat/completions"
$env:LMSTUDIO_MODEL="qwen/qwen3-vl-8b"
```
3. Rode a API normalmente:
```powershell
uvicorn app.main:app --reload
```
