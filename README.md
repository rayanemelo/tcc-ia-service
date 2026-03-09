Instalar as dependencias:
```pip install -r requirements.txt```


Comando para rodar localmente:
```uvicorn app.main:app --reload```

## LM Studio

1. No LM Studio, carregue um modelo vision-language e inicie o servidor local.
2. Configure variaveis de ambiente:
```powershell
$env:LMSTUDIO_BASE_URL="http://127.0.0.1:1234"
$env:LMSTUDIO_CHAT_PATH="/v1/chat/completions"
$env:LMSTUDIO_MODEL="qwen/qwen3-vl-8b"
$env:LMSTUDIO_API_KEY="lm-studio"
```
3. Rode a API normalmente:
```powershell
uvicorn app.main:app --reload
```

## Endpoint `/analyze`

Payload (JSON):

```json
{
  "imageUrl": "https://exemplo.com/foto.jpg",
  "userLocation": { "latitude": -29.649, "longitude": -50.575 },
  "mapLocation": { "latitude": -29.650, "longitude": -50.574 }
}
```

Campos novos na resposta:

- `exif_analysis`: metadados EXIF relevantes e deteccao de foto antiga.
- `geo_consistency`: distancias entre usuario, ponto no mapa e GPS da foto (EXIF).
- `veracity_score`: score final de veracidade (0 a 1).
- `veracity_signals`: detalhamento por componente (`visual_score`, `temporal_score`, `geo_score`).
