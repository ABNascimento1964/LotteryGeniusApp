from flask import Flask, render_template, request, send_file
import random
import io
from collections import Counter
import requests

app = Flask(__name__)

# -----------------------------
# Conjuntos de números especiais
# -----------------------------

PRIMOS = {2, 3, 5, 7, 11, 13, 17, 19, 23}
FIBONACCI = {1, 2, 3, 5, 8, 13, 21}
BORDAS = {
    1, 2, 3, 4, 5,
    6, 10,
    11, 15,
    16, 20,
    21, 22, 23, 24, 25
}

# -----------------------------
# Função para analisar um jogo
# -----------------------------

def analisar_jogo(jogo):
    pares = sum(1 for n in jogo if n % 2 == 0)
    impares = len(jogo) - pares
    primos = sum(1 for n in jogo if n in PRIMOS)
    fib = sum(1 for n in jogo if n in FIBONACCI)
    borda = sum(1 for n in jogo if n in BORDAS)
    baixos = sum(1 for n in jogo if n <= 13)
    altos = len(jogo) - baixos

    return {
        "pares": pares,
        "impares": impares,
        "primos": primos,
        "fibonacci": fib,
        "borda": borda,
        "baixos": baixos,
        "altos": altos,
    }

# ----------------------------------
# Carregar últimos resultados reais
# (API oficial CAIXA)
# ----------------------------------

URL_LOTOFACIL_ULTIMO = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"
URL_LOTOFACIL_CONCURSO = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil/{}"

CAIXA_HEADERS = {
    "accept": "application/json",
    # user-agent fake de navegador, a API costuma exigir
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
}


def carregar_ultimos_resultados(qtd_concursos=10):
    """
    Lê o ÚLTIMO resultado da Lotofácil direto da API da Caixa
    e calcula as frequências dos últimos N concursos.

    Retorna:
      - ultimo_resultado: {"concurso": int, "data": str, "dezenas": [int,...]}
      - frequencias: {1..25: quantidade nas N últimas extrações}
    """
    # ---------- pega o último concurso ----------
    try:
        resp = requests.get(URL_LOTOFACIL_ULTIMO, headers=CAIXA_HEADERS, timeout=10)
        resp.raise_for_status()
        dados_ultimo = resp.json()
    except Exception as exc:
        print("Erro ao baixar último resultado da Lotofácil:", exc)
        return None, {n: 0 for n in range(1, 26)}

    try:
        numero_ultimo = int(dados_ultimo.get("numero"))
        dezenas_ultimo_raw = (
            dados_ultimo.get("listaDezenas")
            or dados_ultimo.get("dezenasSorteadasOrdemSorteio")
            or []
        )
        data_ultimo = dados_ultimo.get("dataApuracao")
    except Exception as exc:
        print("Erro ao interpretar dados do último concurso:", exc)
        return None, {n: 0 for n in range(1, 26)}

    dezenas_ultimo = []
    for d in dezenas_ultimo_raw:
        try:
            dezenas_ultimo.append(int(d))
        except (TypeError, ValueError):
            continue
    dezenas_ultimo.sort()

    ultimo_resultado = {
        "concurso": numero_ultimo,
        "data": data_ultimo,
        "dezenas": dezenas_ultimo,
    }

    # ---------- frequências dos últimos N concursos ----------
    primeiro_concurso = max(1, numero_ultimo - qtd_concursos + 1)
    contador = Counter()

    for concurso in range(primeiro_concurso, numero_ultimo + 1):
        try:
            url = URL_LOTOFACIL_CONCURSO.format(concurso)
            r = requests.get(url, headers=CAIXA_HEADERS, timeout=10)
            r.raise_for_status()
            dados = r.json()

            dezenas_raw = (
                dados.get("listaDezenas")
                or dados.get("dezenasSorteadasOrdemSorteio")
                or []
            )

            for d in dezenas_raw:
                try:
                    n = int(d)
                except (TypeError, ValueError):
                    continue
                if 1 <= n <= 25:
                    contador[n] += 1
        except Exception as exc:
            print(f"Erro ao baixar concurso {concurso}:", exc)
            continue

    frequencias = {n: contador.get(n, 0) for n in range(1, 26)}

    return ultimo_resultado, frequencias

# -----------------------------
# Geração de jogos
# -----------------------------

def gerar_jogos(qtd_jogos=10, dezenas_por_jogo=15, frequencias=None):
    """
    Gera jogos usando TODAS as dezenas (1..25).
    Usa as frequências como peso:
      peso = frequencia + 1  (assim até quem não saiu ainda pode aparecer)
    """
    if frequencias is None:
        frequencias = {n: 0 for n in range(1, 26)}

    numeros = list(range(1, 26))
    pesos = [frequencias.get(n, 0) + 1 for n in numeros]

    jogos = []

    for _ in range(qtd_jogos):
        # sorteio ponderado (pode repetir dentro do sorteio bruto)
        sorteio_bruto = random.choices(
            population=numeros,
            weights=pesos,
            k=dezenas_por_jogo * 2,  # pega um pouco a mais para evitar repetição
        )

        # remove repetidos mantendo aleatório
        vistos = set()
        unicos = []
        for n in sorteio_bruto:
            if n not in vistos:
                vistos.add(n)
                unicos.append(n)
            if len(unicos) == dezenas_por_jogo:
                break

        # se mesmo assim faltar número, completa com o que sobrou
        if len(unicos) < dezenas_por_jogo:
            restantes = [n for n in numeros if n not in vistos]
            if len(restantes) >= dezenas_por_jogo - len(unicos):
                extra = random.sample(restantes, dezenas_por_jogo - len(unicos))
                unicos.extend(extra)

        unicos.sort()
        estat = analisar_jogo(unicos)

        jogos.append(
            {
                "dezenas": unicos,
                "analise": estat,
            }
        )

    return jogos

# -----------------------------
# Rotas Flask
# -----------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    # valores padrão
    qtd_jogos = 10
    dezenas_por_jogo = 15

    if request.method == "POST":
        try:
            qtd_jogos = int(request.form.get("qtd_jogos", qtd_jogos))
        except (TypeError, ValueError):
            qtd_jogos = 10

        try:
            dezenas_por_jogo = int(
                request.form.get("dezenas_por_jogo", dezenas_por_jogo)
            )
        except (TypeError, ValueError):
            dezenas_por_jogo = 15

        # limites de segurança
        qtd_jogos = max(1, min(qtd_jogos, 50))
        dezenas_por_jogo = max(15, min(dezenas_por_jogo, 20))

    # carrega últimos concursos e frequências (agora direto da Caixa)
    ultimo_resultado, frequencias = carregar_ultimos_resultados(qtd_concursos=10)

    # gera jogos usando 1..25 com peso nas dezenas mais quentes
    jogos = gerar_jogos(
        qtd_jogos=qtd_jogos,
        dezenas_por_jogo=dezenas_por_jogo,
        frequencias=frequencias,
    )

    return render_template(
        "index.html",
        ultimo_resultado=ultimo_resultado,
        frequencias=frequencias,
        jogos=jogos,
        qtd_jogos=qtd_jogos,
        dezenas_por_jogo=dezenas_por_jogo,
    )


@app.route("/download_txt")
def download_txt():
    # lê parâmetros (se vierem da URL)
    qtd_jogos = int(request.args.get("qtd_jogos", 20))
    dezenas_por_jogo = int(request.args.get("dezenas_por_jogo", 15))

    # garante limites
    qtd_jogos = max(1, min(qtd_jogos, 50))
    dezenas_por_jogo = max(15, min(dezenas_por_jogo, 20))

    # gera novamente para o TXT
    _, frequencias = carregar_ultimos_resultados(qtd_concursos=10)
    jogos = gerar_jogos(
        qtd_jogos=qtd_jogos,
        dezenas_por_jogo=dezenas_por_jogo,
        frequencias=frequencias,
    )

    buffer = io.StringIO()
    buffer.write("Lottery Genius - Jogos gerados\n\n")
    for idx, jogo in enumerate(jogos, start=1):
        dezenas_str = ",".join(f"{n:02d}" for n in jogo["dezenas"])
        buffer.write(f"Jogo {idx:02d}: {dezenas_str}\n")

    mem = io.BytesIO()
    mem.write(buffer.getvalue().encode("utf-8"))
    mem.seek(0)

    return send_file(
        mem,
        as_attachment=True,
        download_name="jogos_lottery_genius.txt",
        mimetype="text/plain",
    )


if __name__ == "__main__":
    app.run(debug=True)
