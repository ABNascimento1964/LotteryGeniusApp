import os
import time
import logging
from typing import Optional, Dict, Any

import requests
from flask import Flask, jsonify

# -----------------------------------------------------------------------------
# Configuração básica
# -----------------------------------------------------------------------------
app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

CAIXA_LOTOFACIL_URL = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"

# Cache simples em memória para não bater na API toda hora
_last_result_cache: Dict[str, Any] = {}
CACHE_TTL_SECONDS = 60  # 1 minuto de cache


# -----------------------------------------------------------------------------
# Funções auxiliares
# -----------------------------------------------------------------------------
def _get_headers() -> Dict[str, str]:
    """
    Headers para parecer um navegador normal.
    Isso ajuda a evitar 403 da API da Caixa.
    """
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://loterias.caixa.gov.br/",
        "Connection": "keep-alive",
    }


def fetch_lotofacil_from_caixa() -> Dict[str, Any]:
    """
    Busca o último resultado da Lotofácil diretamente da API da Caixa.
    Faz algumas tentativas em caso de erro temporário.
    Levanta exceção em caso de falha.
    """
    session = requests.Session()
    retries = 3

    for attempt in range(1, retries + 1):
        try:
            logging.info(f"Tentando buscar Lotofácil na Caixa (tentativa {attempt}/{retries})")
            resp = session.get(
                CAIXA_LOTOFACIL_URL,
                headers=_get_headers(),
                timeout=10,
            )

            # Se der 403, loga bem explícito
            if resp.status_code == 403:
                logging.error(
                    "403 Forbidden ao acessar a API da Caixa. "
                    "Provavelmente bloqueio por IP/servidor. "
                    "Tente usar proxy residencial ou outro provedor de hospedagem."
                )
                raise RuntimeError("Acesso proibido (403) pela API da Caixa.")

            resp.raise_for_status()

            data = resp.json()
            logging.info("Resultado da Lotofácil obtido com sucesso na API da Caixa.")
            return data

        except requests.exceptions.RequestException as e:
            logging.warning(f"Erro ao acessar API da Caixa: {e}")
            if attempt == retries:
                raise
            time.sleep(2)

    raise RuntimeError("Falha ao buscar resultado da Lotofácil após várias tentativas.")


def get_lotofacil_result() -> Dict[str, Any]:
    """
    Retorna o último resultado da Lotofácil, com cache simples em memória.
    """
    now = time.time()

    # Usa cache se ainda estiver válido
    if (
        _last_result_cache
        and (now - _last_result_cache.get("timestamp", 0)) < CACHE_TTL_SECONDS
    ):
        return _last_result_cache["data"]

    # Sem cache ou expirado: busca na API
    data = fetch_lotofacil_from_caixa()
    _last_result_cache["data"] = data
    _last_result_cache["timestamp"] = now
    return data


# -----------------------------------------------------------------------------
# Rotas
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    """
    Rota principal – só pra saber que o serviço está no ar.
    """
    return jsonify(
        {
            "status": "ok",
            "message": "LotteryGeniusApp está rodando 🚀",
            "endpoints": {
                "ultimo_resultado_lotofacil": "/lotofacil/ultimo",
            },
        }
    )


@app.route("/lotofacil/ultimo")
def lotofacil_ultimo():
    """
    Retorna o último resultado da Lotofácil em JSON.
    """
    try:
        data = get_lotofacil_result()
        return jsonify(
            {
                "success": True,
                "data": data,
            }
        )
    except Exception as e:
        logging.exception("Erro ao obter último resultado da Lotofácil.")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                }
            ),
            500,
        )


# -----------------------------------------------------------------------------
# Main (para rodar localmente ou em produção)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
