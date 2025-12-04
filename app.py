import time
import logging
from typing import Dict, Any, List

import requests
from flask import Flask, jsonify

# -----------------------------------------------------------------------------
# Configuração básica do Flask
# -----------------------------------------------------------------------------
app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# -----------------------------------------------------------------------------
# Fonte ÚNICA de dados: JSON público da Lotofácil no GitHub
# Projeto: guilhermeasn/loteria.json
# -----------------------------------------------------------------------------
GITHUB_LOTOFACIL_URL = (
    "https://raw.githubusercontent.com/"
    "guilhermeasn/loteria.json/master/data/lotofacil.json"
)

# Cache simples em memória
_last_result_cache: Dict[str, Any] = {}
CACHE_TTL_SECONDS = 60  # 1 minuto


# -----------------------------------------------------------------------------
# Busca o último resultado da Lotofácil no JSON público
# -----------------------------------------------------------------------------
def fetch_lotofacil_from_github() -> Dict[str, Any]:
    """
    Lê TODOS os resultados da Lotofácil no JSON lotofacil.json
    e pega o concurso mais recente.

    Formato do JSON (exemplo):
        {
          "3551": [1, 2, 3, ..., 25],
          "3550": [...],
          ...
        }
    """
    logging.info(f"[GITHUB] Buscando JSON em {GITHUB_LOTOFACIL_URL}")
    resp = requests.get(GITHUB_LOTOFACIL_URL, timeout=10)
    logging.info(f"[GITHUB] Status code: {resp.status_code}")
    resp.raise_for_status()

    data = resp.json()

    if not isinstance(data, dict) or not data:
        raise RuntimeError("JSON da loteria.json veio vazio ou em formato inesperado.")

    # Pega o maior número de concurso (último sorteio)
    concursos_numericos: List[int] = [int(k) for k in data.keys()]
    ultimo_concurso = max(concursos_numericos)

    dezenas_raw = data[str(ultimo_concurso)]  # lista de ints ou strings
    dezenas = [f"{int(d):02d}" for d in dezenas_raw]  # normaliza para "01", "02", ...

    return {
        "source": "github-loteria.json",
        "concurso": ultimo_concurso,
        "dezenas": dezenas,
        "raw": {str(ultimo_concurso): dezenas_raw},
    }


# -----------------------------------------------------------------------------
# Função com cache em memória
# -----------------------------------------------------------------------------
def get_lotofacil_result() -> Dict[str, Any]:
    now = time.time()

    # Se tem cache recente, usa ele
    if (
        _last_result_cache
        and (now - _last_result_cache.get("timestamp", 0)) < CACHE_TTL_SECONDS
    ):
        logging.info("Retornando resultado do cache.")
        return _last_result_cache["data"]

    # Senão, busca de novo no GitHub
    logging.info("Cache vazio/expirado. Buscando novo resultado no GitHub...")
    result = fetch_lotofacil_from_github()

    _last_result_cache["data"] = result
    _last_result_cache["timestamp"] = now
    return result


# -----------------------------------------------------------------------------
# Rotas
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    return jsonify({
        "status": "ok",
        "message": "LotteryGeniusApp (fonte GitHub) está rodando 🚀",
        "endpoints": {
            "ping": "/ping",
            "lotofacil_ultimo": "/lotofacil/ultimo",
            "lotofacil_ultimo_com_barra": "/lotofacil/ultimo/",
        }
    })


@app.route("/ping")
def ping():
    # mensagem nova, pra diferenciar do código antigo
    return "pong - app (fonte GitHub) está rodando"


# Aceita COM e SEM barra no final
@app.route("/lotofacil/ultimo")
@app.route("/lotofacil/ultimo/")
def lotofacil_ultimo():
    try:
        result = get_lotofacil_result()
        return jsonify({
            "success": True,
            "result": result
        })
    except Exception as e:
        logging.exception("Erro ao obter Lotofácil (GitHub).")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# -----------------------------------------------------------------------------
# Main (para rodar localmente; no Render, usa o 'app' WSGI)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
