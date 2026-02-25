from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import json, os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from cryptography.fernet import Fernet

app = Flask(__name__)
app.secret_key = 'chave_seguranca_codetecx_2026'

# ==========================================
# CONFIGURAÇÕES DE SEGURANÇA (AES-256)
# ==========================================
CHAVE_MESTRA = b'U2ZLBCXpcy_pEcsjdgCSxoZbYrbneHPDsSA47mso0xw='
cipher_suite = Fernet(CHAVE_MESTRA)

DB_FILE = 'denuncias_database.json'
CONFIG_FILE = 'admin_config.json'

def carregar_credenciais():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"user": "admin", "pass": "123456"}

MEU_EMAIL_ENVIO = "canaldenuncia@codetecx.com"
MINHA_SENHA_APP = "eflwietplcuoazsd" 

# ==========================================
# MOTOR DE NOTIFICAÇÃO
# ==========================================
def enviar_email_notificacao(email_criptografado, protocolo, parecer):
    try:
        if not email_criptografado or "ANONIMO" in email_criptografado:
            return False

        email_real = cipher_suite.decrypt(email_criptografado.encode()).decode()
        
        msg = MIMEMultipart()
        msg['From'] = f"Comitê de Ética EL SHADDAY <{MEU_EMAIL_ENVIO}>"
        msg['To'] = email_real
        msg['Subject'] = f"CONCLUSÃO DE CHAMADO: Protocolo #{protocolo}"

        corpo_html = f"""
        <html>
            <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #1e293b; line-height: 1.6;">
                <div style="max-width: 600px; margin: auto; border: 1px solid #e2e8f0; padding: 30px; border-radius: 15px;">
                    <h2 style="color: #2563eb;">Atualização Final de Relato</h2>
                    <p>Informamos que a análise do seu relato sob o protocolo <strong>{protocolo}</strong> foi concluída.</p>
                    <div style="background-color: #f1f5f9; padding: 20px; border-left: 6px solid #2563eb;">
                        <p><strong>Parecer:</strong> "{parecer}"</p>
                    </div>
                </div>
            </body>
        </html>
        """
        msg.attach(MIMEText(corpo_html, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(MEU_EMAIL_ENVIO, MINHA_SENHA_APP)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Erro e-mail: {e}")
        return False

# ==========================================
# ROTAS DE ACESSO
# ==========================================

@app.route('/')
def index():
    if session.get('admin_logado'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    credenciais = carregar_credenciais()
    if request.method == 'POST':
        usuario = request.form.get('user')
        senha = request.form.get('pass')
        if usuario == credenciais['user'] and senha == credenciais['pass']:
            session['admin_logado'] = True
            return redirect(url_for('dashboard'))
        return render_template('login.html', erro="Credenciais Inválidas")
    return render_template('login.html')

@app.route('/alterar_acesso', methods=['POST'])
def alterar_acesso():
    if not session.get('admin_logado'):
        return redirect(url_for('login'))
    novo_user = request.form.get('novo_user')
    nova_senha = request.form.get('nova_senha')
    if novo_user and nova_senha:
        with open(CONFIG_FILE, 'w', encoding="utf-8") as f:
            json.dump({"user": novo_user, "pass": nova_senha}, f)
        session.pop('admin_logado', None)
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if not session.get('admin_logado'):
        return redirect(url_for('login'))
    denuncias = []
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: denuncias = json.load(f)
            except: denuncias = []
    return render_template('dashboard.html', denuncias=denuncias[::-1])

@app.route('/logout')
def logout():
    session.pop('admin_logado', None)
    return redirect(url_for('login'))

# ==========================================
# PROCESSAMENTO E IMPRESSÃO (AJUSTADO)
# ==========================================

@app.route('/atualizar_denuncia', methods=['POST'])
def atualizar():
    """ Rota original do Dashboard """
    if not session.get('admin_logado'): 
        return jsonify({"status": "erro", "msg": "Sessão expirada"}), 401
    
    prot = request.form.get('protocolo')
    novo_status = request.form.get('status')
    novo_parecer = request.form.get('parecer')
    
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            banco = json.load(f)
        
        email_cripto = None
        for d in banco:
            if d['protocolo'] == prot:
                d['status'] = novo_status
                d['parecer_comite'] = novo_parecer
                email_cripto = d.get('email_contato')
                break
        
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(banco, f, indent=2, ensure_ascii=False)
            
        if novo_status == "Finalizada" and email_cripto:
            enviar_email_notificacao(email_cripto, prot, novo_parecer)
            
    return redirect(url_for('dashboard'))

@app.route('/gestao/<prot>', methods=['GET', 'POST'])
def gestao_dossie(prot):
    """ Rota nova para o Dossiê de Impressão """
    if not session.get('admin_logado'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Se clicar em "Salvar Alterações" no Dossiê
        novo_status = request.form.get('status')
        novo_parecer = request.form.get('parecer')
        
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                banco = json.load(f)
            
            email_cripto = None
            for d in banco:
                if d['protocolo'] == prot:
                    d['status'] = novo_status
                    # Importante: No dossiê salvamos no campo 'parecer' para bater com o HTML
                    d['parecer'] = novo_parecer 
                    # Também atualizamos o parecer_comite para manter o dashboard em dia
                    d['parecer_comite'] = novo_parecer
                    email_cripto = d.get('email_contato')
                    break
            
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(banco, f, indent=2, ensure_ascii=False)
            
            if novo_status == "Finalizado" and email_cripto:
                enviar_email_notificacao(email_cripto, prot, novo_parecer)
                
        return redirect(url_for('dashboard'))

    # Se for apenas carregar a página (GET)
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            banco = json.load(f)
            denuncia = next((d for d in banco if d['protocolo'] == prot), None)
            if denuncia:
                return render_template('impressao.html', d=denuncia)
    
    return "Relato não encontrado", 404

if __name__ == '__main__':
    
    app.run(debug=True, host='0.0.0.0', port=8081)