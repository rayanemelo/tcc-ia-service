"""Constantes de negócio, pesos e prompts usados no pipeline de classificação."""

from app.config import (
    MAX_IMAGE_AGE_HOURS,
)

# Tamanho maximo aceito para o download da imagem (8 MB).
MAX_IMAGE_BYTES = 8 * 1024 * 1024
# Timeout de rede para baixar a imagem enviada pelo usuario.
IMAGE_DOWNLOAD_TIMEOUT_SECONDS = 10
# Nota minima para aprovar automaticamente a evidencia.
APPROVE_THRESHOLD = 0.85
# Faixa intermediaria que exige revisao manual humana.
MANUAL_REVIEW_THRESHOLD = 0.60
# Lado maximo (largura/altura) da imagem enviada ao VLM.
MAX_VLM_IMAGE_SIDE = 1024
# Qualidade JPEG usada na compressao antes de enviar ao modelo.
VLM_JPEG_QUALITY = 85

# Valor neutro usado quando um sinal nao pode ser calculado.
NEUTRAL_SCORE = 0.5
# Pesos da composicao de veracidade (soma = 1.0).
VERACITY_VISUAL_WEIGHT = 0.50
VERACITY_TEMPORAL_WEIGHT = 0.20
VERACITY_GEO_WEIGHT = 0.30
# Pesos da nota final (confianca de alagamento + veracidade global).
FINAL_SCORE_FLOOD_WEIGHT = 0.55
FINAL_SCORE_VERACITY_WEIGHT = 0.45

# Reexporta limite de idade para manter semantica de dominio em um unico modulo.
MAX_ALLOWED_IMAGE_AGE_HOURS = MAX_IMAGE_AGE_HOURS

# Conversao da qualidade da evidencia para nota numerica.
EVIDENCE_QUALITY_SCORE = {
    "high": 1.0,
    "medium": 0.7,
    "low": 0.4,
}

# Prompt de sistema: define o papel do modelo e o formato estrito de resposta JSON.
SYSTEM_PROMPT = (
    "Você é um especialista em análise forense visual e monitoramento de alagamentos urbanos. "
    "Sua tarefa é analisar imagens enviadas por usuários para verificar autenticidade da imagem, presença de alagamento e possíveis tentativas de fraude ou manipulação."
    "Analise cuidadosamente a imagem considerando as seguintes dimensões: "
    "1. AUTENTICIDADE DA IMAGEM "
    "Verifique se a imagem parece ser uma fotografia real de um ambiente físico. "
    "Sinais de imagem inválida incluem: "
    "- screenshot de aplicativo ou rede social "
    "- foto exibida em tela de celular, computador ou televisão "
    "- foto de outra foto impressa "
    "- imagem claramente gerada por computador, ilustração ou renderização 3D "
    "- presença de interface de aplicativo, barras de status ou menus."
    "2. MANIPULAÇÃO DIGITAL OU MONTAGEM "
    "Procure sinais de edição ou manipulação visual, como: "
    "- iluminação inconsistente entre objetos "
    "- sombras incompatíveis com a direção da luz "
    "- brilho diferente em partes da imagem "
    "- bordas recortadas indicando possível colagem "
    "- halos ou contornos artificiais em objetos "
    "- sinais de que um objeto foi retirado de outra foto e inserido na imagem "
    "- distorções no fundo da imagem "
    "- inconsistências de perspectiva "
    "- texturas desalinhadas (exemplo: azulejos ou grades desencontrados) "
    "- padrões repetidos artificialmente "
    "- áreas pixeladas ou com resolução diferente do restante da imagem "
    "- artefatos de compressão inconsistentes."
    "3. SINAIS DE IMAGEM GERADA POR IA "
    "Observe possíveis artefatos típicos de imagens geradas por IA, como: "
    "- objetos deformados ou incompletos "
    "- padrões repetitivos ou artificiais "
    "- texto ilegível em placas ou sinais "
    "- reflexos impossíveis ou inconsistentes "
    "- estruturas urbanas fisicamente impossíveis "
    "- incoerência entre objetos e cenário."
    "4. QUALIDADE DA EVIDÊNCIA "
    "Avalie se a imagem possui qualidade suficiente para análise confiável. "
    "Considere fatores como: "
    "- baixa resolução "
    "- imagem borrada "
    "- iluminação insuficiente ou muito escura "
    "- câmera obstruída por chuva, vidro ou sujeira "
    "- enquadramento que não mostra claramente o local."
    "Classifique a qualidade da evidência como: "
    "- high: imagem clara, com boa visibilidade do local "
    "- medium: imagem parcialmente clara mas com algumas limitações "
    "- low: imagem difícil de analisar."
    "5. DETECÇÃO DE ALAGAMENTO "
    "Avalie a presença de água acumulada no ambiente urbano."
    "Classifique mentalmente o nível de alagamento com base nos seguintes critérios: "
    "LEVE: "
    "- água cobrindo apenas a rua "
    "- lâmina de água rasa "
    "- trânsito ainda possível."
    "MODERADO: "
    "- água invadindo calçadas "
    "- água próxima ou entrando em imóveis "
    "- água cobrindo parte significativa das rodas dos veículos "
    "- trânsito difícil ou arriscado."
    "INTERDITADO: "
    "- rua ou área completamente submersa "
    "- veículos parcialmente submersos "
    "- grande volume de água "
    "- impossível transitar com segurança."
    "NÃO CONSIDERAR COMO ALAGAMENTO: "
    "- pequenas poças isoladas "
    "- chão apenas molhado "
    "- água acumulada apenas na sarjeta."
    "6. COBERTURA DE ÁGUA "
    "Avalie aproximadamente quanto da área visível está coberta por água: "
    "- none: nenhuma água visível "
    "- small: pequenas áreas com água "
    "- medium: parte significativa da rua coberta "
    "- large: grande parte da área visível coberta."
    "7. CONSISTÊNCIA FÍSICA DA CENA "
    "Avalie se a cena parece fisicamente plausível considerando: "
    "- continuidade da lâmina d'água "
    "- reflexos naturais "
    "- interação da água com objetos "
    "- coerência com inclinação da rua."
    "8. PROBABILIDADE DE MANIPULAÇÃO "
    "Estime a probabilidade de manipulação digital com base nos sinais observados."
    "9. PROBABILIDADE DE IMAGEM GERADA POR IA "
    "Estime a probabilidade de que a imagem tenha sido gerada por inteligência artificial."
    "Evite marcar fraude apenas por baixa qualidade da imagem. "
    "Fraude deve ser marcada apenas se houver sinais claros de manipulação ou tentativa de engano."
    "Se algum campo não puder ser determinado com confiança, forneça a melhor estimativa baseada nas evidências visuais."
    "Responda SOMENTE com JSON válido neste formato exato: "
    "{"
    '"image_valid": true|false, '
    '"flood_detected": true|false, '
    '"flood_level": "none|leve|moderado|interditado", '
    '"fraud_suspected": true|false, '
    '"confidence": 0.0-1.0, '
    '"evidence_quality": "high|medium|low", '
    '"water_coverage": "none|small|medium|large", '
    '"scene_consistency": 0.0-1.0, '
    '"manipulation_probability": 0.0-1.0, '
    '"ai_generated_probability": 0.0-1.0, '
    '"reason": "explicação curta e objetiva"'
    "}"
)

# Prompt de usuario: reforca que a resposta deve ser somente JSON.
USER_PROMPT = (
    "Analise cuidadosamente a imagem enviada. "
    "Avalie autenticidade, presença de alagamento, possíveis manipulações e qualidade da evidência. "
    "Responda apenas com JSON válido no formato definido. "
    "Não use markdown e não inclua explicações adicionais."
)
