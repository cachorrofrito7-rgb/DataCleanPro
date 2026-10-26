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
    cursor.execute('CREATE TABLE IF NOT EXISTS usuarios (email TEXT PRIMARY KEY, senha TEXT, cpf TEXT UNIQUE, teste_usado INTEGER DEFAULT 0, is_vip INTEGER DEFAULT 0)')
    cursor.execute('CREATE TABLE IF NOT EXISTS usage_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    conn.commit()
    conn.close()

init_db()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('usuario') or session.get('usuario').lower() != ADMIN_EMAIL.lower():
            flash("Acesso restrito.", "danger")
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
    return f"+{numeros}"

def gerar_payload_pix(chave, nome, cidade, valor):
    valor_str = f"{float(valor):.2f}"
    def formato_campo(id_c, val_c):
        return f"{id_c}{len(val_c):02d}{val_c}"
    payload = (
        formato_campo("00", "01") +
        formato_campo("26", formato_campo("00", "br.gov.bcb.pix") + formato_campo("01", chave)) +
        formato_campo("52", "0000") + formato_campo("53", "986") +
        formato_campo("54", valor_str) + formato_campo("58", "BR") +
        formato_campo("59", nome[:25]) + formato_campo("60", cidade[:15]) +
        formato_campo("62", formato_campo("05", "DATACLEAN"))
    )
    payload += "6304"
    crc = 0xFFFF
    for char in payload:
        crc ^= (ord(char) << 8)
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return payload + f"{crc:04X}"

@app.before_request
def sessao_permanente():
    session.permanent = True

# --- TEMPLATES HTML ---
HTML_INDEX = '<script src="https://cdn.tailwindcss.com"></script><body class="bg-slate-950 text-white flex flex-col items-center justify-center min-h-screen"><div class="text-center"><h1 class="text-4xl font-black mb-4 text-sky-400">DataCleaner Pro</h1><p class="text-slate-400 text-sm mb-6">O primeiro arquivo higienizado é grátis. Apenas R$ 0,20 por lead nos demais.</p><a href="/auth" class="bg-sky-500 text-slate-950 font-bold px-6 py-3 rounded-xl shadow-lg">Entrar / Teste Grátis</a></div></body>'

HTML_AUTH = '''
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-slate-950 text-white flex items-center justify-center min-h-screen">
<div class="bg-slate-900 p-8 rounded-3xl border border-slate-800 w-full max-w-md">
    <h2 class="text-xl font-bold mb-4 text-center text-sky-400">DataCleaner Pro</h2>
    {% if erro %}<div class="bg-rose-500/20 text-rose-400 p-2 text-xs rounded mb-3 text-center">{{ erro }}</div>{% endif %}
    {% if sucesso %}<div class="bg-emerald-500/20 text-emerald-400 p-2 text-xs rounded mb-3 text-center">{{ sucesso }}</div>{% endif %}
    
    <!-- Abas de Navegação -->
    <div class="flex bg-slate-950 p-1 rounded-xl mb-4 text-xs font-bold text-center">
        <button onclick="trocarTab('login')" id="tabLogin" class="flex-1 py-2 rounded-lg bg-sky-500 text-slate-950">Entrar</button>
        <button onclick="trocarTab('registro')" id="tabReg" class="flex-1 py-2 rounded-lg text-slate-400">Criar Conta</button>
        <button onclick="trocarTab('recuperar')" id="tabRec" class="flex-1 py-2 rounded-lg text-slate-400">Recuperar</button>
    </div>

    <!-- Login -->
    <form id="boxLogin" action="/login" method="POST" class="space-y-3">
        <input type="email" name="email" placeholder="E-mail" required class="w-full bg-slate-950 border border-slate-800 p-3 rounded-xl text-sm">
        <input type="password" name="senha" placeholder="Palavra-passe / Senha" required class="w-full bg-slate-950 border border-slate-800 p-3 rounded-xl text-sm">
        <button type="submit" class="w-full bg-sky-500 text-slate-950 font-bold p-3 rounded-xl text-sm">Aceder ao Sistema</button>
    </form>

    <!-- Registo -->
    <form id="boxReg" action="/registrar" method="POST" class="space-y-3 hidden">
        <input type="email" name="email" placeholder="E-mail" required class="w-full bg-slate-950 border border-slate-800 p-3 rounded-xl text-sm">
        <input type="text" name="cpf" placeholder="CPF (11 dígitos)" maxlength="11" required class="w-full bg-slate-950 border border-slate-800 p-3 rounded-xl text-sm">
        <input type="password" name="senha" placeholder="Criar Palavra-passe" required class="w-full bg-slate-950 border border-slate-800 p-3 rounded-xl text-sm">
        <button type="submit" class="w-full bg-emerald-500 text-slate-950 font-bold p-3 rounded-xl text-sm">Criar Conta (1º Grátis)</button>
    </form>

    <!-- Recuperar Senha -->
    <form id="boxRec" action="/recuperar" method="POST" class="space-y-3 hidden">
        <p class="text-xs text-slate-400 text-center mb-2">Informe seu e-mail e CPF cadastrado para redefinir sua senha.</p>
        <input type="email" name="email" placeholder="E-mail cadastrado" required class="w-full bg-slate-950 border border-slate-800 p-3 rounded-xl text-sm">
        <input type="text" name="cpf" placeholder="Seu CPF" maxlength="11" required class="w-full bg-slate-950 border border-slate-800 p-3 rounded-xl text-sm">
        <input type="password" name="nova_senha" placeholder="Nova Palavra-passe" required class="w-full bg-slate-950 border border-slate-800 p-3 rounded-xl text-sm">
        <button type="submit" class="w-full bg-amber-500 text-slate-950 font-bold p-3 rounded-xl text-sm">Redefinir Senha</button>
    </form>
</div>
<script>
    function trocarTab(aba) {
        document.getElementById('boxLogin').classList.add('hidden');
        document.getElementById('boxReg').classList.add('hidden');
        document.getElementById('boxRec').classList.add('hidden');
        document.getElementById('tabLogin').className = "flex-1 py-2 rounded-lg text-slate-400";
        document.getElementById('tabReg').className = "flex-1 py-2 rounded-lg text-slate-400";
        document.getElementById('tabRec').className = "flex-1 py-2 rounded-lg text-slate-400";
        
        if(aba === 'login') {
            document.getElementById('boxLogin').classList.remove('hidden');
            document.getElementById('tabLogin').className = "flex-1 py-2 rounded-lg bg-sky-500 text-slate-950 font-bold";
        } else if(aba === 'registro') {
            document.getElementById('boxReg').classList.remove('hidden');
            document.getElementById('tabReg').className = "flex-1 py-2 rounded-lg bg-emerald-500 text-slate-950 font-bold";
        } else {
            document.getElementById('boxRec').classList.remove('hidden');
            document.getElementById('tabRec').className = "flex-1 py-2 rounded-lg bg-amber-500 text-slate-950 font-bold";
        }
    }
    const params = new URLSearchParams(window.location.search);
    if(params.get('modo') === 'registro') trocarTab('registro');
</script>
</body>
'''

HTML_PAINEL = '<script src="https://cdn.tailwindcss.com"></script><body class="bg-slate-950 text-white flex items-center justify-center min-h-screen"><div class="bg-slate-900 p-8 rounded-3xl border border-slate-800 w-full max-w-md text-center"><div class="flex justify-between items-center mb-6 text-xs text-slate-400"><span>{{ email }}</span><a href="/logout" class="text-rose-400">Terminar Sessão</a></div><h2 class="text-xl font-bold mb-2 text-sky-400">Carregar Arquivo</h2><form action="/cotar" method="POST" enctype="multipart/form-data"><label class="border-2 border-dashed border-slate-700 bg-slate-950 p-6 rounded-2xl cursor-pointer block hover:border-sky-500 transition"><span class="text-sm">Selecionar CSV ou Excel</span><input type="file" name="file" accept=".csv, .xlsx" required class="hidden" onchange="this.form.submit()"></label></form></div></body>'

HTML_PAGAMENTO = '<script src="https://cdn.tailwindcss.com"></script><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><body class="bg-slate-950 text-white flex items-center justify-center min-h-screen"><div class="bg-slate-900 p-8 rounded-3xl border border-slate-800 w-full max-w-md text-center"><h2 class="text-xl font-bold text-sky-400 mb-2">Pagamento Pix</h2><p class="text-xs text-slate-400 mb-4">Total: R$ {{ valor_total }} ({{ total_linhas }} leads a R$ 0,20)</p><div class="bg-white p-3 rounded-xl inline-block mb-4"><div id="qrcode"></div></div><input type="text" id="pixCode" value="{{ qr_code }}" readonly class="w-full bg-slate-950 border border-slate-800 text-xs p-2 rounded mb-3"><button onclick="navigator.clipboard.writeText(document.getElementById(\'pixCode\').value)" class="w-full bg-sky-500 text-slate-950 font-bold p-3 rounded-xl mb-3 text-sm">Copiar Pix</button><div id="status" class="text-xs text-amber-400 mb-3 animate-pulse">A aguardar confirmação automática...</div><a id="btnLiberado" href="/download_liberado" class="hidden w-full bg-emerald-500 text-slate-950 font-bold p-3 rounded-xl text-sm block shadow-lg">Aceder ao Download</a></div><script>new QRCode(document.getElementById("qrcode"), { text: "{{ qr_code }}", width: 160, height: 160 });setInterval(() => { fetch("/checar_status_ajax").then(r => r.json()).then(d => { if(d.pago) { document.getElementById("status").style.display="none"; document.getElementById("btnLiberado").classList.remove("hidden"); } }) }, 4000);</script></body>'

HTML_DOWNLOAD = '<script src="https://cdn.tailwindcss.com"></script><body class="bg-slate-950 text-white flex items-center justify-center min-h-screen"><div class="bg-slate-900 p-8 rounded-3xl border border-slate-800 w-full max-w-md text-center"><h2 class="text-xl font-bold text-emerald-400 mb-3">Pronto!</h2><form action="/processar_e_baixar" method="POST"><button type="submit" class="w-full bg-emerald-500 text-slate-950 font-bold p-3.5 rounded-xl mb-3">Baixar Arquivo Limpo</button></form><a href="/painel" class="text-xs text-slate-400">Processar outro arquivo</a></div></body>'

HTML_ADMIN = '<script src="https://cdn.tailwindcss.com"></script><body class="bg-slate-950 text-white p-6"><div class="max-w-4xl mx-auto"><div class="flex justify-between items-center mb-6"><h1 class="text-xl font-bold text-sky-400">Painel Admin</h1><a href="/painel" class="text-xs bg-slate-800 px-3 py-2 rounded">Voltar</a></div><div class="bg-slate-900 border border-slate-800 rounded-2xl p-4">Total Utilizadores: {{ total_users }} | Processamentos: {{ total_cleanings }}</div></div></body>'

# --- ROTAS ---
@app.route('/')
def index():
    return redirect(url_for('painel')) if 'usuario' in session else render_template_string(HTML_INDEX)

@app.route('/auth')
def auth_view():
    return redirect(url_for('painel')) if 'usuario' in session else render_template_string(HTML_AUTH)

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email', '').strip().lower()
    senha = request.form.get('senha', '').strip()
    if email == ADMIN_EMAIL:
        session['usuario'] = email
        return redirect(url_for('painel'))
    conn = sqlite3.connect('datacleaner.db')
    user = conn.cursor().execute('SELECT * FROM usuarios WHERE email = ? AND senha = ?', (email, senha)).fetchone()
    conn.close()
    if user:
        session['usuario'] = email
        return redirect(url_for('painel'))
    return render_template_string(HTML_AUTH, erro="Credenciais inválidas.")

@app.route('/registrar', methods=['POST'])
def registrar():
    email = request.form.get('email', '').strip().lower()
    senha = request.form.get('senha', '').strip()
    cpf = re.sub(r'\D', '', request.form.get('cpf', ''))
    if len(cpf) != 11:
        return render_template_string(HTML_AUTH, erro="CPF deve ter 11 dígitos.")
    conn = sqlite3.connect('datacleaner.db')
    try:
        conn.cursor().execute('INSERT INTO usuarios (email, senha, cpf, teste_usado, is_vip) VALUES (?, ?, ?, 0, 0)', (email, senha, cpf))
        conn.commit()
        session['usuario'] = email
        return redirect(url_for('painel'))
    except:
        return render_template_string(HTML_AUTH, erro="E-mail ou CPF já registados.")
    finally:
        conn.close()

@app.route('/recuperar', methods=['POST'])
def recuperar():
    email = request.form.get('email', '').strip().lower()
    cpf = re.sub(r'\D', '', request.form.get('cpf', ''))
    nova_senha = request.form.get('nova_senha', '').strip()
    
    conn = sqlite3.connect('datacleaner.db')
    c = conn.cursor()
    user = c.execute('SELECT email FROM usuarios WHERE email = ? AND cpf = ?', (email, cpf)).fetchone()
    if user:
        c.execute('UPDATE usuarios SET senha = ? WHERE email = ?', (nova_senha, email))
        conn.commit()
        conn.close()
        return render_template_string(HTML_AUTH, sucesso="Palavra-passe redefinida com sucesso! Pode entrar.")
    conn.close()
    return render_template_string(HTML_AUTH, erro="E-mail ou CPF não conferem.")

@app.route('/painel')
def painel():
    if 'usuario' not in session: return redirect(url_for('index'))
    return render_template_string(HTML_PAINEL, email=session['usuario'])

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = sqlite3.connect('datacleaner.db')
    c = conn.cursor()
    tu = c.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    tc = c.execute("SELECT COUNT(*) FROM usage_logs").fetchone()[0]
    tv = c.execute("SELECT COUNT(*) FROM usuarios WHERE is_vip = 1").fetchone()[0]
    conn.close()
    return render_template_string(HTML_ADMIN, total_users=tu, total_cleanings=tc, total_vip=tv)

@app.route('/cotar', methods=['POST'])
def cotar():
    if 'usuario' not in session: return redirect(url_for('index'))
    file = request.files.get('file')
    if not file: return "Nenhum arquivo", 400
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)
    df = pd.read_csv(path) if file.filename.endswith('.csv') else pd.read_excel(path)
    total = len(df)
    user = session.get('usuario')
    
    try:
        cl_conn = sqlite3.connect('datacleaner.db')
        cl_conn.cursor().execute("INSERT INTO usage_logs (email) VALUES (?)", (user,))
        cl_conn.commit()
        cl_conn.close()
    except: pass

    conn = sqlite3.connect('datacleaner.db')
    c = conn.cursor()
    res = c.execute('SELECT teste_usado, is_vip FROM usuarios WHERE email = ?', (user,)).fetchone()
    vip = res[1] == 1 if res else False
    usado = res[0] == 1 if res else False

    if user == ADMIN_EMAIL or vip:
        val = 0.00
    elif not usado:
        val = 0.00
        c.execute('UPDATE usuarios SET teste_usado = 1 WHERE email = ?', (user,))
        conn.commit()
    else:
        val = max(10.00, float(total * 0.20))
    conn.close()

    session['filename_pendente'] = file.filename
    session['total_linhas'] = total
    session['valor_total'] = f"{val:.2f}"

    if val == 0.00:
        session['pago'] = True
        return redirect(url_for('tela_download'))

    pid = "manual_pix"
    qr = None
    try:
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN_MP}", "Content-Type": "application/json", "X-Idempotency-Key": str(uuid.uuid4())}
        p_data = {"transaction_amount": float(val), "description": f"Higienização de {total} leads", "payment_method_id": "pix", "payer": {"email": user}}
        resp = requests.post("https://api.mercadopago.com/v1/payments", json=p_data, headers=headers, timeout=10)
        if resp.status_code == 201:
            pj = resp.json()
            pid = pj.get("id")
            qr = pj.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code")
    except: pass

    if not qr:
        qr = gerar_payload_pix(MINHA_CHAVE_PIX, "DataCleaner", "Sao Paulo", val)

    session['payment_id'] = pid
    session['qr_code'] = qr
    session['pago'] = False
    return redirect(url_for('tela_pagamento'))

@app.route('/pagamento')
def tela_pagamento():
    if 'usuario' not in session or 'filename_pendente' not in session: return redirect(url_for('painel'))
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
    except: pass
    return jsonify({"pago": session.get('pago', False)})

@app.route('/download_liberado')
def tela_download():
    if not session.get('pago') or 'filename_pendente' not in session: return redirect(url_for('painel'))
    return render_template_string(HTML_DOWNLOAD)

@app.route('/processar_e_baixar', methods=['POST'])
def processar_e_baixar():
    if not session.get('pago') or 'filename_pendente' not in session: return "Acesso negado.", 403
    fn = session['filename_pendente']
    inp = os.path.join(UPLOAD_FOLDER, fn)
    if not os.path.exists(inp): return "Arquivo expirado", 404
    df = pd.read_csv(inp) if fn.endswith('.csv') else pd.read_excel(inp)
    for col in df.columns:
        cl = col.lower()
        if 'nome' in cl: df[col] = df[col].apply(limpar_nome)
        elif 'email' in cl: df[col] = df[col].apply(limpar_email)
        elif 'tel' in cl or 'cel' in cl or 'fone' in cl or 'whatsapp' in cl: df[col] = df[col].apply(limpar_telefone)
    df = df.drop_duplicates()
    cn = next((c for c in df.columns if 'nome' in c.lower()), None)
    if cn: df = df.sort_values(by=cn, ascending=True)
    out_name = "limpo_" + fn
    out_path = os.path.join(UPLOAD_FOLDER, out_name)
    if out_name.endswith('.csv'): df.to_csv(out_path, index=False, encoding='utf-8-sig')
    else: df.to_excel(out_path, index=False)
    resp = send_file(out_path, as_attachment=True)
    @resp.call_on_close
    def clean():
        try:
            if os.path.exists(inp): os.remove(inp)
            if os.path.exists(out_path): os.remove(out_path)
            session.pop('pago', None)
            session.pop('filename_pendente', None)
        except: pass
    return resp

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)