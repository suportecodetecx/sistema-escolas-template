from flask import Flask, render_template, request, jsonify, make_response, session, redirect, url_for
import json, os, hashlib, base64
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet

# Fuso horário de Brasília
FUSO_BR = timezone(timedelta(hours=-3))

app = Flask(__name__)
app.secret_key = 'chave_seguranca_codetecx_2026'

# --- VARIÁVEIS GLOBAIS E CRIPTOGRAFIA ---
CHAVE_MESTRA = b'U2ZLBCXpcy_pEcsjdgCSxoZbYrbneHPDsSA47mso0xw='
cipher_suite = Fernet(CHAVE_MESTRA)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# --- AJUSTE DE AMBIENTE (VERCEL) ---
# Na Vercel, usamos /tmp para persistência temporária durante a sessão
if os.environ.get('VERCEL'):
    DB_FILE = os.path.join('/tmp', 'denuncias_database.json')
    ADMIN_CONFIG_FILE = os.path.join('/tmp', 'admin_config.json')
else:
    caminho_base = os.getcwd()
    DB_FILE = os.path.join(caminho_base, 'denuncias_database.json')
    ADMIN_CONFIG_FILE = os.path.join(caminho_base, 'admin_config.json')

# --- INICIALIZAÇÃO DE SEGURANÇA ---
def inicializar_admin_config():
    if not os.path.exists(ADMIN_CONFIG_FILE):
        config_inicial = {"user": "admin", "pass": "2821"}
        try:
            with open(ADMIN_CONFIG_FILE, 'w', encoding="utf-8") as f:
                json.dump(config_inicial, f, ensure_ascii=False, indent=4)
        except: pass

inicializar_admin_config()

# --- TRAVA DE LICENCIAMENTO ---
DATA_EXPIRACAO = "2026-12-24" 
def verificar_licenca():
    try:
        data_limite = datetime.strptime(DATA_EXPIRACAO, '%Y-%m-%d')
        agora = datetime.now(FUSO_BR).replace(tzinfo=None)
        return agora <= data_limite
    except: return False

HTML_BLOQUEIO = """
<!DOCTYPE html>
<html lang="pt-br">
<head><meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script><title>Validação</title></head>
<body class="bg-slate-50 flex items-center justify-center min-h-screen p-6">
    <div class="max-w-md w-full text-center space-y-6">
        <h1 class="text-2xl font-black text-slate-800 uppercase italic">Sincronização de Segurança</h1>
        <p class="text-slate-500 text-sm">Licença expirada em 2026-12-24. Contate o suporte técnico.</p>
    </div>
</body>
</html>
"""

# ==========================================
# [BLOCO 02]: SEGURANÇA E AUXILIARES
# ==========================================
def criptografar_dado(texto):
    if not texto or "@" not in str(texto): return "ANONIMO"
    texto_preparado = str(texto).lower().strip().encode()
    return cipher_suite.encrypt(texto_preparado).decode()

def gerar_protocolo_sequencial():
    data_hoje = datetime.now(FUSO_BR).strftime('%Y%m%d')
    contador = 1
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try:
                banco = json.load(f)
                hoje_count = [d for d in banco if str(d.get('protocolo', '')).startswith(data_hoje)]
                contador = len(hoje_count) + 1
            except: pass
    return f"{data_hoje}-{str(contador).zfill(4)}"

# ==========================================
# [BLOCO 03]: ROTAS DO USUÁRIO
# ==========================================
@app.route('/')
def home():
    if not verificar_licenca(): return HTML_BLOQUEIO, 403
    ultimo_visto = request.cookies.get('ultimo_protocolo', 'Nenhum')
    return render_template('denuncia.html', ultimo=ultimo_visto)

@app.route('/consultar/<prot>')
def consultar(prot):
    if not verificar_licenca(): return "Indisponível", 403
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            banco = json.load(f)
            for d in banco:
                if d['protocolo'] == prot:
                    resp = make_response(jsonify({"status": d['status']}))
                    resp.set_cookie('ultimo_protocolo', prot, max_age=60*60*24*7) 
                    return resp
    return jsonify({"status": "Nao encontrado"}), 404

@app.route('/enviar', methods=['POST'])
def enviar():
    if not verificar_licenca(): return jsonify({"status": "erro"}), 403
    try:
        agora = datetime.now(FUSO_BR)
        protocolo = gerar_protocolo_sequencial()
        
        arquivo = request.files.get('arquivo')
        conteudo_anexo_final = "Nenhum"
        if arquivo and arquivo.filename != '':
            extensao = os.path.splitext(arquivo.filename)[1].lower().replace('.', '')
            if extensao in ['png', 'jpg', 'jpeg', 'webp']:
                imagem_base64 = base64.b64encode(arquivo.read()).decode('utf-8')
                conteudo_anexo_final = f"data:image/{extensao};base64,{imagem_base64}"

        nova_denuncia = {
            "protocolo": protocolo,
            "data": agora.strftime('%d/%m/%Y %H:%M:%S'),
            "unidade": request.form.get('unidade'),
            "categoria": request.form.get('categoria'),
            "assunto": request.form.get('titulo'),
            "relato": request.form.get('relato'),
            "anexo": conteudo_anexo_final,
            "email_contato": criptografar_dado(request.form.get('email_opcional')),
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

        resp = make_response(jsonify({"status": "sucesso", "protocolo": protocolo}))
        resp.set_cookie('ultimo_protocolo', protocolo, max_age=60*60*24*30)
        return resp
    except Exception as e: return jsonify({"status": "erro", "msg": str(e)}), 500

# ==========================================
# [BLOCO 05]: GESTÃO E DASHBOARD
# ==========================================
def carregar_credenciais():
    if os.path.exists(ADMIN_CONFIG_FILE):
        try:
            with open(ADMIN_CONFIG_FILE, 'r', encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"user": "admin", "pass": "2821"}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logado'): return redirect(url_for('dashboard'))
    if request.method == 'POST':
        cred = carregar_credenciais()
        if request.form.get('user') == cred['user'] and request.form.get('pass') == cred['pass']:
            session['admin_logado'] = True
            return redirect(url_for('dashboard'))
        return render_template('login.html', erro="Incorreto")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logado', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not session.get('admin_logado'): return redirect(url_for('login'))
    denuncias = []
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: denuncias = json.load(f)
            except: pass
    return render_template('dashboard.html', denuncias=denuncias[::-1])

@app.route('/atualizar_denuncia', methods=['POST'])
def atualizar():
    if not session.get('admin_logado'): return redirect(url_for('login'))
    prot = request.form.get('protocolo')
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            banco = json.load(f)
        for d in banco:
            if d['protocolo'] == prot:
                d['status'] = request.form.get('status')
                d['parecer_comite'] = request.form.get('parecer')
                break
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(banco, f, indent=2, ensure_ascii=False)
    return redirect(url_for('dashboard'))

@app.route('/alterar_acesso', methods=['POST'])
def alterar_senha():
    if not session.get('admin_logado'): return redirect(url_for('login'))
    nova = request.form.get('nova_senha')
    if nova:
        with open(ADMIN_CONFIG_FILE, 'w', encoding="utf-8") as f:
            json.dump({"user": "admin", "pass": str(nova)}, f, indent=4)
    return redirect(url_for('dashboard'))

# ==========================================
# [BLOCO 06]: DOSSIÊ DE IMPRESSÃO (HTML PRESERVADO)
# ==========================================
@app.route('/gestao/<prot>')
def area_segura(prot):
    if not session.get('admin_logado'): return redirect(url_for('login'))
    d = None
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            banco = json.load(f)
            d = next((item for item in banco if item['protocolo'] == prot), None)
    if not d: return "Não encontrado", 404

    id_seguro = "ID_SIGILOSO"
    token_auth = hashlib.md5(f"{prot}{d['data']}".encode()).hexdigest().upper()[:20]
    midia_html = f"""<div class="container-midia"><div class="secao-titulo">Anexo Enviado</div><div class="caixa-imagem"><img src="{d['anexo']}" class="img-anexo"></div></div>""" if d.get('anexo') and d['anexo'] != "Nenhum" else ""

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

app = app

if __name__ == '__main__':
    app.run(debug=True)