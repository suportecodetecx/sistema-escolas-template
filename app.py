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
import resend # <--- Adicionado para compatibilidade com Railway

# Constante para facilitar o uso do fuso horário de Brasília em todo o código
FUSO_BR = timezone(timedelta(hours=-3))

# CRIAÇÃO DO APP
app = Flask(__name__)
app.secret_key = 'chave_seguranca_codetecx_2026' # ESSA LINHA PERMITE O LOGIN

# --- VARIÁVEIS GLOBAIS ---
CHAVE_MESTRA = b'U2ZLBCXpcy_pEcsjdgCSxoZbYrbneHPDsSA47mso0xw='
cipher_suite = Fernet(CHAVE_MESTRA)

# ==========================================
# [BLOCO 01]: CONFIGURAÇÕES, SEGURANÇA E LICENÇA
# ==========================================
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# --- CONFIGURAÇÃO DO RESEND (API) ---
# Adicione a chave RESEND_API_KEY no painel do Railway
resend.api_key = os.environ.get("RESEND_API_KEY")

# --- AJUSTE DE AMBIENTE (Simulador vs Railway) ---
# --- AJUSTE DE AMBIENTE ---
# Ele tenta o Railway primeiro, se não existir, usa a pasta atual do servidor (Render/Local)
caminho_base = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', os.getcwd())

# Garante que as pastas existam para não dar erro ao salvar
UPLOAD_FOLDER = os.path.join(caminho_base, 'uploads')
DATA_FOLDER = os.path.join(caminho_base, 'data')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

# Configurações de E-mail e Alerta (Mantendo suas variáveis originais)
MEU_EMAIL_ENVIO = "suporte@codetecx.com"
MINHA_SENHA_APP = "wvutpranzjyyosuz" 
EMAIL_CAMILA = "suporte@codetecx.com"
LISTA_ADMINS = ["suporte@codetecx.com", EMAIL_CAMILA]

# Caminhos de arquivos
UPLOAD_FOLDER = os.path.join(caminho_base, 'uploads')
DB_FILE = os.path.join(caminho_base, 'denuncias_database.json')
ADMIN_CONFIG_FILE = os.path.join(caminho_base, 'admin_config.json')

# --- GARANTE QUE O ARQUIVO DE SENHA EXISTA ---
def inicializar_admin_config():
    """ Cria o arquivo de senha inicial APENAS se ele não existir """
    if not os.path.exists(ADMIN_CONFIG_FILE):
        config_inicial = {"user": "admin", "pass": "2821"}
        try:
            with open(ADMIN_CONFIG_FILE, 'w', encoding="utf-8") as f:
                json.dump(config_inicial, f, ensure_ascii=False, indent=4)
            print("✅ Arquivo de configuração inicial criado com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao criar arquivo de config: {e}")
    else:
        print("📁 Arquivo de senha detectado. Mantendo credenciais atuais.")

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

inicializar_admin_config()

# --- TRAVA DE LICENCIAMENTO ---
DATA_EXPIRACAO = "2026-12-24" 

def verificar_licenca():
    """ Retorna True se o sistema estiver dentro do prazo de validade """
    try:
        data_limite = datetime.strptime(DATA_EXPIRACAO, '%Y-%m-%d')
        return datetime.now() <= data_limite
    except:
        return False

def alertar_admin_bloqueio():
    """ Envia e-mail de falta de pagamento via Resend (Fiel ao seu texto original) """
    try:
        resend.Emails.send({
            "from": f"Sistema de Segurança <onboarding@resend.dev>",
            "to": EMAIL_CAMILA,
            "subject": "⚠️ AVISO IMPORTANTE: Suspensão de Licença - Canal de Ética",
            "html": f"""
                <p>Prezada Camila,</p>
                <p>Informamos que a licença de uso do Canal de Integridade El Shadday expirou em <strong>{DATA_EXPIRACAO}</strong>.</p>
                <p>Devido à ausência de renovação/pagamento, o sistema foi suspenso preventivamente. Para restabelecer o acesso e evitar a interrupção na recepção de relatos (Lei 14.457/22), por favor, entre em contato com o suporte técnico.</p>
            """
        })
        print("✅ Alerta de bloqueio enviado via Resend.")
    except Exception as e: 
        print(f"❌ Falha ao enviar alerta de bloqueio via Resend: {e}")

# --- HTML DA TELA DE BLOQUEIO PROFISSIONAL ---
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
            <div class="bg-blue-100 p-5 rounded-full animate-pulse">
                <svg class="w-10 h-10 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
            </div>
        </div>
        <h1 class="text-2xl font-black text-slate-800 uppercase italic">Sincronização de Segurança</h1>
        <p class="text-slate-500 text-sm leading-relaxed">
            Este módulo do <strong>Canal de Integridade</strong> está passando por uma validação de licença periódica obrigatória para garantir a integridade dos dados.
        </p>
        <div class="bg-white p-6 rounded-[2rem] shadow-xl shadow-blue-900/5 border border-slate-100">
            <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Status da Conectividade</p>
            <span class="inline-flex items-center px-4 py-1 rounded-full text-xs font-bold bg-orange-100 text-orange-700">
                Aguardando Validação do Ciclo
            </span>
        </div>
        <p class="text-[9px] text-slate-400 uppercase font-black tracking-tighter">
            Contate o suporte técnico para restabelecer o acesso total ao painel.
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
    return jsonify({"status": "erro", "msg": "Arquivo muito grande! O limite é 16MB."}), 413

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
# [BLOCO 04]: MOTOR DE PROCESSAMENTO (RESEND)
# ==========================================
def enviar_emails_async(unidade, data_hora, protocolo, email_bruto):
    """ Envio assíncrono otimizado via RESEND (Sem erro 101) """
    try:
        BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8080")
        link_gestao = f"{BASE_URL}/gestao/{protocolo}"

        # EMAIL ADMIN
        resend.Emails.send({
            "from": f"Canal de Integridade <onboarding@resend.dev>",
            "to": LISTA_ADMINS,
            "subject": f"ALERTA: Nova Denúncia #{protocolo} - {unidade}",
            "html": f"""
                <h3>Nova denúncia recebida no sistema.</h3>
                <p><strong>Unidade:</strong> {unidade}<br>
                <strong>Data:</strong> {data_hora}<br>
                <strong>Protocolo:</strong> {protocolo}</p>
                <p><a href='{link_gestao}'>Para visualizar o dossiê completo, acesse aqui.</a></p>
            """
        })

        # EMAIL DENUNCIANTE
        if email_bruto and "@" in str(email_bruto):
            resend.Emails.send({
                "from": f"Canal de Integridade El Shadday <onboarding@resend.dev>",
                "to": email_bruto.strip(),
                "subject": f"Confirmação de Registro - Protocolo #{protocolo}",
                "html": f"""
                    <p>Olá,</p>
                    <p>Seu relato foi registrado com sucesso em nosso Canal de Integridade.</p>
                    <p><strong>PROTOCOLO PARA CONSULTA:</strong> {protocolo}<br>
                    <strong>DATA:</strong> {data_hora}<br>
                    <strong>UNIDADE:</strong> {unidade}</p>
                    <p>Guardar seu número de protocolo para acompanhar o status no site.</p>
                    <p>Atenciosamente,<br>Comitê de Ética El Shadday</p>
                """
            })
        print(f"✅ Fluxo de e-mails do protocolo {protocolo} via Resend concluído.")
    except Exception as e:
        print(f"❌ ERRO NA THREAD DE EMAIL (RESEND): {e}")

@app.route('/enviar', methods=['POST'])
def enviar():
    if not verificar_licenca(): return jsonify({"status": "erro", "msg": "Licença expirada."}), 403
    try:
        fuso_br = timezone(timedelta(hours=-3))
        agora = datetime.now(fuso_br)
        protocolo = gerar_protocolo_sequencial()
        data_hora = agora.strftime('%d/%m/%Y %H:%M:%S')
        
        unidade = request.form.get('unidade') 
        categoria = request.form.get('categoria')
        assunto = request.form.get('titulo')
        relato = request.form.get('relato')
        email_bruto = request.form.get('email_opcional')
        arquivo = request.files.get('arquivo')
        
        nome_setor_pasta = secure_filename(unidade)
        caminho_final_setor = os.path.join(UPLOAD_FOLDER, nome_setor_pasta)
        if not os.path.exists(caminho_final_setor): os.makedirs(caminho_final_setor)

        conteudo_anexo_final = "Nenhum"
        if arquivo and arquivo.filename != '':
            if allowed_file(arquivo.filename):
                extensao = os.path.splitext(arquivo.filename)[1].lower().replace('.', '')
                if extensao == 'jpg': extensao = 'jpeg'
                imagem_bits = arquivo.read()
                imagem_base64 = base64.b64encode(imagem_bits).decode('utf-8')
                conteudo_anexo_final = f"data:image/{extensao};base64,{imagem_base64}"
            else: return jsonify({"status": "erro", "msg": "❌ ARQUIVO BLOQUEADO."}), 400

        nova_denuncia = {
            "protocolo": protocolo,
            "data": data_hora,
            "unidade": unidade,
            "setor_pasta": nome_setor_pasta,
            "categoria": categoria,
            "assunto": assunto,
            "relato": relato,
            "anexo": conteudo_anexo_final,
            "email_contato": criptografar_dado(email_bruto),
            "status": "Recebido / Em Triagem",
            "parecer_comite": ""            
        }
        
        banco = []
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                try: banco = json.load(f)
                except: banco = []

        banco.append(nova_denuncia)
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(banco, f, indent=2, ensure_ascii=False)

        threading.Thread(target=enviar_emails_async, args=(unidade, data_hora, protocolo, email_bruto), daemon=True).start()

        response = jsonify({"status": "sucesso", "protocolo": protocolo})
        response.set_cookie('ultimo_protocolo', protocolo, max_age=60*60*24*30)
        return response, 200
    except Exception as e:
        print("❌ ERRO GERAL /enviar:", e)
        return jsonify({"status": "erro", "msg": "Erro interno"}), 500

# ==========================================
# [BLOCO 05]: GESTÃO, DASHBOARD E PARECER
# ==========================================
def carregar_credenciais():
    if os.path.exists(ADMIN_CONFIG_FILE):
        try:
            with open(ADMIN_CONFIG_FILE, 'r', encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"user": "admin", "pass": "2821"}

def enviar_email_conclusao(email_criptografado, protocolo, parecer):
    """ Notifica conclusão via Resend """
    try:
        if not email_criptografado or "ANONIMO" in email_criptografado: return False
        email_real = cipher_suite.decrypt(email_criptografado.encode()).decode().strip()
        
        resend.Emails.send({
            "from": f"Comitê de Ética EL SHADDAY <onboarding@resend.dev>",
            "to": email_real,
            "subject": f"CONCLUSÃO DE CHAMADO: Protocolo #{protocolo}",
            "html": f"""
                <div style="font-family: sans-serif; padding: 20px; border: 1px solid #eee;">
                    <h3>Atualização de Relato</h3>
                    <p>Protocolo: <strong>{protocolo}</strong></p>
                    <p><strong>Parecer Final:</strong><br>{parecer}</p>
                    <p>Este retorno encerra o processo de apuração interna.</p>
                </div>
            """
        })
        print(f"✅ Conclusão enviada via Resend para {email_real}")
        return True
    except Exception as e:
        print(f"❌ Erro notificação final: {e}")
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
    if not session.get('admin_logado'): return redirect(url_for('login'))
    denuncias_total = []
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: denuncias_total = json.load(f)
            except: denuncias_total = []
    return render_template('dashboard.html', denuncias=denuncias_total[::-1])

@app.route('/atualizar_denuncia', methods=['POST'])
def atualizar():
    if not session.get('admin_logado'): return redirect(url_for('login'))
    prot = request.form.get('protocolo')
    novo_status = request.form.get('status')
    novo_parecer = request.form.get('parecer')
    
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f: banco = json.load(f)
        email_alvo = None
        for d in banco:
            if d['protocolo'] == prot:
                d['status'] = novo_status
                d['parecer_comite'] = novo_parecer
                email_alvo = d.get('email_contato')
                break
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(banco, f, indent=2, ensure_ascii=False)
        
        if novo_status == "Finalizada" and email_alvo:
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
        except: return "Erro ao salvar", 500
    return "Erro: Senha vazia", 400

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
    porta = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=porta, debug=False)