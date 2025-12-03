import os
import time
import logging
from typing import Dict, Any
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

# Cache simples
_last_result_cache: Dict[str, Any] = {}
CACHE_TTL_SECONDS = 60  # 1 minuto


# -----------------------------------------------------------------------------
# Headers necessários para evitar 403 na API da Caixa
# -----------------------------------------------------------------------------
def _get_headers() -> Dict[str, str]:
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


# -----------------------------------------------------------------------------
# Busca dados da Lotofácil na Caixa
# -----------------------------------------------------------------------------
def fetch_lotofacil_from_caixa() -> Dict[str, Any]:
    session = requests.Session()
    retries = 3

    for attempt in range(1, retries + 1):
        try:
            logging.info(f"Tentando buscar Lotofácil (tentativa {attempt}/{retries})")
            resp = session.get(
                CAIXA_LOTOFACIL_URL,
                headers=_get_headers(),
                timeout=10,
            )

            if resp.status_code == 403:
                raise RuntimeError("Acesso proibido (403) pela API da Caixa.")

            resp.raise_for_status()
            data = resp.json()
            return data

        except Exception as e:
            logging.warning(f"Erro: {e}")
            if attempt == retries:
                raise
            time.sleep(2)

    raise RuntimeError("Falha ao buscar resultado da Lotofácil.")


# -----------------------------------------------------------------------------
# Cache
# -----------------------------------------------------------------------------
def get_lotofacil_result() -> Dict[str, Any]:
    now = time.time()

    if (
        _last_result_cache
        and (now - _last_result_cache.get("timestamp", 0)) < CACHE_TTL_SECONDS
    ):
        return _last_result_cache["data"]

    data = fetch_lotofacil_from_caixa()
    _last_result_cache["data"] = data
    _last_result_cache["timestamp"] = now
    return data


# -----------------------------------------------------------------------------
# Rotas
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    return jsonify(
        {
            "status": "ok",
            "message": "LotteryGeniusApp está rodando 🚀",
            "endpoints": {
                "lotofacil": "/lotofacil/ultimo",
                "ping": "/ping"
            },
        }
    )


@app.route("/lotofacil/ultimo")
def lotofacil_ultimo():
    try:
        data = get_lotofacil_result()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logging.exception("Erro ao obter Lotofácil.")
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------------------------------------------------------
# Rota de teste
# -----------------------------------------------------------------------------
@app.route("/ping")
def ping():
    return "pong - app está rodando"


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
