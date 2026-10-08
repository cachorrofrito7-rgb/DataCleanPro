from flask import Flask, render_template, request, send_file, redirect, url_for, session
import pandas as pd
import re
import os
import requests
import uuid

app = Flask(__name__)
app.secret_key = "datacleaner_segredo_oficial_definitivo"

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# SEU TOKEN REAL DO MERCADO PAGO
ACCESS_TOKEN_MP = "APP_USR-7867386358048993-100810-4465684464772bfe6f520899f45e0b59-725141812"

# SUA CHAVE PIX OFICIAL (Fallback e recebimento direto)
MINHA_CHAVE_PIX = "e32c6a95-8ef0-471f-ae7a-4072a635be4e"

def limpar_telefone(tel):
    if pd.isna(tel):
        return ""
    numeros = re.sub(r'\D', '', str(tel))
    if numeros.startswith('55') and len(numeros) in [12, 13]:
        numeros = numeros[2:]
    if len(numeros) == 11:
        return f"({numeros[:2]}) {numeros[2:7]}-{numeros[7:]}"
    elif len(numeros) == 10:
        return f"({numeros[:2]}) {numeros[2:6]}-{numeros[6:]}"
    return numeros

def gerar_payload_pix(chave, nome, cidade, valor):
    """Gera o BR Code (Pix Copia e Cola) estático/dinâmico válido exigido pelos bancos."""
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

@app.route('/')
def index():
    if 'usuario' in session:
        return redirect(url_for('painel'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    senha = request.form.get('senha')
    if email and senha:
        session['usuario'] = email
        return redirect(url_for('painel'))
    return render_template('login.html', erro="Preencha os campos.")

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
        
        # Valor de teste para o Administrador ou tabela progressiva padrão
        if session.get('usuario') == "admin@datacleaner.com":
            valor_total = 0.32
        else:
            if total_linhas <= 5000:
                preco = 0.20
            elif total_linhas <= 10000:
                preco = 0.15
            else:
                preco = 0.10
            valor_total = max(10.00, float(total_linhas * preco))
        
        session['filename_pendente'] = file.filename
        session['total_linhas'] = total_linhas
        session['valor_total'] = f"{valor_total:.2f}"
        
        payment_id = "manual_pix"
        qr_code_gerado = None
        
        # Tenta criar via API do Mercado Pago
        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN_MP}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": str(uuid.uuid4())
        }
        
        payment_data = {
            "transaction_amount": float(valor_total),
            "description": f"Higienização de {total_linhas} leads - DataCleaner",
            "payment_method_id": "pix",
            "payer": {"email": session['usuario']}
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
            
        # Fallback seguro com BR Code nativo caso a API externa tenha restrições de conta nova
        if not qr_code_gerado:
            qr_code_gerado = gerar_payload_pix(MINHA_CHAVE_PIX, "DataCleaner", "Sao Paulo", valor_total)
            
        session['payment_id'] = payment_id
        session['qr_code'] = qr_code_gerado
        
        return redirect(url_for('tela_pagamento'))

@app.route('/pagamento')
def tela_pagamento():
    if 'usuario' not in session or 'filename_pendente' not in session:
        return redirect(url_for('painel'))
        
    return render_template('pagamento.html', 
                           filename=session['filename_pendente'],
                           total_linhas=session['total_linhas'],
                           valor_total=session['valor_total'],
                           qr_code=session.get('qr_code', ''))

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
        
    return render_template('aguardando_pagamento.html', 
                           filename=session.get('filename_pendente'),
                           valor_total=session.get('valor_total'),
                           aviso="O Pix ainda não foi compensado.")

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
        
    for col in df.select_dtypes(include=['object', 'str']).columns:
        df[col] = df[col].astype(str).str.strip()
        
    if 'email' in df.columns:
        df['email'] = df['email'].str.lower()
    if 'nome' in df.columns:
        df['nome'] = df['nome'].str.title()
    if 'telefone' in df.columns:
        df['telefone'] = df['telefone'].apply(limpar_telefone)
        
    df = df.drop_duplicates()
    
    output_filename = "limpo_" + filename
    output_path = os.path.join(UPLOAD_FOLDER, output_filename)
    df.to_csv(output_path, index=False)
    
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
