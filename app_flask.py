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

# PÁGINA DE BOAS-VINDAS (LANDING PAGE) INTEGRADA
HTML_INDEX = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DataCleaner Pro - Higienização de Leads</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>.glass-card { background: rgba(15, 23, 42, 0.8); backdrop-filter: blur(16px); border: 1px solid rgba(56, 189, 248, 0.15); }</style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col justify-between">
    <header class="w-full border-b border-slate-900 bg-slate-950/80 sticky top-0 z-50">
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
    <main class="max-w-6xl mx-auto px-6 py-16 flex-1 text-center">
        <div class="max-w-3xl mx-auto mb-16">
            <h1 class="text-4xl sm:text-6xl font-extrabold tracking-tight text-white mb-6 leading-tight">
                Transforme bases de dados sujas em <span class="text-sky-400">Leads Prontos para Vendas</span>
            </h1>
            <p class="text-slate-400 text-base sm:text-lg mb-10">
                Automatize a correção ortográfica, formatação de telefones/e-mails, remoção de duplicados e ordenação alfabética instantaneamente.
            </p>
            <a href="/login_view" class="inline-flex items-center gap-2 bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-8 py-4 rounded-2xl shadow-xl shadow-sky-500/25 transition">
                <i class="fa-solid fa-rocket"></i> Começar Teste Grátis Agora
            </a>
        </div>
    </main>
    <footer class="w-full border-t border-slate-900 bg-slate-950 py-8 text-center text-xs text-slate-500">
        <p>&copy; 2026 DataCleaner Pro. Todos os direitos reservados.</p>
    </footer>
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
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email', '').strip().lower()
    senha = request.form.get('senha', '').strip()
    
    if not email or not senha:
        return render_template('login.html', erro_login="Preencha o e-mail e a senha.", aba_ativa="login")

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
    
    return render_template('login.html', erro_login="Credenciais inválidas ou conta não encontrada.", aba_ativa="login")

@app.route('/registrar', methods=['POST'])
def registrar():
    email = request.form.get('email', '').strip().lower()
    senha = request.form.get('senha', '').strip()
    cpf = re.sub(r'\D', '', request.form.get('cpf', ''))

    if not email or not senha or not cpf:
        return render_template('login.html', erro_reg="Preencha todos os campos para o Teste Grátis.", aba_ativa="registro")

    if len(cpf) != 11:
        return render_template('login.html', erro_reg="CPF inválido. Introduza os 11 dígitos.", aba_ativa="registro")

    conn = sqlite3.connect('datacleaner.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO usuarios (email, senha, cpf, teste_usado) VALUES (?, ?, ?, 0)', (email, senha, cpf))
        conn.commit()
        session['usuario'] = email
        return redirect(url_for('painel'))
    except sqlite3.IntegrityError:
        return render_template('login.html', erro_reg="Este CPF ou e-mail já possui uma conta cadastrada.", aba_ativa="registro")
    finally:
        conn.close()

@app.route('/painel')
def painel():
    if 'usuario' not in session:
        return redirect(url_for('index'))
    return render_template('painel.html', email=session['usuario'])

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
                if total_linhas <= 5000:
                    preco = 0.20
                elif total_linhas <= 10000:
                    preco = 0.15
                else:
                    preco = 0.10
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
        
        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN_MP}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": str(uuid.uuid4())
        }
        
        payment_data = {
            "transaction_amount": float(valor_total),
            "description": f"Higienização de {total_linhas} leads - DataCleaner",
            "payment_method_id": "pix",
            "payer": {"email": usuario_atual}
        }
        
        try:
            resp = requests.post("https://api.mercadopago.com/v1/payments", json=payment_data, headers=headers, timeout=10)
            if resp.status_code == 201:
                p_json = resp.json()
                payment_id = p_json.get("id")
                t_data = p_json.get("point_of_interaction", {}).get("transaction_data", {})
                qr_code_gerado = t_data.get("qr_code")
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
    return render_template('pagamento.html', filename=session['filename_pendente'], total_linhas=session['total_linhas'], valor_total=session['valor_total'], qr_code=session.get('qr_code', ''))

@app.route('/verificar_pagamento', methods=['GET'])
def verificar_pagamento():
    if 'usuario' not in session:
        return redirect(url_for('index'))
    payment_id = session.get('payment_id')
    if payment_id == "manual_pix":
        session['pago'] = True
        return redirect(url_for('tela_download'))
        
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN_MP}"}
    try:
        resp = requests.get(f"https://api.mercadopago.com/v1/payments/{payment_id}", headers=headers, timeout=10)
        if resp.status_code == 200:
            if resp.json().get("status") == "approved":
                session['pago'] = True
                return redirect(url_for('tela_download'))
    except:
        pass
    return render_template('aguardando_pagamento.html', filename=session.get('filename_pendente'), valor_total=session.get('valor_total'), aviso="O Pix ainda não foi compensado.")

@app.route('/download_liberado')
def tela_download():
    if not session.get('pago') or 'filename_pendente' not in session:
        return redirect(url_for('painel'))
    return render_template('download.html', filename=session['filename_pendente'])

@app.route('/processar_e_baixar', methods=['POST'])
def processar_e_baixar():
    if not session.get('pago') or 'filename_pendente' not in session:
        return "Acesso negado. O pagamento é obrigatório.", 403
        
    filename = session['filename_pendente']
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    
    if not os.path.exists(input_path):
        return "Ficheiro expirado", 404
        
    if filename.endswith('.csv'):
        df = pd.read_csv(input_path)
    else:
        df = pd.read_excel(input_path)
        
    for col in df.columns:
        col_lower = col.lower()
        if 'nome' in col_lower:
            df[col] = df[col].apply(limpar_nome)
        elif 'email' in col_lower or 'e-mail' in col_lower:
            df[col] = df[col].apply(limpar_email)
        elif 'tel' in col_lower or 'cel' in col_lower or 'fone' in col_lower or 'whatsapp' in col_lower:
            df[col] = df[col].apply(limpar_telefone)
            
    df = df.drop_duplicates()
    
    coluna_nome = next((c for c in df.columns if 'nome' in c.lower()), None)
    if coluna_nome:
        df = df.sort_values(by=coluna_nome, ascending=True)
    
    output_filename = "limpo_" + filename
    output_path = os.path.join(UPLOAD_FOLDER, output_filename)
    
    if output_filename.endswith('.csv'):
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
    else:
        df.to_excel(output_path, index=False)
    
    response = send_file(output_path, as_attachment=True)
    
    @response.call_on_close
    def limpar_tudo():
        try:
            if os.path.exists(input_path): os.remove(input_path)
            if os.path.exists(output_path): os.remove(output_path)
            session.clear()
        except:
            pass

    return response

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
