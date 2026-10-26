from flask import Flask, render_template_string, request, send_file, redirect, url_for, session, flash, jsonify
from datetime import timedelta
from functools import wraps
import pandas as pd
import re
import os
import requests
import uuid
import sqlite3
import dns.resolver

app = Flask(__name__)
app.secret_key = "datacleaner_segredo_oficial_definitivo"
app.permanent_session_lifetime = timedelta(minutes=5)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ACCESS_TOKEN_MP = "APP_USR-7867386358048993-100810-4465684464772bfe6f520899f45e0b59-725141812"
MINHA_CHAVE_PIX = "e32c6a95-8ef0-471f-ae7a-4072a635be4e"
ADMIN_EMAIL = "cachorrofrito7@gmail.com"

def init_db():
    conn = sqlite3.connect('datacleaner.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            email TEXT PRIMARY KEY,
            senha TEXT,
            cpf TEXT UNIQUE,
            teste_usado INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            api_token TEXT UNIQUE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_email = session.get('usuario')
        if not user_email or user_email.lower() != ADMIN_EMAIL.lower():
            flash("Acesso restrito ao administrador.", "danger")
            return redirect(url_for('painel'))
        return f(*args, **kwargs)
    return decorated_function

def limpar_nome(nome):
    if pd.isna(nome): return ""
    return " ".join(str(nome).strip().lower().split()).title()

def limpar_email(email):
    if pd.isna(email): return ""
    return str(email).strip().lower()

def validar_dominio_email(email):
    try:
        if "@" not in email: return False
        dominio = email.split('@')[1]
        registros = dns.resolver.resolve(dominio, 'MX')
        return True if registros else False
    except:
        return False

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

@app.route('/googled2b6467c03a7583c.html')
def google_verification():
    return "google-site-verification: googled2b6467c03a7583c.html"

# ==========================================
# INTERFACES DE UTILIZADOR (UI/UX CORPORATIVA)
# ==========================================

HTML_ADMIN = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Painel Enterprise - DataCleaner Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans antialiased">
    <div class="max-w-7xl mx-auto px-6 py-10">
        <header class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-10 pb-6 border-b border-slate-800">
            <div>
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
                        <i class="fa-solid fa-chart-pie"></i>
                    </div>
                    <h1 class="text-2xl font-black tracking-tight text-white">Painel Enterprise <span class="text-sky-400">Admin</span></h1>
                </div>
                <p class="text-xs text-slate-400 mt-1">Gestão global de utilizadores, chaves de API e acessos VIP.</p>
            </div>
            <a href="/painel" class="inline-flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-800 px-5 py-2.5 rounded-xl text-xs font-semibold transition shadow-sm">
                <i class="fa-solid fa-arrow-left"></i> Voltar ao Painel
            </a>
        </header>
        
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
            <div class="bg-slate-900/60 backdrop-blur border border-slate-800/80 p-6 rounded-2xl shadow-xl">
                <span class="text-xs uppercase text-slate-400 font-bold tracking-wider">Total de Utilizadores</span>
                <p class="text-4xl font-black text-white mt-2">{{ total_users }}</p>
            </div>
            <div class="bg-slate-900/60 backdrop-blur border border-slate-800/80 p-6 rounded-2xl shadow-xl">
                <span class="text-xs uppercase text-slate-400 font-bold tracking-wider">Arquivos Higienizados</span>
                <p class="text-4xl font-black text-sky-400 mt-2">{{ total_cleanings }}</p>
            </div>
            <div class="bg-slate-900/60 backdrop-blur border border-slate-800/80 p-6 rounded-2xl shadow-xl">
                <span class="text-xs uppercase text-slate-400 font-bold tracking-wider">Utilizadores VIP / Enterprise</span>
                <p class="text-4xl font-black text-emerald-400 mt-2">{{ total_vip }}</p>
            </div>
        </div>

        <div class="bg-slate-900/60 backdrop-blur border border-slate-800/80 rounded-2xl overflow-hidden shadow-2xl">
            <div class="p-6 border-b border-slate-800">
                <h2 class="text-base font-bold text-white">Base de Utilizadores Registados</h2>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-sm">
                    <thead class="bg-slate-950/50 text-slate-400 uppercase text-xs tracking-wider">
                        <tr>
                            <th class="p-4 font-semibold">E-mail</th>
                            <th class="p-4 font-semibold">CPF</th>
                            <th class="p-4 font-semibold">Token API</th>
                            <th class="p-4 font-semibold">Status do Plano</th>
                            <th class="p-4 font-semibold text-center">Ação VIP</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800/60">
                        {% for user in users %}
                        <tr class="hover:bg-slate-800/30 transition">
                            <td class="p-4 font-medium text-slate-200">{{ user[0] }}</td>
                            <td class="p-4 text-slate-400 font-mono text-xs">{{ user[2] }}</td>
                            <td class="p-4 text-slate-400 font-mono text-xs">{{ user[5] or 'N/A' }}</td>
                            <td class="p-4">
                                {% if user[4] == 1 or user[0] == 'cachorrofrito7@gmail.com' %}
                                    <span class="inline-flex items-center gap-1.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs px-3 py-1 rounded-full font-bold">
                                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> Enterprise VIP
                                    </span>
                                {% else %}
                                    <span class="inline-flex items-center gap-1.5 bg-slate-800 text-slate-400 text-xs px-3 py-1 rounded-full font-medium">
                                        Standard (1º Grátis)
                                    </span>
                                {% endif %}
                            </td>
                            <td class="p-4 text-center">
                                {% if user[0] != 'cachorrofrito7@gmail.com' %}
                                <form action="/admin/toggle-vip" method="POST" class="inline">
                                    <input type="hidden" name="email_alvo" value="{{ user[0] }}">
                                    {% if user[4] == 1 %}
                                        <button type="submit" class="bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-xs px-3.5 py-1.5 rounded-xl font-bold transition shadow-sm">Remover VIP</button>
                                    {% else %}
                                        <button type="submit" class="bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border border-sky-500/30 text-xs px-3.5 py-1.5 rounded-xl font-bold transition shadow-sm">Tornar VIP</button>
                                    {% endif %}
                                </form>
                                {% else %}
                                <span class="text-xs text-slate-500 font-medium italic">Master Admin</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

HTML_INDEX = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DataCleaner Pro Enterprise - Higienização e Validação de Leads</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>.glass { background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(56, 189, 248, 0.15); }</style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col justify-between font-sans antialiased selection:bg-sky-500 selection:text-slate-950">
    <header class="w-full border-b border-slate-900 bg-slate-950/80 sticky top-0 z-50 backdrop-blur">
        <div class="max-w-6xl mx-auto px-6 h-20 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400 shadow-lg shadow-sky-500/10">
                    <i class="fa-solid fa-shield-halved"></i>
                </div>
                <span class="text-xl font-black tracking-tight text-white">DataCleaner <span class="text-sky-400">Enterprise</span></span>
            </div>
            <div class="flex items-center gap-4">
                <a href="/login_view" class="text-xs font-bold text-slate-300 hover:text-white transition px-4 py-2">Entrar</a>
                <a href="/login_view?modo=registro" class="bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-black px-5 py-2.5 rounded-xl transition shadow-lg shadow-sky-500/25">Teste Grátis</a>
            </div>
        </div>
    </header>
    <main class="max-w-6xl mx-auto px-6 py-24 flex-1 text-center">
        <div class="max-w-3xl mx-auto mb-16">
            <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs font-bold mb-6 shadow-sm">
                <i class="fa-solid fa-bolt text-amber-400"></i> Suporte a Big Data (Streaming em Lotes) e Validação DNS de E-mails
            </div>
            <h1 class="text-4xl sm:text-6xl font-black tracking-tight text-white mb-6 leading-[1.1]">
                Transforme bases de dados sujas em <span class="text-transparent bg-clip-text bg-gradient-to-r from-sky-400 to-emerald-400">Leads Prontos para Vendas</span>
            </h1>
            <p class="text-slate-400 text-base sm:text-lg mb-10 leading-relaxed">
                Higienização automatizada em larga escala, validação de e-mails ativos via DNS, normalização de telemóveis para WhatsApp e API dedicada para CRMs. O seu 1º arquivo é totalmente grátis.
            </p>
            <div class="flex flex-col sm:flex-row items-center justify-center gap-4">
                <a href="/login_view?modo=registro" class="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-slate-950 font-black px-8 py-4 rounded-2xl shadow-xl shadow-sky-500/25 transition transform hover:-translate-y-0.5 text-sm">
                    <i class="fa-solid fa-rocket"></i> Experimentar Grátis Agora
                </a>
                <a href="/login_view" class="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-800 font-bold px-8 py-4 rounded-2xl transition text-sm">
                    <i class="fa-solid fa-right-to-bracket"></i> Aceder ao Painel
                </a>
            </div>
        </div>
    </main>
    <footer class="w-full border-t border-slate-900 bg-slate-950 py-8 text-center text-xs text-slate-500">
        <p>&copy; 2026 DataCleaner Enterprise. Todos os direitos reservados. Conformidade LGPD rigorosa.</p>
    </footer>
</body>
</html>
"""

HTML_LOGIN = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acesso - DataCleaner Enterprise</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>.glass { background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(20px); border: 1px solid rgba(56, 189, 248, 0.15); }</style>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen relative overflow-hidden font-sans antialiased">
    <div class="glass p-8 sm:p-10 rounded-3xl shadow-2xl max-w-md w-full relative z-10 mx-4 border border-slate-800">
        <div class="text-center mb-6">
            <a href="/" class="text-xs text-sky-400 hover:text-sky-300 transition font-semibold mb-3 inline-block">← Voltar à página inicial</a>
            <h1 class="text-2xl font-black text-white tracking-tight">DataCleaner <span class="text-sky-400">Enterprise</span></h1>
            <p class="text-xs text-slate-400 mt-1">O seu <strong class="text-emerald-400">primeiro arquivo é 100% grátis</strong>!</p>
        </div>
        
        <div class="flex bg-slate-950 p-1.5 rounded-2xl mb-6 border border-slate-800/80 shadow-inner">
            <button type="button" onclick="mudarAba('login')" id="btnTabLogin" class="flex-1 py-2.5 text-xs font-black rounded-xl transition duration-200 bg-sky-500 text-slate-950 shadow-md">Entrar</button>
            <button type="button" onclick="mudarAba('registro')" id="btnTabRegistro" class="flex-1 py-2.5 text-xs font-black rounded-xl transition duration-200 text-slate-400 hover:text-white">Teste Grátis</button>
            <button type="button" onclick="mudarAba('recuperar')" id="btnTabRecuperar" class="flex-1 py-2.5 text-xs font-black rounded-xl transition duration-200 text-slate-400 hover:text-white">Recuperar</button>
        </div>

        <div id="formLogin">
            {% if erro_login %}
            <div class="bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs p-3.5 rounded-xl mb-4 text-center font-bold flex items-center justify-center gap-2">
                <i class="fa-solid fa-circle-exclamation"></i> {{ erro_login }}
            </div>
            {% endif %}
            <form action="/login" method="POST" class="space-y-4">
                <div>
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-bold">E-mail</label>
                    <input type="email" name="email" required placeholder="seu@email.com" class="w-full bg-slate-950 border border-slate-800 text-slate-200 rounded-xl px-4 py-3.5 focus:outline-none focus:border-sky-500 text-sm font-medium">
                </div>
                <div>
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-bold">Senha</label>
                    <input type="password" name="senha" required placeholder="••••••••" class="w-full bg-slate-950 border border-slate-800 text-slate-200 rounded-xl px-4 py-3.5 focus:outline-none focus:border-sky-500 text-sm font-medium">
                </div>
                <button type="submit" class="w-full bg-sky-500 hover:bg-sky-400 text-slate-950 font-black py-4 rounded-xl transition text-sm shadow-lg shadow-sky-500/20 mt-2">Aceder ao Sistema</button>
            </form>
        </div>

        <div id="formRegistro" class="hidden">
            {% if erro_reg %}
            <div class="bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs p-3.5 rounded-xl mb-4 text-center font-bold flex items-center justify-center gap-2">
                <i class="fa-solid fa-circle-exclamation"></i> {{ erro_reg }}
            </div>
            {% endif %}
            <form action="/registrar" method="POST" class="space-y-4">
                <div>
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-bold">E-mail</label>
                    <input type="email" name="email" required placeholder="seu@email.com" class="w-full bg-slate-950 border border-slate-800 text-slate-200 rounded-xl px-4 py-3.5 focus:outline-none focus:border-sky-500 text-sm font-medium">
                </div>
                <div>
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-bold">CPF (Registo Único)</label>
                    <input type="text" name="cpf" id="cpf" required placeholder="000.000.000-00" maxlength="14" oninput="mascaraCpf(this)" class="w-full bg-slate-950 border border-slate-800 text-slate-200 rounded-xl px-4 py-3.5 focus:outline-none focus:border-sky-500 text-sm font-medium">
                </div>
                <div>
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-bold">Criar Senha</label>
                    <input type="password" name="senha" required placeholder="••••••••" class="w-full bg-slate-950 border border-slate-800 text-slate-200 rounded-xl px-4 py-3.5 focus:outline-none focus:border-sky-500 text-sm font-medium">
                </div>
                <button type="submit" class="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black py-4 rounded-xl transition text-sm shadow-lg shadow-emerald-500/20 mt-2">Resgatar 1º Arquivo Grátis</button>
            </form>
        </div>

        <div id="formRecuperar" class="hidden">
            {% if sucesso_rec %}
            <div class="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs p-3.5 rounded-xl mb-4 text-center font-bold">{{ sucesso_rec }}</div>
            {% endif %}
            {% if erro_rec %}
            <div class="bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs p-3.5 rounded-xl mb-4 text-center font-bold">{{ erro_rec }}</div>
            {% endif %}
            <form action="/recuperar" method="POST" class="space-y-4">
                <div>
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-bold">E-mail Cadastrado</label>
                    <input type="email" name="email" required placeholder="seu@email.com" class="w-full bg-slate-950 border border-slate-800 text-slate-200 rounded-xl px-4 py-3.5 focus:outline-none focus:border-sky-500 text-sm font-medium">
                </div>
                <div>
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-bold">CPF Cadastrado</label>
                    <input type="text" name="cpf" required placeholder="000.000.000-00" maxlength="14" oninput="mascaraCpf(this)" class="w-full bg-slate-950 border border-slate-800 text-slate-200 rounded-xl px-4 py-3.5 focus:outline-none focus:border-sky-500 text-sm font-medium">
                </div>
                <div>
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-bold">Nova Senha</label>
                    <input type="password" name="nova_senha" required placeholder="••••••••" class="w-full bg-slate-950 border border-slate-800 text-slate-200 rounded-xl px-4 py-3.5 focus:outline-none focus:border-sky-500 text-sm font-medium">
                </div>
                <button type="submit" class="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-4 rounded-xl transition text-sm shadow-lg shadow-amber-500/20 mt-2">Redefinir Senha</button>
            </form>
        </div>
    </div>
    <script>
        function mudarAba(aba) {
            let fLogin = document.getElementById('formLogin');
            let fReg = document.getElementById('formRegistro');
            let fRec = document.getElementById('formRecuperar');
            let bLogin = document.getElementById('btnTabLogin');
            let bReg = document.getElementById('btnTabRegistro');
            let bRec = document.getElementById('btnTabRecuperar');
            
            fLogin.classList.add('hidden'); fReg.classList.add('hidden'); fRec.classList.add('hidden');
            bLogin.className = "flex-1 py-2.5 text-xs font-black rounded-xl text-slate-400 hover:text-white";
            bReg.className = "flex-1 py-2.5 text-xs font-black rounded-xl text-slate-400 hover:text-white";
            bRec.className = "flex-1 py-2.5 text-xs font-black rounded-xl text-slate-400 hover:text-white";

            if(aba === 'login') {
                fLogin.classList.remove('hidden');
                bLogin.className = "flex-1 py-2.5 text-xs font-black rounded-xl bg-sky-500 text-slate-950 shadow-md";
            } else if(aba === 'registro') {
                fReg.classList.remove('hidden');
                bReg.className = "flex-1 py-2.5 text-xs font-black rounded-xl bg-emerald-500 text-slate-950 shadow-md";
            } else {
                fRec.classList.remove('hidden');
                bRec.className = "flex-1 py-2.5 text-xs font-black rounded-xl bg-amber-500 text-slate-950 shadow-md";
            }
        }
        
        const urlParams = new URLSearchParams(window.location.search);
        if(urlParams.get('modo') === 'registro') { mudarAba('registro'); }
        {% if aba_ativa == 'registro' %} mudarAba('registro'); {% endif %}
        {% if aba_ativa == 'recuperar' %} mudarAba('recuperar'); {% endif %}
        
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

HTML_PAINEL = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Painel Enterprise - DataCleaner Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>.glass { background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(20px); border: 1px solid rgba(56, 189, 248, 0.15); }</style>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen font-sans antialiased py-12">
    <div class="glass p-8 sm:p-10 rounded-3xl shadow-2xl max-w-xl w-full relative mx-4 border border-slate-800">
        <div class="flex justify-between items-center mb-8 pb-4 border-b border-slate-800/80">
            <span class="text-xs font-bold text-slate-300 bg-slate-950 px-3.5 py-1.5 rounded-xl border border-slate-800 flex items-center gap-2">
                <i class="fa-solid fa-user text-sky-400"></i> {{ email }}
            </span>
            <div class="flex items-center gap-3">
                {% if email.lower() == 'cachorrofrito7@gmail.com' %}
                <a href="/admin" class="text-xs font-black text-sky-400 bg-sky-500/10 border border-sky-500/30 px-3 py-1.5 rounded-xl hover:bg-sky-500/25 transition">Admin</a>
                {% endif %}
                <a href="/logout" class="text-xs font-bold text-rose-400 hover:text-rose-300 transition px-2 py-1">Terminar Sessão</a>
            </div>
        </div>
        
        <div id="uploadCard">
            <h2 class="text-2xl font-black text-white mb-2 tracking-tight">Carregar Arquivo (Big Data Support)</h2>
            <p class="text-slate-400 text-xs sm:text-sm mb-6 leading-relaxed">Envie o seu arquivo CSV ou Excel. O motor aplica streaming em lotes, validação DNS de e-mails, formatação de telemóveis e exclusão temporizada (LGPD).</p>
            
            <form action="/cotar" method="POST" enctype="multipart/form-data" onsubmit="mostrarLoader()">
                <label id="dropZone" class="border-2 border-dashed border-slate-700 hover:border-sky-500 bg-slate-950/50 hover:bg-slate-950 p-8 rounded-2xl cursor-pointer flex flex-col items-center justify-center transition duration-200 block text-center group mb-6">
                    <div class="w-14 h-14 rounded-2xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 text-2xl mb-3 group-hover:scale-110 transition shadow-lg">
                        <i class="fa-solid fa-cloud-arrow-up"></i>
                    </div>
                    <span id="fileNameDisplay" class="text-sm font-bold text-slate-200 mb-1">Clique para selecionar o arquivo</span>
                    <span class="text-xs text-slate-500 font-medium">Formatos aceites: .csv ou .xlsx</span>
                    <input type="file" id="fileInput" name="file" accept=".csv, .xlsx" required class="hidden" onchange="atualizarNomeArquivo(this)">
                </label>
                <button type="submit" id="btnProcessar" class="w-full bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-slate-950 font-black py-4 rounded-xl transition text-sm shadow-xl shadow-sky-500/25 flex items-center justify-center gap-2">
                    <i class="fa-solid fa-wand-magic-sparkles"></i> Processar e Higienizar Agora
                </button>
            </form>

            <!-- Credenciais de API para automações (n8n / Make) -->
            <div class="mt-8 pt-6 border-t border-slate-800/80">
                <h4 class="text-xs font-black uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-2">
                    <i class="fa-solid fa-key text-sky-400"></i> Sua Token de API para Automações:
                </h4>
                <div class="flex items-center gap-2">
                    <input type="text" value="{{ api_token }}" readonly class="w-full bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded-lg p-2.5 font-mono select-all">
                </div>
                <p class="text-[10px] text-slate-500 mt-1">Use este token para integrar o DataCleaner diretamente ao n8n, Make ou CRM via endpoint `/api/v1/higienizar`.</p>
            </div>
        </div>

        <div id="loadingCard" class="hidden text-center py-12">
            <div class="inline-block w-12 h-12 border-4 border-sky-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <h3 class="text-lg font-black text-white mb-1">A processar base em alta performance...</h3>
            <p class="text-slate-400 text-xs">O motor está a validar e-mails via DNS e a estruturar lotes sem limite de linhas.</p>
        </div>
    </div>
    <script>
        function atualizarNomeArquivo(input) {
            if (input.files && input.files[0]) {
                let nome = input.files[0].name;
                document.getElementById('fileNameDisplay').textContent = "📄 " + nome;
                document.getElementById('fileNameDisplay').classList.add("text-sky-400", "font-black");
                document.getElementById('dropZone').classList.add("border-sky-500", "bg-sky-500/5");
            }
        }
        function mostrarLoader() {
            let fileInput = document.getElementById('fileInput');
            if(fileInput.files.length > 0) {
                document.getElementById('uploadCard').classList.add('hidden');
                document.getElementById('loadingCard').classList.remove('hidden');
            }
        }
    </script>
</body>
</html>
"""

HTML_PAGAMENTO = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pagamento Pix - DataCleaner Enterprise</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>.glass { background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(20px); border: 1px solid rgba(56, 189, 248, 0.15); }</style>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen font-sans antialiased">
    <div class="glass p-8 sm:p-10 rounded-3xl shadow-2xl max-w-md w-full text-center border border-slate-800 mx-4">
        <h2 class="text-2xl font-black text-white mb-1 tracking-tight">Finalizar Pagamento Pix</h2>
        <p class="text-slate-400 text-xs sm:text-sm mb-4">Arquivo: <span class="text-slate-200 font-bold">{{ filename }}</span> (<span class="text-sky-400 font-semibold">{{ total_linhas }} leads</span>)</p>
        
        <div class="w-full bg-slate-950 rounded-full h-2 mb-2 overflow-hidden border border-slate-800">
            <div id="progressBar" class="bg-amber-500 h-2 rounded-full transition-all duration-1000" style="width: 100%"></div>
        </div>
        <div class="flex justify-between items-center text-xs text-slate-400 mb-6 font-bold">
            <span>⏳ Expira em: <strong id="countdown" class="text-amber-400">05:00</strong></span>
            <span>R$ 0,20 / lead</span>
        </div>

        <div class="bg-slate-950 p-5 rounded-2xl mb-6 border border-slate-800/80 shadow-inner">
            <span class="text-xs uppercase tracking-wider text-slate-400 font-bold">Total a Pagar</span>
            <div class="text-3xl font-black text-emerald-400 mt-1">R$ {{ valor_total }}</div>
        </div>
        <div class="bg-white p-4 rounded-2xl inline-block mb-6 shadow-xl border border-slate-200"><div id="qrcode"></div></div>
        <input type="text" id="pixCode" value="{{ qr_code }}" readonly class="w-full bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded-xl p-3.5 mb-4 select-all font-mono">
        <button onclick="copiarPix()" id="btnCopiar" class="w-full bg-sky-500 hover:bg-sky-400 text-slate-950 font-black py-3.5 rounded-xl transition mb-3 shadow-lg shadow-sky-500/25 text-sm">📋 Copiar Código Pix</button>
        
        <div id="statusPagamento" class="bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs py-3 px-4 rounded-xl font-bold flex items-center justify-center gap-2 mb-3">
            <i class="fa-solid fa-spinner animate-spin"></i> A aguardar compensação automática do Pix...
        </div>

        <a id="btnLiberado" href="/download_liberado" class="hidden w-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black py-3.5 rounded-xl transition text-center text-sm shadow-lg shadow-emerald-500/25 block">
            <i class="fa-solid fa-circle-check"></i> Pagamento Aprovado! Aceder ao Download
        </a>
    </div>
    <script>
        if("{{ qr_code }}") { new QRCode(document.getElementById("qrcode"), { text: "{{ qr_code }}", width: 180, height: 180 }); }
        let t = 300;
        let totalTime = 300;
        let timer = setInterval(() => {
            let m = Math.floor(t / 60), s = t % 60;
            document.getElementById("countdown").textContent = (m<10?"0"+m:m) + ":" + (s<10?"0"+s:s);
            let pct = (t / totalTime) * 100;
            document.getElementById("progressBar").style.width = pct + "%";
            if(t <= 0) { clearInterval(timer); window.location.href = "/painel"; }
            t--;
        }, 1000);

        setInterval(() => {
            fetch('/checar_status_ajax')
                .then(response => response.json())
                .then(data => {
                    if (data.pago) {
                        document.getElementById('statusPagamento').classList.add('hidden');
                        document.getElementById('btnLiberado').classList.remove('hidden');
                    }
                }).catch(err => console.log(err));
        }, 4000);

        function copiarPix() {
            let c = document.getElementById("pixCode"); c.select(); navigator.clipboard.writeText(c.value);
            let b = document.getElementById("btnCopiar"); b.innerText = "✅ Copiado!"; setTimeout(() => b.innerText = "📋 Copiar Código Pix", 3000);
        }
    </script>
</body>
</html>
"""

HTML_AGUARDANDO = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8"><title>Aguardando - DataCleaner Enterprise</title><script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>.glass { background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(20px); border: 1px solid rgba(56, 189, 248, 0.15); }</style>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen font-sans antialiased">
    <div class="glass p-8 sm:p-10 rounded-3xl shadow-2xl max-w-md w-full text-center border border-slate-800 mx-4">
        <div class="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 text-xl mx-auto mb-4">
            <i class="fa-solid fa-spinner animate-spin"></i>
        </div>
        <h2 class="text-2xl font-black text-amber-400 mb-2 tracking-tight">Aguardando Compensação</h2>
        <p class="text-slate-400 text-xs sm:text-sm mb-6 leading-relaxed">{{ aviso }}</p>
        <a href="/verificar_pagamento" class="block w-full bg-sky-500 hover:bg-sky-400 text-slate-950 font-black py-3.5 rounded-xl transition mb-3 text-center text-sm shadow-lg shadow-sky-500/20">🔄 Verificar Novamente</a>
        <a href="/pagamento" class="block text-xs font-bold text-slate-400 hover:text-white transition">← Voltar ao QR Code</a>
    </div>
</body>
</html>
"""

HTML_DOWNLOAD = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8"><title>Download - DataCleaner Enterprise</title><script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>.glass { background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(20px); border: 1px solid rgba(56, 189, 248, 0.15); }</style>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen font-sans antialiased">
    <div class="glass p-8 sm:p-10 rounded-3xl shadow-2xl max-w-md w-full text-center border border-slate-800 mx-4">
        <div class="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 text-2xl mx-auto mb-4 shadow-lg shadow-emerald-500/10">
            <i class="fa-solid fa-circle-check"></i>
        </div>
        <h2 class="text-2xl font-black text-emerald-400 mb-2 tracking-tight">Higienizado com Sucesso!</h2>
        <p class="text-slate-400 text-xs sm:text-sm mb-8 leading-relaxed">Dados validados via DNS, duplicados removidos e ordenação alfabética concluída.</p>
        <form action="/processar_e_baixar" method="POST">
            <button type="submit" class="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black py-4 rounded-xl transition mb-4 shadow-xl shadow-emerald-500/25 text-sm flex items-center justify-center gap-2">
                <i class="fa-solid fa-download"></i> Baixar Arquivo Agora
            </button>
        </form>
        <a href="/painel" class="block text-xs font-bold text-slate-400 hover:text-slate-200 transition">Processar outro arquivo</a>
    </div>
</body>
</html>
"""

# ==========================================
# ROTAS DO APLICATIVO
# ==========================================

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

    if email == ADMIN_EMAIL:
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
    api_token = str(uuid.uuid4())

    if not email or not senha or not cpf:
        return render_template_string(HTML_LOGIN, erro_reg="Preencha todos os campos.", aba_ativa="registro")
    if len(cpf) != 11:
        return render_template_string(HTML_LOGIN, erro_reg="CPF inválido (11 dígitos).", aba_ativa="registro")

    conn = sqlite3.connect('datacleaner.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO usuarios (email, senha, cpf, teste_usado, is_vip, api_token) VALUES (?, ?, ?, 0, 0, ?)', (email, senha, cpf, api_token))
        conn.commit()
        session['usuario'] = email
        return redirect(url_for('painel'))
    except sqlite3.IntegrityError:
        return render_template_string(HTML_LOGIN, erro_reg="Este CPF ou e-mail já possui uma conta.", aba_ativa="registro")
    finally:
        conn.close()

@app.route('/recuperar', methods=['POST'])
def recuperar():
    email = request.form.get('email', '').strip().lower()
    cpf = re.sub(r'\D', '', request.form.get('cpf', ''))
    nova_senha = request.form.get('nova_senha', '').strip()

    if not email or not cpf or not nova_senha:
        return render_template_string(HTML_LOGIN, erro_rec="Preencha todos os campos para recuperar a senha.", aba_ativa="recuperar")

    conn = sqlite3.connect('datacleaner.db')
    cursor = conn.cursor()
    user = cursor.execute('SELECT email FROM usuarios WHERE email = ? AND cpf = ?', (email, cpf)).fetchone()
    if user:
        cursor.execute('UPDATE usuarios SET senha = ? WHERE email = ?', (nova_senha, email))
        conn.commit()
        conn.close()
        return render_template_string(HTML_LOGIN, sucesso_rec="Senha redefinida com sucesso! Faça login.", aba_ativa="login")
    
    conn.close()
    return render_template_string(HTML_LOGIN, erro_rec="E-mail ou CPF não conferem.", aba_ativa="recuperar")

@app.route('/painel')
def painel():
    if 'usuario' not in session:
        return redirect(url_for('index'))
    
    conn = sqlite3.connect('datacleaner.db')
    cursor = conn.cursor()
    res = cursor.execute('SELECT api_token FROM usuarios WHERE email = ?', (session['usuario'],)).fetchone()
    api_token = res[0] if res and res[0] else "N/A"
    conn.close()

    return render_template_string(HTML_PAINEL, email=session['usuario'], api_token=api_token)

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = sqlite3.connect('datacleaner.db')
    cursor = conn.cursor()
    
    try:
        total_users = cursor.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    except:
        total_users = 0

    try:
        total_cleanings = cursor.execute("SELECT COUNT(*) FROM usage_logs").fetchone()[0]
    except:
        total_cleanings = 0

    try:
        total_vip = cursor.execute("SELECT COUNT(*) FROM usuarios WHERE is_vip = 1").fetchone()[0]
    except:
        total_vip = 0

    try:
        users = cursor.execute("SELECT email, senha, cpf, teste_usado, is_vip, api_token FROM usuarios ORDER BY email DESC").fetchall()
    except:
        users = []

    conn.close()
    return render_template_string(HTML_ADMIN, total_users=total_users, total_cleanings=total_cleanings, total_vip=total_vip, users=users)

@app.route('/admin/toggle-vip', methods=['POST'])
@admin_required
def admin_toggle_vip():
    email_alvo = request.form.get('email_alvo')
    if email_alvo and email_alvo.lower() != ADMIN_EMAIL.lower():
        conn = sqlite3.connect('datacleaner.db')
        cursor = conn.cursor()
        user = cursor.execute("SELECT is_vip FROM usuarios WHERE email = ?", (email_alvo,)).fetchone()
        if user:
            novo_status = 0 if user[0] == 1 else 1
            cursor.execute("UPDATE usuarios SET is_vip = ? WHERE email = ?", (novo_status, email_alvo))
            conn.commit()
        conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/cotar', methods=['POST'])
def cotar():
    if 'usuario' not in session:
        return redirect(url_for('index'))
    if 'file' not in request.files:
        return "Nenhum arquivo enviado", 400
    
    file = request.files['file']
    if file.filename == '':
        return "Arquivo não selecionado", 400

    if file:
        input_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(input_path)
        
        # Contagem segura de linhas para arquivos grandes (streaming chunks)
        total_linhas = 0
        if file.filename.endswith('.csv'):
            for chunk in pd.read_csv(input_path, chunksize=10000):
                total_linhas += len(chunk)
        else:
            df_temp = pd.read_excel(input_path)
            total_linhas = len(df_temp)
            del df_temp

        usuario_atual = session.get('usuario')
        
        try:
            conn_log = sqlite3.connect('datacleaner.db')
            curr_log = conn_log.cursor()
            curr_log.execute("INSERT INTO usage_logs (email) VALUES (?)", (usuario_atual,))
            conn_log.commit()
            conn_log.close()
        except:
            pass

        conn = sqlite3.connect('datacleaner.db')
        cursor = conn.cursor()
        cursor.execute('SELECT teste_usado, is_vip FROM usuarios WHERE email = ?', (usuario_atual,))
        res = cursor.fetchone()
        
        is_vip = res[1] == 1 if res else False
        teste_usado = res[0] == 1 if res else False

        if usuario_atual == ADMIN_EMAIL or is_vip:
            valor_total = 0.00
        elif not teste_usado:
            valor_total = 0.00
            cursor.execute('UPDATE usuarios SET teste_usado = 1 WHERE email = ?', (usuario_atual,))
            conn.commit()
        else:
            valor_total = max(10.00, float(total_linhas * 0.20))
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
        session['pago'] = False
        return redirect(url_for('tela_pagamento'))

@app.route('/pagamento')
def tela_pagamento():
    if 'usuario' not in session or 'filename_pendente' not in session:
        return redirect(url_for('painel'))
    return render_template_string(HTML_PAGAMENTO, filename=session['filename_pendente'], total_linhas=session['total_linhas'], valor_total=session['valor_total'], qr_code=session.get('qr_code', ''))

@app.route('/checar_status_ajax')
def checar_status_ajax():
    if 'usuario' not in session: return jsonify({"pago": False})
    if session.get('payment_id') == "manual_pix":
        session['pago'] = True
        return jsonify({"pago": True})
    try:
        resp = requests.get(f"https://api.mercadopago.com/v1/payments/{session.get('payment_id')}", headers={"Authorization": f"Bearer {ACCESS_TOKEN_MP}"}, timeout=10)
        if resp.status_code == 200 and resp.json().get("status") == "approved":
            session['pago'] = True
            return jsonify({"pago": True})
    except:
        pass
    return jsonify({"pago": session.get('pago', False)})

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
    if not os.path.exists(input_path): return "Arquivo expirado", 404
    
    output_filename = "limpo_" + filename
    output_path = os.path.join(UPLOAD_FOLDER, output_filename)

    # Processamento em lotes (Streaming Chunks) para poupar RAM com arquivos grandes
    if filename.endswith('.csv'):
        primeiro_bloco = True
        for df in pd.read_csv(input_path, chunksize=10000):
            for col in df.columns:
                cl = col.lower()
                if 'nome' in cl: df[col] = df[col].apply(limpar_nome)
                elif 'email' in cl or 'e-mail' in cl:
                    df[col] = df[col].apply(limpar_email)
                    df['email_valido'] = df[col].apply(validar_dominio_email)
                elif 'tel' in cl or 'cel' in cl or 'fone' in cl or 'whatsapp' in cl:
                    df[col] = df[col].apply(limpar_telefone)
            
            df = df.drop_duplicates()
            coluna_nome = next((c for c in df.columns if 'nome' in c.lower()), None)
            if coluna_nome: df = df.sort_values(by=coluna_nome, ascending=True)

            df.to_csv(output_path, mode='w' if primeiro_bloco else 'a', index=False, header=primeiro_bloco, encoding='utf-8-sig')
            primeiro_bloco = False
    else:
        df = pd.read_excel(input_path)
        for col in df.columns:
            cl = col.lower()
            if 'nome' in cl: df[col] = df[col].apply(limpar_nome)
            elif 'email' in cl or 'e-mail' in cl:
                df[col] = df[col].apply(limpar_email)
                df['email_valido'] = df[col].apply(validar_dominio_email)
            elif 'tel' in cl or 'cel' in cl or 'fone' in cl or 'whatsapp' in cl:
                df[col] = df[col].apply(limpar_telefone)
                
        df = df.drop_duplicates()
        coluna_nome = next((c for c in df.columns if 'nome' in c.lower()), None)
        if coluna_nome: df = df.sort_values(by=coluna_nome, ascending=True)
        df.to_excel(output_path, index=False)
    
    response = send_file(output_path, as_attachment=True)
    @response.call_on_close
    def limpar_tudo():
        try:
            if os.path.exists(input_path): os.remove(input_path)
            if os.path.exists(output_path): os.remove(output_path)
            session.pop('pago', None)
            session.pop('filename_pendente', None)
        except: pass
    return response

# Endpoint API Gratuito para Integrações (n8n / Make / Webhooks)
@app.route('/api/v1/higienizar', methods=['POST'])
def api_higienizar():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"erro": "Token de API não fornecido"}), 401
    
    conn = sqlite3.connect('datacleaner.db')
    cursor = conn.cursor()
    user = cursor.execute('SELECT email FROM usuarios WHERE api_token = ?', (token,)).fetchone()
    conn.close()

    if not user:
        return jsonify({"erro": "Token de API inválido"}), 403

    if 'file' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400
    
    file = request.files['file']
    input_path = os.path.join(UPLOAD_FOLDER, "api_" + file.filename)
    file.save(input_path)

    df = pd.read_csv(input_path) if file.filename.endswith('.csv') else pd.read_excel(input_path)
    for col in df.columns:
        cl = col.lower()
        if 'nome' in cl: df[col] = df[col].apply(limpar_nome)
        elif 'email' in cl or 'e-mail' in cl: df[col] = df[col].apply(limpar_email)
        elif 'tel' in cl or 'cel' in cl or 'fone' in cl or 'whatsapp' in cl: df[col] = df[col].apply(limpar_telefone)
            
    df = df.drop_duplicates()
    output_path = os.path.join(UPLOAD_FOLDER, "limpo_api_" + file.filename)
    if file.filename.endswith('.csv'): df.to_csv(output_path, index=False, encoding='utf-8-sig')
    else: df.to_excel(output_path, index=False)

    return send_file(output_path, as_attachment=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)