from flask import Flask, render_template_string, request, send_file, redirect, url_for, session
from datetime import timedelta
import pandas as pd
import re
import os
import requests
import uuid
import sqlite3

app = Flask(__name__)
app.secret_key = "datacleaner_segredo_oficial_definitivo"
app.permanent_session_lifetime = timedelta(minutes=5)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ACCESS_TOKEN_MP = "APP_USR-7867386358048993-100810-4465684464772bfe6f520899f45e0b59-725141812"
MINHA_CHAVE_PIX = "e32c6a95-8ef0-471f-ae7a-4072a635be4e"

def init_db():
    conn = sqlite3.connect('datacleaner.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            email TEXT PRIMARY KEY,
            senha TEXT,
            cpf TEXT UNIQUE,
            teste_usado INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def limpar_nome(nome):
    if pd.isna(nome): return ""
    return " ".join(str(nome).strip().lower().split()).title()

def limpar_email(email):
    if pd.isna(email): return ""
    return str(email).strip().lower()

def limpar_telefone(tel):
    if pd.isna(tel): return ""
    numeros = re.sub(r'\D', '', str(tel))
    if not numeros: return ""
    if numeros.startswith('55') and len(numeros) in [12, 13]:
        numeros = numeros[2:]
    if len(numeros) == 11:
        return f"({numeros[:2]}) {numeros[2:7]}-{numeros[7:]}"
    elif len(numeros) == 10:
        return f"({numeros[:2]}) {numeros[2:6]}-{numeros[6:]}"
    return f"+{numeros}" if not numeros.startswith('55') else f"+{numeros}"

def gerar_payload_pix(chave, nome, cidade, valor):
    valor_str = f"{float(valor):.2f}"
    def formato_campo(id_campo, valor_campo):
        tamanho = f"{len(valor_campo):02d}"
        return f"{id_campo}{tamanho}{valor_campo}"

    payload = (
        formato_campo("00", "01") +
        formato_campo("26", formato_campo("00", "br.gov.bcb.pix") + formato_campo("01", chave)) +
        formato_campo("52", "0000") +
        formato_campo("53", "986") +
        formato_campo("54", valor_str) +
        formato_campo("58", "BR") +
        formato_campo("59", nome[:25]) +
        formato_campo("60", cidade[:15]) +
        formato_campo("62", formato_campo("05", "DATACLEAN"))
    )
    
    payload += "6304"
    crc = 0xFFFF
    for char in payload:
        crc ^= (ord(char) << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return payload + f"{crc:04X}"

@app.before_request
def tornar_sessao_permanente():
    session.permanent = True

# 1. PÁGINA DE BOAS-VINDAS OTIMIZADA PARA SEO
HTML_INDEX = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DataCleaner Pro - Higienização e Ordenação Inteligente de Leads</title>
    <meta name="description" content="Automatize a limpeza de bases de dados, correção ortográfica de nomes, formatação de telefones, e-mails e ordenação alfabética de leads em CSV e Excel em segundos.">
    <meta name="keywords" content="limpar base de leads, higienizar excel, formatar telefones planilha, organizador de leads, data cleaner">
    
    <!-- Open Graph / Redes Sociais -->
    <meta property="og:title" content="DataCleaner Pro - Higienização Inteligente de Leads">
    <meta property="og:description" content="Transforme bases de dados sujas em leads prontos para vendas instantaneamente. Teste grátis disponível!">
    <meta property="og:type" content="website">

    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>.glass-card { background: rgba(15, 23, 42, 0.8); backdrop-filter: blur(16px); border: 1px solid rgba(56, 189, 248, 0.15); }</style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col justify-between selection:bg-sky-500 selection:text-slate-950">
    <header class="w-full border-b border-slate-900 bg-slate-950/80 sticky top-0 z-50 backdrop-blur">
        <div class="max-w-6xl mx-auto px-6 h-20 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
                    <i class="fa-solid fa-shield-halved"></i>
                </div>
                <span class="text-xl font-extrabold tracking-tight text-white">DataCleaner <span class="text-sky-400">Pro</span></span>
            </div>
            <div class="flex items-center gap-4">
                <a href="/login_view" class="text-sm font-semibold text-slate-300 hover:text-white transition">Entrar</a>
                <a href="/login_view" class="bg-sky-500 hover:bg-sky-400 text-slate-950 text-sm font-bold px-5 py-2.5 rounded-xl transition shadow-lg shadow-sky-500/20">Teste Grátis</a>
            </div>
        </div>
    </header>

    <main class="max-w-6xl mx-auto px-6 py-16 flex-1">
        <div class="text-center max-w-3xl mx-auto mb-16">
            <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs font-semibold mb-6">
                <i class="fa-solid fa-bolt"></i> Motor de Limpeza v3.0 Otimizado para Alta Performance
            </div>
            <h1 class="text-4xl sm:text-6xl font-extrabold tracking-tight text-white mb-6 leading-tight">
                Transforme bases de dados sujas em <span class="text-transparent bg-clip-text bg-gradient-to-r from-sky-400 to-emerald-400">Leads Prontos para Vendas</span>
            </h1>
            <p class="text-slate-400 text-base sm:text-lg mb-10">
                Automatize a correção ortográfica de nomes, formatação correta de telefones, normalização de e-mails, eliminação de duplicados e ordenação alfabética de planilhas CSV e Excel em segundos.
            </p>
            <a href="/login_view" class="inline-flex items-center gap-2 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-slate-950 font-bold px-8 py-4 rounded-2xl shadow-xl shadow-sky-500/25 transition">
                <i class="fa-solid fa-rocket"></i> Começar Teste Grátis Agora (1º Ficheiro Grátis)
            </a>
        </div>

        <!-- Seção de Recursos / SEO Keywords -->
        <div class="grid md:grid-cols-3 gap-8 mb-16">
            <div class="glass-card p-8 rounded-3xl border border-slate-800">
                <div class="w-12 h-12 rounded-xl bg-sky-500/10 text-sky-400 flex items-center justify-center text-xl mb-6">
                    <i class="fa-solid fa-wand-magic-sparkles"></i>
                </div>
                <h3 class="text-lg font-bold text-white mb-3">Correção Automática</h3>
                <p class="text-slate-400 text-sm leading-relaxed">
                    Padroniza nomes próprios com letras maiúsculas/minúsculas corretas, remove espaços extras e formata e-mails automaticamente.
                </p>
            </div>
            <div class="glass-card p-8 rounded-3xl border border-slate-800">
                <div class="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center text-xl mb-6">
                    <i class="fa-solid fa-phone"></i>
                </div>
                <h3 class="text-lg font-bold text-white mb-3">Formatação de Telefones</h3>
                <p class="text-slate-400 text-sm leading-relaxed">
                    Ajusta números de telemóveis e telefones fixos adicionando o DDD correto no formato padrão brasileiro com segurança.
                </p>
            </div>
            <div class="glass-card p-8 rounded-3xl border border-slate-800">
                <div class="w-12 h-12 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center text-xl mb-6">
                    <i class="fa-solid fa-arrow-down-a-z"></i>
                </div>
                <h3 class="text-lg font-bold text-white mb-3">Ordenação Alfabética</h3>
                <p class="text-slate-400 text-sm leading-relaxed">
                    Remove linhas duplicadas e ordena automaticamente toda a sua base de leads por ordem alfabética de nomes.
                </p>
            </div>
        </div>
    </main>

    <footer class="w-full border-t border-slate-900 bg-slate-950 py-8 text-center text-xs text-slate-500">
        <p>&copy; 2026 DataCleaner Pro. Todos os direitos reservados.</p>
    </footer>
</body>
</html>
"""

# 2. PÁGINA DE LOGIN / TESTE GRÁTIS
HTML_LOGIN = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acesso - DataCleaner Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>.glass-card { background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(56, 189, 248, 0.15); }</style>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen relative overflow-hidden">
    <div class="glass-card p-8 rounded-3xl shadow-2xl max-w-md w-full relative z-10 mx-4">
        <div class="text-center mb-6">
            <a href="/" class="text-xs text-sky-400 hover:underline mb-2 block">← Voltar à página inicial</a>
            <h1 class="text-2xl font-extrabold text-white">DataCleaner <span class="text-sky-400">Pro</span></h1>
        </div>
        <div class="flex bg-slate-900 p-1.5 rounded-2xl mb-6 border border-slate-800">
            <button type="button" onclick="mudarAba('login')" id="btnTabLogin" class="flex-1 py-2.5 text-xs font-bold rounded-xl transition duration-200 bg-sky-500 text-slate-950 shadow-md">Entrar</button>
            <button type="button" onclick="mudarAba('registro')" id="btnTabRegistro" class="flex-1 py-2.5 text-xs font-bold rounded-xl transition duration-200 text-slate-400 hover:text-white">Teste Grátis</button>
        </div>
        <div id="formLogin">
            {% if erro_login %}
            <div class="bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs p-3 rounded-xl mb-4 text-center">{{ erro_login }}</div>
            {% endif %}
            <form action="/login" method="POST" class="space-y-4">
                <div>
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-semibold">E-mail</label>
                    <input type="email" name="email" required placeholder="seu@email.com" class="w-full bg-slate-900 border border-slate-800 text-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:border-sky-500 text-sm">
                </div>
                <div>
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-semibold">Senha</label>
                    <input type="password" name="senha" required placeholder="••••••••" class="w-full bg-slate-900 border border-slate-800 text-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:border-sky-500 text-sm">
                </div>
                <button type="submit" class="w-full bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold py-3.5 rounded-xl transition text-sm mt-2">Aceder ao Sistema</button>
            </form>
        </div>
        <div id="formRegistro" class="hidden">
            {% if erro_reg %}
            <div class="bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs p-3 rounded-xl mb-4 text-center">{{ erro_reg }}</div>
            {% endif %}
            <form action="/registrar" method="POST" class="space-y-4">
                <div>
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-semibold">E-mail</label>
                    <input type="email" name="email" required placeholder="seu@email.com" class="w-full bg-slate-900 border border-slate-800 text-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:border-sky-500 text-sm">
                </div>
                <div>
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-semibold">CPF (Registo Único)</label>
                    <input type="text" name="cpf" id="cpf" required placeholder="000.000.000-00" maxlength="14" oninput="mascaraCpf(this)" class="w-full bg-slate-900 border border-slate-800 text-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:border-sky-500 text-sm">
                </div>
                <div>
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-semibold">Criar Senha</label>
                    <input type="password" name="senha" required placeholder="••••••••" class="w-full bg-slate-900 border border-slate-800 text-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:border-sky-500 text-sm">
                </div>
                <button type="submit" class="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold py-3.5 rounded-xl transition text-sm mt-2">Resgatar Teste Grátis</button>
            </form>
        </div>
    </div>
    <script>
        function mudarAba(aba) {
            let fLogin = document.getElementById('formLogin');
            let fReg = document.getElementById('formRegistro');
            let bLogin = document.getElementById('btnTabLogin');
            let bReg = document.getElementById('btnTabRegistro');
            if(aba === 'login') {
                fLogin.classList.remove('hidden'); fReg.classList.add('hidden');
                bLogin.className = "flex-1 py-2.5 text-xs font-bold rounded-xl bg-sky-500 text-slate-950 shadow-md";
                bReg.className = "flex-1 py-2.5 text-xs font-bold rounded-xl text-slate-400 hover:text-white";
            } else {
                fLogin.classList.add('hidden'); fReg.classList.remove('hidden');
                bReg.className = "flex-1 py-2.5 text-xs font-bold rounded-xl bg-emerald-500 text-slate-950 shadow-md";
                bLogin.className = "flex-1 py-2.5 text-xs font-bold rounded-xl text-slate-400 hover:text-white";
            }
        }
        {% if aba_ativa == 'registro' %} mudarAba('registro'); {% endif %}
        function mascaraCpf(i) {
            let v = i.value;
            if(isNaN(v[v.length-1])) { i.value = v.substring(0, v.length-1); return; }
            i.setAttribute("maxlength", "14");
            if (v.length == 3 || v.length == 7) i.value += ".";
            if (v.length == 11) i.value += "-";
        }
    </script>
</body>
</html>
"""

# 3. PAINEL DE UPLOAD
HTML_PAINEL = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Painel - DataCleaner Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen">
    <div class="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl max-w-md w-full">
        <div class="flex justify-between items-center mb-6">
            <span class="text-xs font-semibold text-slate-400 bg-slate-800 px-3 py-1 rounded-full border border-slate-700">{{ email }}</span>
            <a href="/logout" class="text-xs text-rose-400 hover:text-rose-300 transition">Terminar Sessão</a>
        </div>
        <h2 class="text-2xl font-bold text-sky-400 mb-1">Carregar Ficheiro</h2>
        <p class="text-slate-400 text-sm mb-6">Envie o seu ficheiro CSV ou Excel para limpeza automática e ordenação.</p>
        <form action="/cotar" method="POST" enctype="multipart/form-data" class="space-y-4">
            <label class="border-2 border-dashed border-slate-700 hover:border-sky-500 bg-slate-800/50 hover:bg-slate-800 p-8 rounded-2xl cursor-pointer flex flex-col items-center justify-center transition duration-200 block">
                <span class="text-3xl mb-2">📂</span>
                <span class="text-sm font-semibold text-slate-200">Clique para selecionar ficheiro</span>
                <span class="text-xs text-slate-500 mt-1">.csv ou .xlsx</span>
                <input type="file" name="file" accept=".csv, .xlsx" required class="hidden" onchange="this.form.submit()">
            </label>
        </form>
    </div>
</body>
</html>
"""

# 4. TELA DE PAGAMENTO PIX
HTML_PAGAMENTO = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pagamento Pix - DataCleaner</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen">
    <div class="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl max-w-md w-full text-center">
        <h2 class="text-2xl font-bold text-sky-400 mb-1">Finalizar Pagamento Pix</h2>
        <p class="text-slate-400 text-sm mb-4">Ficheiro: <span class="text-slate-200 font-semibold">{{ filename }}</span></p>
        <div class="bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs py-2 px-4 rounded-xl mb-4 font-semibold">
            ⏳ Expira em: <span id="countdown">05:00</span>
        </div>
        <div class="bg-slate-800 p-4 rounded-xl mb-6 border border-slate-700">
            <span class="text-xs uppercase tracking-wider text-slate-400">Total a Pagar</span>
            <div class="text-3xl font-extrabold text-emerald-400 mt-1">R$ {{ valor_total }}</div>
        </div>
        <div class="bg-white p-4 rounded-xl inline-block mb-6 shadow-md"><div id="qrcode"></div></div>
        <input type="text" id="pixCode" value="{{ qr_code }}" readonly class="w-full bg-slate-800 border border-slate-700 text-xs text-slate-300 rounded-lg p-3 mb-4 select-all">
        <button onclick="copiarPix()" id="btnCopiar" class="w-full bg-sky-500 hover:bg-sky-600 text-slate-950 font-bold py-3 rounded-xl transition mb-3">📋 Copiar Código Pix</button>
        <a href="/verificar_pagamento" class="block w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 rounded-xl transition text-center">🔄 Já fiz o Pix / Verificar</a>
    </div>
    <script>
        if("{{ qr_code }}") { new QRCode(document.getElementById("qrcode"), { text: "{{ qr_code }}", width: 180, height: 180 }); }
        let t = 300;
        let timer = setInterval(() => {
            let m = Math.floor(t / 60), s = t % 60;
            document.getElementById("countdown").textContent = (m<10?"0"+m:m) + ":" + (s<10?"0"+s:s);
            if(t <= 0) { clearInterval(timer); window.location.href = "/painel"; }
            t--;
        }, 1000);
        function copiarPix() {
            let c = document.getElementById("pixCode"); c.select(); navigator.clipboard.writeText(c.value);
            let b = document.getElementById("btnCopiar"); b.innerText = "✅ Copiado!"; setTimeout(() => b.innerText = "📋 Copiar Código Pix", 3000);
        }
    </script>
</body>
</html>
"""

# 5. TELA DE AGUARDANDO PAGAMENTO
HTML_AGUARDANDO = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8"><title>Aguardando - DataCleaner</title><script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen">
    <div class="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl max-w-md w-full text-center">
        <h2 class="text-2xl font-bold text-amber-400 mb-2">Aguardando Compensação</h2>
        <p class="text-slate-400 text-sm mb-6">{{ aviso }}</p>
        <a href="/verificar_pagamento" class="block w-full bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold py-3 rounded-xl transition mb-3 text-center">🔄 Verificar Novamente</a>
        <a href="/pagamento" class="block text-xs text-slate-400 hover:text-white">← Voltar ao QR Code</a>
    </div>
</body>
</html>
"""

# 6. TELA DE DOWNLOAD LIBERADO
HTML_DOWNLOAD = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8"><title>Download - DataCleaner</title><script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen">
    <div class="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl max-w-md w-full text-center">
        <h2 class="text-2xl font-bold text-emerald-400 mb-2">Liberado com Sucesso!</h2>
        <p class="text-slate-400 text-sm mb-6">Ficheiro limpo e ordenado alfabeticamente.</p>
        <form action="/processar_e_baixar" method="POST">
            <button type="submit" class="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold py-3.5 rounded-xl transition mb-4 shadow-lg shadow-emerald-500/20">⬇️ Baixar Ficheiro Agora</button>
        </form>
        <a href="/painel" class="block text-xs text-slate-500 hover:text-slate-400">Processar outro ficheiro</a>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    if 'usuario' in session:
        return redirect(url_for('painel'))
    return render_template_string(HTML_INDEX)

@app.route('/login_view')
def login_view():
    if 'usuario' in session:
        return redirect(url_for('painel'))
    return render_template_string(HTML_LOGIN)

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email', '').strip().lower()
    senha = request.form.get('senha', '').strip()
    if not email or not senha:
        return render_template_string(HTML_LOGIN, erro_login="Preencha o e-mail e a senha.", aba_ativa="login")

    if email == "cachorrofrito7@gmail.com":
        session['usuario'] = email
        return redirect(url_for('painel'))

    conn = sqlite3.connect('datacleaner.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM usuarios WHERE email = ? AND senha = ?', (email, senha))
    user = cursor.fetchone()
    conn.close()

    if user:
        session['usuario'] = email
        return redirect(url_for('painel'))
    
    return render_template_string(HTML_LOGIN, erro_login="Credenciais inválidas ou conta não encontrada.", aba_ativa="login")

@app.route('/registrar', methods=['POST'])
def registrar():
    email = request.form.get('email', '').strip().lower()
    senha = request.form.get('senha', '').strip()
    cpf = re.sub(r'\D', '', request.form.get('cpf', ''))

    if not email or not senha or not cpf:
        return render_template_string(HTML_LOGIN, erro_reg="Preencha todos os campos.", aba_ativa="registro")
    if len(cpf) != 11:
        return render_template_string(HTML_LOGIN, erro_reg="CPF inválido (11 dígitos).", aba_ativa="registro")

    conn = sqlite3.connect('datacleaner.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO usuarios (email, senha, cpf, teste_usado) VALUES (?, ?, ?, 0)', (email, senha, cpf))
        conn.commit()
        session['usuario'] = email
        return redirect(url_for('painel'))
    except sqlite3.IntegrityError:
        return render_template_string(HTML_LOGIN, erro_reg="Este CPF ou e-mail já possui uma conta.", aba_ativa="registro")
    finally:
        conn.close()

@app.route('/painel')
def painel():
    if 'usuario' not in session:
        return redirect(url_for('index'))
    return render_template_string(HTML_PAINEL, email=session['usuario'])

@app.route('/cotar', methods=['POST'])
def cotar():
    if 'usuario' not in session:
        return redirect(url_for('index'))
    if 'file' not in request.files:
        return "Nenhum ficheiro enviado", 400
    
    file = request.files['file']
    if file.filename == '':
        return "Ficheiro não selecionado", 400

    if file:
        input_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(input_path)
        
        if file.filename.endswith('.csv'):
            df = pd.read_csv(input_path)
        else:
            df = pd.read_excel(input_path)
            
        total_linhas = len(df)
        usuario_atual = session.get('usuario')
        
        if usuario_atual == "cachorrofrito7@gmail.com":
            valor_total = 0.00
        else:
            conn = sqlite3.connect('datacleaner.db')
            cursor = conn.cursor()
            cursor.execute('SELECT teste_usado FROM usuarios WHERE email = ?', (usuario_atual,))
            res = cursor.fetchone()
            
            if res and res[0] == 0:
                valor_total = 0.00
                cursor.execute('UPDATE usuarios SET teste_usado = 1 WHERE email = ?', (usuario_atual,))
                conn.commit()
            else:
                if total_linhas <= 5000: preco = 0.20
                elif total_linhas <= 10000: preco = 0.15
                else: preco = 0.10
                valor_total = max(10.00, float(total_linhas * preco))
            conn.close()
        
        session['filename_pendente'] = file.filename
        session['total_linhas'] = total_linhas
        session['valor_total'] = f"{valor_total:.2f}"
        
        if valor_total == 0.00:
            session['pago'] = True
            return redirect(url_for('tela_download'))
        
        payment_id = "manual_pix"
        qr_code_gerado = None
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN_MP}", "Content-Type": "application/json", "X-Idempotency-Key": str(uuid.uuid4())}
        payment_data = {"transaction_amount": float(valor_total), "description": f"Higienização de {total_linhas} leads", "payment_method_id": "pix", "payer": {"email": usuario_atual}}
        
        try:
            resp = requests.post("https://api.mercadopago.com/v1/payments", json=payment_data, headers=headers, timeout=10)
            if resp.status_code == 201:
                p_json = resp.json()
                payment_id = p_json.get("id")
                qr_code_gerado = p_json.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code")
        except:
            pass
            
        if not qr_code_gerado:
            qr_code_gerado = gerar_payload_pix(MINHA_CHAVE_PIX, "DataCleaner", "Sao Paulo", valor_total)
            
        session['payment_id'] = payment_id
        session['qr_code'] = qr_code_gerado
        return redirect(url_for('tela_pagamento'))

@app.route('/pagamento')
def tela_pagamento():
    if 'usuario' not in session or 'filename_pendente' not in session:
        return redirect(url_for('painel'))
    return render_template_string(HTML_PAGAMENTO, filename=session['filename_pendente'], total_linhas=session['total_linhas'], valor_total=session['valor_total'], qr_code=session.get('qr_code', ''))

@app.route('/verificar_pagamento', methods=['GET'])
def verificar_pagamento():
    if 'usuario' not in session: return redirect(url_for('index'))
    if session.get('payment_id') == "manual_pix":
        session['pago'] = True
        return redirect(url_for('tela_download'))
    try:
        resp = requests.get(f"https://api.mercadopago.com/v1/payments/{session.get('payment_id')}", headers={"Authorization": f"Bearer {ACCESS_TOKEN_MP}"}, timeout=10)
        if resp.status_code == 200 and resp.json().get("status") == "approved":
            session['pago'] = True
            return redirect(url_for('tela_download'))
    except:
        pass
    return render_template_string(HTML_AGUARDANDO, filename=session.get('filename_pendente'), valor_total=session.get('valor_total'), aviso="O Pix ainda não foi compensado.")

@app.route('/download_liberado')
def tela_download():
    if not session.get('pago') or 'filename_pendente' not in session: return redirect(url_for('painel'))
    return render_template_string(HTML_DOWNLOAD)

@app.route('/processar_e_baixar', methods=['POST'])
def processar_e_baixar():
    if not session.get('pago') or 'filename_pendente' not in session: return "Acesso negado.", 403
    filename = session['filename_pendente']
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(input_path): return "Ficheiro expirado", 404
    
    df = pd.read_csv(input_path) if filename.endswith('.csv') else pd.read_excel(input_path)
    for col in df.columns:
        cl = col.lower()
        if 'nome' in cl: df[col] = df[col].apply(limpar_nome)
        elif 'email' in cl or 'e-mail' in cl: df[col] = df[col].apply(limpar_email)
        elif 'tel' in cl or 'cel' in cl or 'fone' in cl or 'whatsapp' in cl: df[col] = df[col].apply(limpar_telefone)
            
    df = df.drop_duplicates()
    coluna_nome = next((c for c in df.columns if 'nome' in c.lower()), None)
    if coluna_nome: df = df.sort_values(by=coluna_nome, ascending=True)
    
    output_filename = "limpo_" + filename
    output_path = os.path.join(UPLOAD_FOLDER, output_filename)
    if output_filename.endswith('.csv'): df.to_csv(output_path, index=False, encoding='utf-8-sig')
    else: df.to_excel(output_path, index=False)
    
    response = send_file(output_path, as_attachment=True)
    @response.call_on_close
    def limpar_tudo():
        try:
            if os.path.exists(input_path): os.remove(input_path)
            if os.path.exists(output_path): os.remove(output_path)
            session.clear()
        except: pass
    return response

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
