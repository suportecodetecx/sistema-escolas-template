from flask import Flask, render_template, request, jsonify, make_response, session, redirect, url_for
from flask import flash, redirect, url_for, request, session # Certifique-se de que 'flash' está importado
import json, os, hashlib, base64
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet
from pymongo import MongoClient  # Adicionado para conexão com banco

# Fuso horário de Brasília
FUSO_BR = timezone(timedelta(hours=-3))

app = Flask(__name__)
app.secret_key = 'chave_seguranca_codetecx_2026'

# --- CONFIGURAÇÃO MONGODB (SUBSTITUI JSON) ---
MONGO_URI = "mongodb+srv://suporte_db_user:2kT3pEb8AcXFWNbk@cluster0.vw8vm8p.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)
db = client['sistema_elshadday']
col_denuncias = db['denuncias']
col_config = db['config_admin']

# --- VARIÁVEIS GLOBAIS E CRIPTOGRAFIA ---
CHAVE_MESTRA = b'U2ZLBCXpcy_pEcsjdgCSxoZbYrbneHPDsSA47mso0xw='
cipher_suite = Fernet(CHAVE_MESTRA)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 

# --- INICIALIZAÇÃO DE SEGURANÇA ---
def inicializar_admin_config():
    acessos_mestre = [
        {"user": "admin", "pass": "2821", "nome": "Direção El Shadday", "unidade": "Ceic El Shadday"},
        {"user": "admin2", "pass": "1234", "nome": "Gestão Egberto", "unidade": "Ceim Egberto"},
        {"user": "suporte_codetecx", "pass": "mestra@2026", "nome": "Suporte Técnico", "unidade": "Geral"}
    ]

    for credencial in acessos_mestre:
        # Tenta encontrar o usuário
        usuario_existente = col_config.find_one({"user": credencial["user"]})
        
        if not usuario_existente:
            col_config.insert_one(credencial)
            print(f"✅ USUÁRIO CRIADO: {credencial['user']}")
        else:
            # OPCIONAL: Garante que a senha no banco seja a mesma do código
            col_config.update_one(
                {"user": credencial["user"]}, 
                {"$set": {"pass": credencial["pass"], "unidade": credencial["unidade"]}}
            )
            print(f"🔄 USUÁRIO ATUALIZADO: {credencial['user']}")

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


def gerar_protocolo_sequencial():
    data_hoje = datetime.now(FUSO_BR).strftime('%Y%m%d')
    regex = f"^{data_hoje}"
    contador = col_denuncias.count_documents({"protocolo": {"$regex": regex}}) + 1
    return f"{data_hoje}-{str(contador).zfill(4)}"
# ==========================================
# ==========================================
# [BLOCO 03]: ROTAS DO USUÁRIO
# ==========================================
@app.route('/')
def home():
    if not verificar_licenca(): return HTML_BLOQUEIO, 403
    ultimo_visto = request.cookies.get('ultimo_protocolo', 'Nenhum')
    return render_template('denuncia.html', ultimo=ultimo_visto)

# --- ADICIONE ESTAS LINHAS AQUI ---
@app.route('/politica-privacidade')
def politica():
    return render_template('politica-privacidade.html')
# ----------------------------------

@app.route('/consultar/<prot>')
def consultar(prot):
    if not verificar_licenca(): return "Indisponível", 403
    # Busca no MongoDB
    d = col_denuncias.find_one({"protocolo": prot})
    if d:
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
        
        # Tratamento de anexo
        arquivo = request.files.get('arquivo')
        conteudo_anexo_final = "Nenhum"
        if arquivo and arquivo.filename != '':
            extensao = os.path.splitext(arquivo.filename)[1].lower().replace('.', '')
            if extensao in ['png', 'jpg', 'jpeg', 'webp']:
                imagem_base64 = base64.b64encode(arquivo.read()).decode('utf-8')
                conteudo_anexo_final = f"data:image/{extensao};base64,{imagem_base64}"

        # Captura o e-mail em texto simples
        # Se o usuário não preencher, salvamos como "ANÔNIMO"
        email_bruto = request.form.get('email_opcional', '').strip()
        email_final = email_bruto if email_bruto else "ANÔNIMO"

        nova_denuncia = {
            "protocolo": protocolo,
            "data": agora.strftime('%d/%m/%Y %H:%M:%S'),
            "unidade": request.form.get('unidade'),
            "categoria": request.form.get('categoria'),
            "assunto": request.form.get('titulo'),
            "relato": request.form.get('relato'),
            "anexo": conteudo_anexo_final,
            "email_contato": email_final, # TEXTO SIMPLES PARA O DOSSIÊ
            "status": "Recebido / Em Triagem",
            "parecer_comite": ""           
        }
        
        # Insere no MongoDB
        col_denuncias.insert_one(nova_denuncia)

        resp = make_response(jsonify({"status": "sucesso", "protocolo": protocolo}))
        resp.set_cookie('ultimo_protocolo', protocolo, max_age=60*60*24*30)
        return resp
    except Exception as e: return jsonify({"status": "erro", "msg": str(e)}), 500

# ==========================================
# [BLOCO 05]: GESTÃO E DASHBOARD
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logado'): 
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        usuario_digitado = request.form.get('user')
        senha_digitada = request.form.get('pass')

        # BUSCA NO BANCO: Ajustado para os campos que aparecem no seu print do Atlas
        # Se no Atlas estiver 'usuario', use 'usuario'. Se for 'usu...', complete o nome.
        user_no_banco = col_config.find_one({"usuario": usuario_digitado})

        if user_no_banco and user_no_banco.get('senha') == senha_digitada:
            session['admin_logado'] = True
            session['admin_user'] = user_no_banco.get('usuario')
            session['admin_nome'] = user_no_banco.get('nome', 'Administrador')
            session['admin_unidade'] = user_no_banco.get('unidade', 'Geral')
            return redirect(url_for('dashboard'))
        
        return render_template('login.html', erro="Incorreto")
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not session.get('admin_logado'): 
        return redirect(url_for('login'))
    
    denuncias = list(col_denuncias.find({}, {'_id': 0}).sort("data", -1))
    
    return render_template('dashboard.html', 
                           denuncias=denuncias, 
                           unidade_atual=session.get('admin_unidade'),
                           nome_admin=session.get('admin_nome'))

@app.route('/atualizar_denuncia', methods=['POST'])
def atualizar():
    if not session.get('admin_logado'): 
        return redirect(url_for('login'))
        
    prot = request.form.get('protocolo')
    
    col_denuncias.update_one(
        {"protocolo": prot},
        {"$set": {
            "status": request.form.get('status'),
            "parecer_comite": request.form.get('parecer')
        }}
    )
    return redirect(url_for('dashboard'))

@app.route('/alterar_acesso', methods=['POST'])
def alterar_senha():
    if not session.get('admin_logado'): 
        return redirect(url_for('login'))
    
    usuario_atual = session.get('admin_user')
    novo_user = request.form.get('novo_user')
    nova_senha = request.form.get('nova_senha')
    
    if nova_senha and novo_user:
        # Atualiza usando as chaves corretas do banco
        col_config.update_one(
            {"usuario": usuario_atual}, 
            {"$set": {"usuario": novo_user, "senha": str(nova_senha)}}
        )
        session['admin_user'] = novo_user
        flash('Acesso atualizado com sucesso!', 'success')
        return "OK", 200
    return "Erro", 400

# ==========================================
# [BLOCO 06]: DOSSIÊ DE IMPRESSÃO
# ==========================================
@app.route('/gestao/<prot>')
def area_segura(prot):
    if not session.get('admin_logado'): return redirect(url_for('login'))
    
    d = col_denuncias.find_one({"protocolo": prot}, {'_id': 0})
    if not d: return "Não encontrado", 404

    # Ajuste do Email no Dossiê
    email_banco = d.get('email_contato', 'ANÔNIMO')
    id_seguro = email_banco if email_banco != "ANÔNIMO" else "SIGILOSO"
    
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
                <tr><th>ID DENUNCIANTE:</th><td><code>{id_seguro}</code></td></tr>
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
    # O use_reloader=False evita o erro de soquete no Windows
    app.run(debug=True, use_reloader=False)