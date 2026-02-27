# ==========================================
# [BLOCO 01]: CONFIGURAÇÕES, SEGURANÇA E LICENÇA
# ==========================================
from flask import Flask, render_template, request, jsonify, send_from_directory, make_response, session, redirect, url_for
import smtplib, json, os, hashlib, shutil
import base64 
import threading
from threading import Thread
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone 
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet
import resend 

# Fuso horário de Brasília
FUSO_BR = timezone(timedelta(hours=-3))

# CRIAÇÃO DO APP
app = Flask(__name__)
app.secret_key = 'chave_seguranca_codetecx_2026' 

# --- VARIÁVEIS GLOBAIS ---
CHAVE_MESTRA = b'U2ZLBCXpcy_pEcsjdgCSxoZbYrbneHPDsSA47mso0xw='
cipher_suite = Fernet(CHAVE_MESTRA)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# --- CONFIGURAÇÃO DO RESEND (API) ---
resend.api_key = os.environ.get("RESEND_API_KEY")

# --- AJUSTE DE AMBIENTE (RENDER / GITHUB) ---
caminho_base = os.getcwd()
UPLOAD_FOLDER = os.path.join(caminho_base, 'uploads')
DATA_FOLDER = os.path.join(caminho_base, 'data')
DB_FILE = os.path.join(caminho_base, 'denuncias_database.json')
ADMIN_CONFIG_FILE = os.path.join(caminho_base, 'admin_config.json')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

# --- CONFIGURAÇÕES DE ENVIO ---
MEU_EMAIL_ENVIO = "suporte@codetecx.com"
MINHA_SENHA_APP = "szqbymzenmtqfjvj" 

# Destinatário oficial para alertas de sistema e licença
EMAIL_ADMIN_SUPORTE = "camilameireles@se-pmmc.com.br"
LISTA_ADMINS = [EMAIL_ADMIN_SUPORTE]

# --- GARANTE QUE O ARQUIVO DE SENHA EXISTA ---
def inicializar_admin_config():
    """ Cria o arquivo de senha inicial se não existir """
    if not os.path.exists(ADMIN_CONFIG_FILE):
        config_inicial = {"user": "admin", "pass": "2821"}
        try:
            with open(ADMIN_CONFIG_FILE, 'w', encoding="utf-8") as f:
                json.dump(config_inicial, f, ensure_ascii=False, indent=4)
            print("✅ Configuração inicial Codetecx criada.")
        except Exception as e:
            print(f"❌ Erro ao criar config: {e}")

inicializar_admin_config()

# --- TRAVA DE LICENCIAMENTO (BLOQUEIO POR FALTA DE PAGAMENTO) ---
DATA_EXPIRACAO = "2026-12-24" 

def verificar_licenca():
    """ Verifica validade do sistema para exibição da tela de bloqueio """
    try:
        data_limite = datetime.strptime(DATA_EXPIRACAO, '%Y-%m-%d')
        return datetime.now() <= data_limite
    except:
        return False

def alertar_admin_bloqueio():
    """ Envia alerta de expiração para Camila Meireles """
    try:
        resend.Emails.send({
            "from": "Segurança Sistema <suporte@codetecx.com>",
            "to": EMAIL_ADMIN_SUPORTE,
            "subject": "⚠️ ALERTA CRÍTICO: Licença Expirada",
            "html": f"""
                <h3>Bloqueio de Sistema</h3>
                <p>A licença de uso do Canal de Integridade (El Shadday/Codetecx) expirou em <b>{DATA_EXPIRACAO}</b>.</p>
                <p>O acesso ao painel e novos relatos foram suspensos automaticamente.</p>
            """
        })
    except: pass

# --- TELA DE BLOQUEIO PROFISSIONAL ---
HTML_BLOQUEIO = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script>
    <title>Validação de Sistema</title>
</head>
<body class="bg-slate-50 flex items-center justify-center min-h-screen p-6">
    <div class="max-w-md w-full text-center space-y-6">
        <div class="flex justify-center">
            <div class="bg-red-100 p-5 rounded-full animate-pulse">
                <svg class="w-10 h-10 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
            </div>
        </div>
        <h1 class="text-2xl font-black text-slate-800 uppercase italic">Codetecx - Bloqueio</h1>
        <p class="text-slate-500 text-sm leading-relaxed">
            Este módulo está suspenso devido à expiração da licença de uso ou pendência de sincronização.
        </p>
        <div class="bg-white p-6 rounded-[2rem] shadow-xl border border-slate-100">
            <span class="inline-flex items-center px-4 py-1 rounded-full text-xs font-bold bg-red-100 text-red-700">
                Sistema Suspenso
            </span>
        </div>
        <p class="text-[9px] text-slate-400 uppercase font-black tracking-tighter">
            Contate o suporte técnico para regularizar o acesso.
        </p>
    </div>
</body>
</html>
"""

# --- SEGURANÇA DE ARQUIVOS ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"status": "erro", "msg": "Arquivo muito grande! Limite: 16MB."}), 413

# ==========================================
# [BLOCO 02]: SEGURANÇA E CRIPTOGRAFIA (REVERSÍVEL)
# ==========================================
def criptografar_dado(texto):
    """ Criptografia Reversível (AES-256) """
    try:
        if not texto: return "ANONIMO"
        if isinstance(texto, bytes): texto = texto.decode('utf-8', errors='ignore')
        texto = str(texto).strip()
        if texto.upper() == "ANONIMO": return "ANONIMO"
        if "@" not in texto: return "ANONIMO"
        texto_preparado = texto.lower().encode('utf-8')
        return cipher_suite.encrypt(texto_preparado).decode('utf-8')
    except Exception as e:
        print("❌ ERRO criptografar_dado:", e)
        return "ANONIMO"

def gerar_id_criptografico(dado_criptografado):
    """ Gera um ID visual curto baseado no e-mail criptografado """
    try:
        if not dado_criptografado: return "IDENTIDADE PRESERVADA"
        if isinstance(dado_criptografado, bytes): dado_criptografado = dado_criptografado.decode('utf-8', errors='ignore')
        dado_criptografado = str(dado_criptografado)
        if "ANONIMO" in dado_criptografado.upper() or len(dado_criptografado) < 22: return "IDENTIDADE PRESERVADA"
        fragmento = dado_criptografado[10:22].upper().replace('-', 'X').replace('_', 'Y')
        return f"ID_SEGURANCA_{fragmento}"
    except Exception as e:
        print("❌ ERRO gerar_id_criptografico:", e)
        return "IDENTIDADE PRESERVADA"

def gerar_protocolo_sequencial():
    """ Gera protocolo baseado na data: AAAAMMDD-0001 """
    data_hoje = datetime.now().strftime('%Y%m%d')
    contador = 1
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try:
                banco = json.load(f)
                hoje_count = [d for d in banco if str(d.get('protocolo', '')).startswith(data_hoje)]
                contador = len(hoje_count) + 1
            except Exception as e:
                print("Erro ao ler banco de dados:", e)
                contador = 1
    return f"{data_hoje}-{str(contador).zfill(4)}"

# ==========================================
# [BLOCO 03]: ROTAS DE NAVEGAÇÃO E COOKIES
# ==========================================
@app.route('/')
def home():
    if not verificar_licenca():
        alertar_admin_bloqueio() 
        return HTML_BLOQUEIO, 403
    ultimo_visto = request.cookies.get('ultimo_protocolo', 'Nenhum')
    return render_template('denuncia.html', ultimo=ultimo_visto)

@app.route('/baixar/<setor>/<nome>')
def baixar(setor, nome):
    caminho_setor = os.path.join(UPLOAD_FOLDER, secure_filename(setor))
    return send_from_directory(caminho_setor, nome)

@app.route('/consultar/<prot>')
def consultar(prot):
    if not verificar_licenca(): return "Serviço Indisponível", 403
    status_encontrado = None
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            banco = json.load(f)
            for d in banco:
                if d['protocolo'] == prot:
                    status_encontrado = d['status']
                    break
    if status_encontrado:
        resp = make_response(jsonify({"status": status_encontrado}))
        resp.set_cookie('ultimo_protocolo', prot, max_age=60*60*24*7) 
        return resp
    return jsonify({"status": "Nao encontrado"}), 404


# ==========================================
# [BLOCO 04]: MOTOR DE ENVIO (EXCLUSIVO DENUNCIANTE)
# ==========================================

def disparar_email_seguro(destinatario, assunto, corpo_html):
    """ Tenta Resend primeiro; se falhar, usa SMTP como Fallback """
    # 1. TENTATIVA VIA RESEND (API)
    try:
        resend.Emails.send({
            "from": "Canal de Integridade <suporte@codetecx.com>",
            "to": destinatario,
            "subject": assunto,
            "html": corpo_html
        })
        print(f"✅ Sucesso via Resend: {destinatario}")
        return True
    except Exception as e_resend:
        print(f"⚠️ Resend falhou (Provável Sandbox/DNS). Tentando SMTP... Erro: {e_resend}")
        
        # 2. TENTATIVA VIA SMTP (GOOGLE WORKSPACE) - O SEU PLANO B SEGURO
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(MEU_EMAIL_ENVIO, MINHA_SENHA_APP)
            
            msg = MIMEMultipart()
            msg['From'] = f"Canal de Integridade <{MEU_EMAIL_ENVIO}>"
            msg['To'] = destinatario
            msg['Subject'] = assunto
            msg.attach(MIMEText(corpo_html, 'html'))
            
            server.sendmail(MEU_EMAIL_ENVIO, destinatario, msg.as_string())
            server.quit()
            print(f"✅ Sucesso via SMTP (Google): {destinatario}")
            return True
        except Exception as e_smtp:
            print(f"❌ AMBOS OS MÉTODOS FALHARAM para {destinatario}: {e_smtp}")
            return False

def enviar_emails_async(unidade, data_hora, protocolo, email_bruto):
    """ Gerencia os disparos APENAS para o Denunciante (Cidadão) """
    
    print(f"📧 Processando protocolo: {protocolo}")

    # --- DISPARO EXCLUSIVO PARA O CIDADÃO ---
    # Só dispara se o e-mail não for nulo e for um formato válido
    if email_bruto and "@" in str(email_bruto):
        destinatario_cidadao = str(email_bruto).strip()
        
        corpo_cid = f"""
            <div style="font-family: sans-serif; padding: 20px; color: #333; border: 1px solid #eee; border-radius: 8px;">
                <h3 style="color: #2c3e50;">Confirmação de Registro</h3>
                <p>Olá,</p>
                <p>Seu relato foi registrado com sucesso em nosso <strong>Canal de Integridade</strong>.</p>
                <div style="background-color: #f8fafc; padding: 15px; border-radius: 5px; border-left: 4px solid #2c3e50; margin: 20px 0;">
                    <strong>PROTOCOLO PARA CONSULTA:</strong> {protocolo}<br>
                    <strong>DATA:</strong> {data_hora}<br>
                    <strong>UNIDADE:</strong> {unidade}
                </div>
                <p>Guarde este número para acompanhar o andamento do seu relato através do sistema.</p>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #888;">Atenciosamente,<br><strong>Comitê de Ética e Integridade</strong></p>
            </div>
        """
        
        # Dispara para o cidadão usando o motor híbrido
        disparar_email_seguro(destinatario_cidadao, f"Confirmação de Registro - Protocolo #{protocolo}", corpo_cid)
    else:
        print(f"ℹ️ Protocolo {protocolo}: Relato anônimo ou e-mail ausente. Nenhum disparo realizado.")

# No seu app.route('/enviar'), o chamado permanece:
# threading.Thread(target=enviar_emails_async, args=(unidade, data_hora, protocolo, email_bruto), daemon=True).start()

# ==========================================
# [BLOCO 05]: GESTÃO, DASHBOARD E PARECER
# ==========================================

def carregar_credenciais():
    """ Carrega as credenciais de acesso ao painel administrativo """
    if os.path.exists(ADMIN_CONFIG_FILE):
        try:
            with open(ADMIN_CONFIG_FILE, 'r', encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"user": "admin", "pass": "2821"}

def enviar_email_conclusao(email_criptografado, protocolo, parecer):
    """ Envia o parecer final exclusivamente para o denunciante """
    try:
        # Se for anônimo, não há o que enviar
        if not email_criptografado or "ANONIMO" in email_criptografado: 
            print(f"ℹ️ Protocolo {protocolo}: Conclusão sem e-mail (Anônimo).")
            return False
        
        # Descriptografa o e-mail real do cidadão
        email_real = cipher_suite.decrypt(email_criptografado.encode()).decode().strip()
        
        assunto = f"CONCLUSÃO DE RELATO: Protocolo #{protocolo}"
        corpo_html = f"""
            <div style="font-family: sans-serif; padding: 20px; border: 1px solid #eee; border-radius: 8px; color: #333;">
                <h3 style="color: #2c3e50;">Atualização de Protocolo - Canal de Integridade</h3>
                <p>Prezado(a),</p>
                <p>Informamos que o seu relato registrado sob o protocolo <strong>#{protocolo}</strong> foi concluído e finalizado pelo Comitê de Ética.</p>
                
                <div style="background-color: #f8fafc; padding: 15px; border-left: 4px solid #1e293b; margin: 20px 0;">
                    <strong style="color: #1e293b;">PARECER FINAL:</strong><br>
                    <p style="white-space: pre-wrap;">{parecer}</p>
                </div>
                
                <p style="font-size: 12px; color: #64748b;">Este é um envio automático. Não é necessário responder.</p>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                <p>Atenciosamente,<br><strong>Comitê de Ética e Integridade</strong></p>
            </div>
        """
        
        # Dispara usando o motor seguro (Resend com Fallback SMTP)
        return disparar_email_seguro(email_real, assunto, corpo_html)
        
    except Exception as e:
        print(f"❌ Erro ao processar envio de conclusão: {e}")
        return False

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logado'): return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = request.form.get('user')
        pw = request.form.get('pass')
        cred = carregar_credenciais()
        if user == cred['user'] and pw == cred['pass']:
            session['admin_logado'] = True
            return redirect(url_for('dashboard'))
        return render_template('login.html', erro="Credenciais Inválidas")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logado', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    """ Painel principal: admins acompanham tudo por aqui, sem receber e-mails """
    if not session.get('admin_logado'): return redirect(url_for('login'))
    denuncias_total = []
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: 
                denuncias_total = json.load(f)
            except: 
                denuncias_total = []
    return render_template('dashboard.html', denuncias=denuncias_total[::-1])

@app.route('/atualizar_denuncia', methods=['POST'])
def atualizar():
    """ Atualiza status e parecer. Se finalizado, dispara e-mail para o cidadão """
    if not session.get('admin_logado'): return redirect(url_for('login'))
    prot = request.form.get('protocolo')
    novo_status = request.form.get('status')
    novo_parecer = request.form.get('parecer')
    
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            banco = json.load(f)
        
        email_alvo = None
        for d in banco:
            if d['protocolo'] == prot:
                d['status'] = novo_status
                d['parecer_comite'] = novo_parecer
                email_alvo = d.get('email_contato')
                break
        
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(banco, f, indent=2, ensure_ascii=False)
        
        # DISPARO PARA O CIDADÃO: Apenas se finalizada e não for anônimo
        if novo_status == "Finalizada" and email_alvo and email_alvo != "ANONIMO":
            threading.Thread(target=enviar_email_conclusao, args=(email_alvo, prot, novo_parecer), daemon=True).start()
            
    return redirect(url_for('dashboard'))

@app.route('/alterar_acesso', methods=['POST'])
def alterar_senha():
    if not session.get('admin_logado'): return redirect(url_for('login'))
    nova_senha = request.form.get('nova_senha')
    if nova_senha:
        try:
            with open(ADMIN_CONFIG_FILE, 'w', encoding="utf-8") as f:
                json.dump({"user": "admin", "pass": str(nova_senha)}, f, indent=4)
            return redirect(url_for('dashboard'))
        except: 
            return "Erro ao salvar novas credenciais", 500
    return "Erro: Senha não pode ser vazia", 400

# ==========================================
# [BLOCO 06]: DOSSIÊ DE IMPRESSÃO (ESTILO FOLHA A4)
# ==========================================
@app.route('/gestao/<prot>')
def area_segura(prot):
    if not session.get('admin_logado'): return redirect(url_for('login'))
    d = None
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try:
                banco = json.load(f)
                d = next((item for item in banco if item['protocolo'] == prot), None)
            except: pass
    if not d: return f"Protocolo {prot} não encontrado.", 404

    # GERA ID SIGILOSO BASEADO NA FUNÇÃO DO BLOCO 02
    id_seguro = gerar_id_criptografico(d.get('email_contato'))
    token_auth = hashlib.md5(f"{prot}{d['data']}".encode()).hexdigest().upper()[:20]
    
    midia_html = ""
    if d.get('anexo') and d['anexo'] != "Nenhum":
        midia_html = f"""<div class="container-midia"><div class="secao-titulo">Anexo Enviado</div><div class="caixa-imagem"><img src="{d['anexo']}" class="img-anexo"></div></div>"""

    # HTML COMPLETO DE IMPRESSÃO (TODAS AS REGRAS CSS PRESERVADAS)
    conteudo_html = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{ size: A4; margin: 0; }}
            * {{ box-sizing: border-box; -webkit-print-color-adjust: exact; }}
            body {{ font-family: 'Courier New', monospace; background: #d1d5db; margin: 0; padding: 0; }}
            .folha-a4 {{ background: white; width: 210mm; min-height: 297mm; margin: 20px auto; padding: 15mm; display: flex; flex-direction: column; position: relative; border: 1px solid #000; }}
            .header {{ border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 15px; text-align: center; }}
            .header h1 {{ margin: 5px 0; font-size: 18px; text-transform: uppercase; }}
            .confidencial {{ background: #000; color: #fff; padding: 2px 10px; font-size: 10px; font-weight: bold; text-align: center; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; font-size: 11px; }}
            th {{ background: #f2f2f2; text-align: left; padding: 5px; border: 1px solid #000; width: 30%; }}
            td {{ padding: 5px; border: 1px solid #000; }}
            .secao-titulo {{ background: #eee; border: 1px solid #000; padding: 4px; font-size: 10px; font-weight: bold; margin-top: 5px; text-transform: uppercase; }}
            .caixa-texto {{ border: 1px solid #000; border-top: none; padding: 8px; font-size: 11px; line-height: 1.3; white-space: pre-wrap; margin-bottom: 10px; min-height: 100px; }}
            .caixa-imagem {{ border: 1px solid #000; border-top: none; padding: 10px; text-align: center; background: #fafafa; }}
            .img-anexo {{ max-width: 100%; max-height: 400px; object-fit: contain; }}
            .linha-assinatura {{ border-top: 1px solid #000; width: 180px; margin: 25px auto 5px; text-align: center; font-size: 8px; font-weight: bold; text-transform: uppercase; }}
            .btn-print {{ position: fixed; top: 20px; right: 20px; background: #000; color: #fff; border: none; padding: 15px 25px; cursor: pointer; font-weight: bold; z-index: 100; border-radius: 5px; }}
            .token-footer {{ font-size: 8px; border-top: 1px solid #000; padding-top: 5px; display: flex; justify-content: space-between; margin-top: auto; }}
            @media print {{ .btn-print {{ display: none; }} body {{ background: white; }} .folha-a4 {{ margin: 0; box-shadow: none; border: none; }} }}
        </style>
    </head>
    <body>
        <button class="btn-print" onclick="window.print()">IMPRIMIR DOSSIÊ</button>
        <div class="folha-a4">
            <div class="header">
                <div class="confidencial">ESTRITAMENTE CONFIDENCIAL - LEI 14.457/22</div>
                <h1>Dossiê de Investigação Interna</h1>
                <small>Integridade El Shadday / Codetecx</small>
            </div>
            <table>
                <tr><th>PROTOCOLO:</th><td><b>{prot}</b></td></tr>
                <tr><th>DATA REGISTRO:</th><td>{d['data']}</td></tr>
                <tr><th>UNIDADE:</th><td>{d['unidade']}</td></tr>
                <tr><th>CATEGORIA:</th><td>{d['categoria']}</td></tr>
                <tr><th>ID SIGILOSO:</th><td><code>{id_seguro}</code></td></tr>
                <tr><th>STATUS ATUAL:</th><td>{d.get('status', 'EM ANÁLISE')}</td></tr>
            </table>
            <div class="secao-titulo">1. Relato dos Fatos</div>
            <div class="caixa-texto">{d['relato']}</div>
            {midia_html}
            <div class="secao-titulo">2. Parecer e Conclusão do Comitê</div>
            <div class="caixa-texto">{d.get('parecer_comite', 'Aguardando registro do parecer oficial...')}</div>
            <div class="assinaturas">
                <table style="border: none; width: 100%;">
                    <tr style="border: none;">
                        <td style="border: none; text-align: center;">
                            <div class="linha-assinatura">Responsável Triagem</div>
                        </td>
                        <td style="border: none; text-align: center;">
                            <div class="linha-assinatura">Comitê de Ética</div>
                        </td>
                    </tr>
                    <tr style="border: none;">
                        <td colspan="2" style="border: none; text-align: center; padding-top: 30px;">
                            <div class="linha-assinatura" style="margin: 0 auto; width: 250px;">Diretoria</div>
                        </td>
                    </tr>
                </table>
            </div>
            <div class="token-footer">
                <span><b>TOKEN:</b> {token_auth}</span>
                <span>Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</span>
            </div>
        </div>
    </body>
    </html>
    """
    return make_response(conteudo_html)

if __name__ == '__main__':
    porta = int(os.environ.get("PORT", 10000)) # O Render usa a 10000 por padrão
    app.run(host='0.0.0.0', port=porta, debug=False)