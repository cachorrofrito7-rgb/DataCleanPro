from flask import Flask, render_template_string, request, send_file, redirect, url_for, session, flash, jsonify
from datetime import timedelta
from functools import wraps
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
            is_vip INTEGER DEFAULT 0
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

# ==========================================
# INTERFACES DE UTILIZADOR (UI / UX SaaS)
# ==========================================

HTML_ADMIN = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Painel de Controlo - DataCleaner Pro</title>
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
                    <h1 class="text-2xl font-black tracking-tight text-white">Painel de Controlo <span class="text-sky-400">Admin</span></h1>
                </div>
                <p class="text-xs text-slate-400 mt-1">Gestão de utilizadores, métricas globais e concessão de acessos VIP para parceiros.</p>
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
                <span class="text-xs uppercase text-slate-400 font-bold tracking-wider">Utilizadores VIP / Parceiros</span>
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
                            <th class="p-4 font-semibold">Status do Plano</th>
                            <th class="p-4 font-semibold text-center">Ação VIP (Parceiro)</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800/60">
                        {% for user in users %}
                        <tr class="hover:bg-slate-800/30 transition">
                            <td class="p-4 font-medium text-slate-200">{{ user[0] }}</td>
                            <td class="p-4 text-slate-400 font-mono text-xs">{{ user[2] }}</td>
                            <td class="p-4">
                                {% if user[4] == 1 or user[0] == 'cachorrofrito7@gmail.com' %}
                                    <span class="inline-flex items-center gap-1.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs px-3 py-1 rounded-full font-bold">
                                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> VIP Ilimitado
                                    </span>
                                {% else %}
                                    <span class="inline-flex items-center gap-1.5 bg-slate-800 text-slate-400 text-xs px-3 py-1 rounded-full font-medium">
                                        Gratuito (1º Arquivo Grátis)
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
    <title>DataCleaner Pro - Higienização e Ordenação Inteligente de Leads</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col justify-between font-sans antialiased">
    <header class="w-full border-b border-slate-900 bg-slate-950/80 sticky top-0 z-50 backdrop-blur">
        <div class="max-w-6xl mx-auto px-6 h-20 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
                    <i class="fa-solid fa-shield-halved"></i>
                </div>
                <span class="text-xl font-black tracking-tight text-white">DataCleaner <span class="text-sky-400">Pro</span></span>
            </div>
            <div class="flex items-center gap-4">
                <a href="/auth" class="text-xs font-bold text-slate-300 hover:text-white transition px-4 py-2">Entrar</a>
                <a href="/auth?modo=registro" class="bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-black px-5 py-2.5 rounded-xl transition shadow-lg shadow-sky-500/25">Teste Grátis</a>
            </div>
        </div>
    </header>
    <main class="max-w-6xl mx-auto px-6 py-20 flex-1 text-center">
        <div class="max-w-3xl mx-auto mb-16">
            <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs font-bold mb-6">
                <i class="fa-solid fa-bolt"></i> O primeiro arquivo higienizado é totalmente grátis! Apenas R$ 0,20 por lead nos demais.
            </div>
            <h1 class="text-4xl sm:text-6xl font-black tracking-tight text-white mb-6 leading-[1.1]">
                Transforme bases de dados sujas em <span class="text-transparent bg-clip-text bg-gradient-to-r from-sky-400 to-emerald-400">Leads Prontos para Vendas</span>
            </h1>
            <p class="text-slate-400 text-base sm:text-lg mb-10 leading-relaxed">
                Automatize a correção ortográfica de nomes, formatação correta de telemóveis/telefones com DDD, normalização de e-mails, eliminação de duplicados e ordenação alfabética de planilhas CSV e Excel em segundos.
            </p>
            <a href="/auth?modo=registro" class="inline-flex items-center gap-2.5 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-slate-950 font-black px-8 py-4 rounded-2xl shadow-xl shadow-sky-500/25 transition">
                <i class="fa-solid fa-rocket"></i> Começar Teste Grátis Agora (1º Arquivo Grátis)
            </a>
        </div>
    </main>
    <footer class="w-full border-t border-slate-900 bg-slate-950 py-8 text-center text-xs text-slate-500">
        <p>&copy; 2026 DataCleaner Pro. Todos os direitos reservados.</p>
    </footer>
</body>
</html>
"""

HTML_AUTH = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acesso - DataCleaner Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>.glass { background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(20px); border: 1px solid rgba(56, 189, 248, 0.15); }</style>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen font-sans antialiased">
    <div class="glass p-8 sm:p-10 rounded-3xl shadow-2xl max-w-md w-full relative z-10 mx-4 border border-slate-800">
        <div class="text-center mb-6">
            <a href="/" class="text-xs text-sky-400 hover:text-sky-300 transition font-semibold mb-3 inline-block">← Voltar à página inicial</a>
            <h1 class="text-2xl font-black text-white tracking-tight">DataCleaner <span class="text-sky-400">Pro</span></h1>
            <p class="text-xs text-slate-400 mt-1">Crie conta e processe o seu <strong class="text-emerald-400">primeiro arquivo gratuitamente</strong>.</p>
        </div>
        
        <div class="flex bg-slate-950 p-1.5 rounded-2xl mb-6 border border-slate-800/80 shadow-inner">
            <button type="button" onclick="mudarAba('login')" id="btnTabLogin" class="flex-1 py-3 text-xs font-black rounded-xl transition duration-200 bg-sky-500 text-slate-950 shadow-md">Entrar</button>
            <button type="button" onclick="mudarAba('registro')" id="btnTabRegistro" class="flex-1 py-3 text-xs font-black rounded-xl transition duration-200 text-slate-400 hover:text-white">Criar Conta (Grátis)</button>
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
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-bold">Palavra-passe / Senha</label>
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
                    <label class="block text-xs uppercase tracking-wider text-slate-400 mb-1.5 font-bold">Criar Palavra-passe</label>
                    <input type="password" name="senha" required placeholder="••••••••" class="w-full bg-slate-950 border border-slate-800 text-slate-200 rounded-xl px-4 py-3.5 focus:outline-none focus:border-sky-500 text-sm font-medium">
                </div>
                <button type="submit" class="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black py-4 rounded-xl transition text-sm shadow-lg shadow-emerald-500/20 mt-2">Resgatar 1º Arquivo Grátis</button>
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
                bLogin.className = "flex-1 py-3 text-xs font-black rounded-xl bg-sky-500 text-slate-950 shadow-md";
                bReg.className = "flex-1 py-3 text-xs font-black rounded-xl text-slate-400 hover:text-white";
            } else {
                fLogin.classList.add('hidden'); fReg.classList.remove('hidden');
                bReg.className = "flex-1 py-3 text-xs font-black rounded-xl bg-emerald-500 text-slate-950 shadow-md";
                bLogin.className = "flex-1 py-3 text-xs font-black rounded-xl text-slate-400 hover:text-white";
            }
        }
        
        const urlParams = new URLSearchParams(window.location.search);
        if(urlParams.get('modo') === 'registro') { mudarAba('registro'); }
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

HTML_PAINEL = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <titl