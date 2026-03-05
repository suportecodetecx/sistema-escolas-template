from flask import Flask, render_template, request, jsonify, make_response, session, redirect, url_for, flash
from flask_wtf.csrf import CSRFProtect, generate_csrf
import json, os, hashlib, base64
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet
from pymongo import MongoClient 
from datetime import timedelta

# ============================================================
# === [1] CONFIGURAÇÕES GERAIS DO SERVIDOR                 ===
# ============================================================
FUSO_BR = timezone(timedelta(hours=-3))

app = Flask(__name__)
app.secret_key = 'chave_seguranca_codetecx_2026'

# --- AJUSTE: SESSÃO PERMANENTE (30 DIAS) ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

@app.before_request
def fazer_sessao_permanente():
    session.permanent = True

# ATIVAÇÃO DA PROTEÇÃO CSRF
csrf = CSRFProtect(app)

# ============================================================
# === [2] CONEXÃO COM O BANCO DE DADOS (MONGODB)           ===
# ============================================================
MONGO_URI = "mongodb+srv://suporte_db_user:2kT3pEb8AcXFWNbk@cluster0.vw8vm8p.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI, connectTimeoutMS=30000, serverSelectionTimeoutMS=30000)

# Nome do Banco de Dados principal
db = client['sistema_empresa'] 
col_config = db['config_admin']

# ============================================================
# === [3] IDENTIDADE VISUAL (CORES DO WHITE LABEL)         ===
# === PARA ADICIONAR NOVA EMPRESA: ADICIONE UM BLOCO AQUI  ===
# ============================================================
CORES_SISTEMA = {
    "sol-magico": {
        "primaria": "#106ab9",
        "secundaria": "#fb923c",
        "tema": "light"
    },
    "lua-nova": {
        "primaria": "#4f46e5",
        "secundaria": "#fb923c",
        "tema": "light"
    },
    "uniao": {
        "primaria": "#475e93",
        "secundaria": "#fb923c",
        "tema": "light"
    },
    "do-re-mi": {
        "primaria": "#2a27db",
        "secundaria": "#fb923c",
        "tema": "light"
    }
}

# ============================================================
# === [4] NOMES (Padronizados para Minúsculo)              ===
# ============================================================
CONFIG_EMPRESAS = {
    "sol-magico": {"nome": "Sol Mágico", "unidades": ["Sol Mágico I", "Sol Mágico II"], "slug": "sol-magico"},
    "lua-nova": {"nome": "Lua Nova", "unidades": ["Lua Nova I", "Lua Nova II"], "slug": "lua-nova"},
    "uniao": {"nome": "União", "unidades": ["União I", "União II"], "slug": "uniao"},
    "do-re-mi": {"nome": "Do Re Mi", "unidades": ["Do Re Mi I", "Do Re Mi II"], "slug": "do-re-mi"}
}

# ============================================================
# === [5] DOMÍNIOS (O Segredo para parar o Erro 404)       ===
# ============================================================
DOMINIOS_CLIENTES = {
    # Vercel (O que você já configurou lá)
    'uniao.codetecx.com': 'uniao',
    'sol-magico.codetecx.com': 'sol-magico',
    'lua-nova.codetecx.com': 'lua-nova',

    # Local (Porta 8000)
    'localhost:8000': 'uniao', 
    '127.0.0.1:8000': 'uniao',
    '0.0.0.0:8000': 'uniao',

    # Link padrão Vercel
    'sistema-escolas-template.vercel.app': 'sol-magico'
}

CHAVE_MESTRA = b'U2ZLBCXpcy_pEcsjdgCSxoZbYrbneHPDsSA47mso0xw='
cipher_suite = Fernet(CHAVE_MESTRA)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 


# ============================================================
# === [5] MOTOR DE CUSTOMIZAÇÃO (CONTEXT PROCESSOR)        ===
# ============================================================
@app.context_processor
def inject_empresa_context():
    slug = request.view_args.get('empresa_slug') if request.view_args else None
    
    if not slug:
        ref = request.referrer or ""
        for s in CONFIG_EMPRESAS.keys():
            if f"/{s}" in ref:
                slug = s
                break

    if not slug:
        host = request.host
        slug = DOMINIOS_CLIENTES.get(host)

    if not slug or slug not in CONFIG_EMPRESAS:
        slug = 'sol-magico'

    dados_padrao = CONFIG_EMPRESAS.get('sol-magico')
    cores_padrao = CORES_SISTEMA.get('sol-magico')

    dados = CONFIG_EMPRESAS.get(slug, dados_padrao).copy()
    cores = CORES_SISTEMA.get(slug, cores_padrao)
    
    dados['cor_primaria'] = cores.get('primaria', '#059669')
    dados['cor_secundaria'] = cores.get('secundaria', '#fbbf24')
    dados['tema'] = cores.get('tema', 'light')
    
    status_login = session.get('admin_logado', False)
    
    return dict(
        empresa_site=dados, 
        slug_site=slug, 
        estilo_site=cores, 
        admin_logado=status_login
    )


# ============================================================
# === [6] GESTÃO DE USUÁRIOS E ACESSOS                     ===
# === ADICIONE OU MUDE SENHAS DE ADMINISTRADORES AQUI      ===
# ============================================================
def inicializar_admin_config():
    acessos_mestre = [
        # MASTER (Codetecx)
        {
            "user": "suporte_codetecx", 
            "pass": "Code@", 
            "nome": "Suporte Técnico", 
            "unidade": "Geral", 
            "empresa_exibicao": "Codetecx"
        },
        
        # EMPRESA: UNIÃO
        {"user": "admin", "pass": "2821", "nome": "Direção União", "unidade": "Uniao", "empresa_exibicao": "União"},
        {"user": "uniao2", "pass": "1234", "nome": "Auxiliar União", "unidade": "Uniao", "empresa_exibicao": "União"},

        # EMPRESA: DO-RE-MI
        {"user": "admin2", "pass": "1234", "nome": "Gestão Do Re Mi", "unidade": "Do-re-mi", "empresa_exibicao": "Do Re Mi"},

        # EMPRESA: SOL MÁGICO
        {"user": "AdminSol", "pass": "1234", "nome": "Direção Sol Mágico", "unidade": "sol-magico", "empresa_exibicao": "Sol Mágico"},

        # EMPRESA: LUA NOVA
        {"user": "AdminLua", "pass": "1234", "nome": "Direção Lua Nova", "unidade": "lua-nova", "empresa_exibicao": "Lua Nova"}
    ]
    
    for credencial in acessos_mestre:
        col_config.update_one(
            {"user": credencial["user"]}, 
            {"$set": credencial},
            upsert=True
        )

inicializar_admin_config()

# ============================================================
# === [7] SEGURANÇA E LICENCIAMENTO                        ===
# ============================================================
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

def gerar_protocolo_dinamico(slug):
    col_atual = db[f'denuncias_{slug}']
    data_hoje = datetime.now(FUSO_BR).strftime('%Y%m%d')
    regex = f"^{data_hoje}"
    contador = col_atual.count_documents({"protocolo": {"$regex": regex}}) + 1
    return f"{data_hoje}-{str(contador).zfill(4)}"

# ==========================================
# [ROTAS DO USUÁRIO (FRONT-END)]
# ==========================================

@app.route('/')
def home():
    return "Por favor, acesse pelo link enviado pela sua instituição (Ex: /sol-magico)", 404

@app.route('/<empresa_slug>')
def home_empresa(empresa_slug):
    if not verificar_licenca(): return HTML_BLOQUEIO, 403
    config = CONFIG_EMPRESAS.get(empresa_slug)
    if not config:
        return "Empresa não encontrada", 404
        
    cores_atuais = CORES_SISTEMA.get(empresa_slug, CORES_SISTEMA['Uniao'])
    ultimo_visto = request.cookies.get('ultimo_protocolo', 'Nenhum')
    
    return render_template('denuncia.html', 
                            ultimo=ultimo_visto, 
                            nome_sistema=f"Portal {config['nome']}", 
                            unidades=config['unidades'],
                            slug_atual=empresa_slug,
                            cores=cores_atuais)

@app.route('/politica-privacidade')
def politica():
    return render_template('politica-privacidade.html')

@app.route('/consultar/<prot>')
def consultar(prot):
    if not verificar_licenca(): return "Indisponível", 403
    for nome_col in db.list_collection_names():
        if nome_col.startswith("denuncias_"):
            d = db[nome_col].find_one({"protocolo": prot})
            if d:
                resp = make_response(jsonify({"status": d['status']}))
                resp.set_cookie('ultimo_protocolo', prot, max_age=60*60*24*7) 
                return resp
    return jsonify({"status": "Nao encontrado"}), 404

@app.route('/enviar', methods=['POST'])
def enviar():
    if not verificar_licenca(): return jsonify({"status": "erro"}), 403
    try:
        slug = request.form.get('empresa_slug', 'geral')
        col_atual = db[f'denuncias_{slug}']
        
        agora = datetime.now(FUSO_BR)
        protocolo = gerar_protocolo_dinamico(slug)
        
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
            "email_contato": request.form.get('email_opcional', 'ANÔNIMO'),
            "status": "Recebido / Em Triagem",
            "parecer_comite": ""           
        }
        col_atual.insert_one(nova_denuncia)
        resp = make_response(jsonify({"status": "sucesso", "protocolo": protocolo}))
        resp.set_cookie('ultimo_protocolo', protocolo, max_age=60*60*24*30)
        return resp
    except Exception as e: return jsonify({"status": "erro", "msg": str(e)}), 500

# ==========================================
# [GESTÃO E DASHBOARD (BACK-END)]
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logado'): 
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        usuario_digitado = request.form.get('user')
        senha_digitada = request.form.get('pass')
        
        user_no_banco = col_config.find_one({"user": usuario_digitado})

        if user_no_banco and str(user_no_banco.get('pass')) == str(senha_digitada):
            session.clear()
            
            empresa_nome = user_no_banco.get('empresa_exibicao', 'Sistema')
            
            session.update({
                'admin_logado': True,
                'admin_user': user_no_banco.get('user'),
                'admin_nome': user_no_banco.get('nome', 'Administrador'),
                'admin_unidade': user_no_banco.get('unidade', 'Geral'),
                'admin_empresa_nome': empresa_nome 
            })
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
        
    unidade_admin = session.get('admin_unidade')
    denuncias = []
    
    if unidade_admin == "Geral":
        for nome_col in db.list_collection_names():
            if nome_col.startswith("denuncias_"):
                itens = list(db[nome_col].find({}, {'_id': 0}))
                for item in itens:
                    item['colecao_origem'] = nome_col
                denuncias.extend(itens)
        denuncias.sort(key=lambda x: x.get('data', ''), reverse=True)
    else:
        nome_colecao = f'denuncias_{unidade_admin}'
        denuncias = list(db[nome_colecao].find({}, {'_id': 0}).sort("data", -1))
        for d in denuncias:
            d['colecao_origem'] = nome_colecao

    for d in denuncias:
        if not d.get('status'):
            d['status'] = "Recebido / Em Triagem"

    return render_template('dashboard.html', 
                            denuncias=denuncias, 
                            unidade_atual=unidade_admin,
                            nome_admin=session.get('admin_nome'),
                            empresa_nome=session.get('admin_empresa_nome'))

@app.route('/atualizar_denuncia', methods=['POST'])
def atualizar():
    if not session.get('admin_logado'): 
        return redirect(url_for('login'))
        
    prot = request.form.get('protocolo')
    novo_status = request.form.get('status')
    novo_parecer = request.form.get('parecer')
    colecao_alvo = request.form.get('colecao_origem') 

    if not colecao_alvo:
        unidade_admin = session.get('admin_unidade')
        colecao_alvo = f'denuncias_{unidade_admin}'

    db[colecao_alvo].update_one(
        {"protocolo": prot},
        {"$set": {
            "status": novo_status, 
            "parecer_comite": novo_parecer,
            "data_atualizacao": datetime.now().strftime('%d/%m/%Y %H:%M')
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
        col_config.update_one(
            {"user": usuario_atual}, 
            {"$set": {"user": novo_user, "pass": str(nova_senha)}}
        )
        session['admin_user'] = novo_user
        return "OK", 200
        
    return "Erro", 400

# ============================================================
# === [SISTEMA DE DOSSIÊ - IMPRESSÃO SEGURA]               ===
# ============================================================
@app.route('/gestao/<prot>')
def area_segura(prot):
    if not session.get('admin_logado'): return redirect(url_for('login'))
    unidade_admin = session.get('admin_unidade')
    
    d = None
    if unidade_admin == "Geral":
        for nome_col in db.list_collection_names():
            if nome_col.startswith("denuncias_"):
                d = db[nome_col].find_one({"protocolo": prot}, {'_id': 0})
                if d: break
    else:
        d = db[f'denuncias_{unidade_admin}'].find_one({"protocolo": prot}, {'_id': 0})

    if not d: return "Não encontrado", 404

    # --- LÓGICA DE SIGILO ---
    email_banco = d.get('email_contato', '').strip()
    if not email_banco or email_banco.upper() in ["ANÔNIMO", "ANONIMO", "NENHUM"]:
        id_seguro = "SIGILOSO / ANÔNIMO"
    else:
        id_seguro = email_banco

    # --- TOKEN DINÂMICO POR IMPRESSÃO ---
    agora_agora = datetime.now().strftime('%d%m%Y%H%M%S%f')
    token_auth = hashlib.md5(f"{prot}{agora_agora}".encode()).hexdigest().upper()[:20]
    
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
                <small>Canal de Ética / Codetecx</small>
            </div>
            <table>
                <tr><th>PROTOCOLO:</th><td><b>{prot}</b></td></tr>
                <tr><th>DATA REGISTRO:</th><td>{d['data']}</td></tr>
                <tr><th>UNIDADE:</th><td>{d['unidade']}</td></tr>
                <tr><th>CATEGORIA:</th><td>{d['categoria']}</td></tr>
                <tr><th>ID DENUNCIANTE:</th><td><code style="font-weight: bold;">{id_seguro}</code></td></tr>
                <tr><th>STATUS ATUAL:</th><td>{d.get('status', 'EM ANÁLISE')}</td></tr>
            </table>
            <div class="secao-titulo">1. Relato dos Fatos</div>
            <div class="caixa-texto">{d['relato']}</div>
            {midia_html}
            <div class="secao-titulo">2. Parecer e Conclusão do Comitê</div>
            <div class="caixa-texto">{d.get('parecer_comite', 'Aguardando registro do parecer oficial...')}</div>
            
            <div class="assinaturas" style="margin-top: 20px;">
                <table style="border: none; width: 100%;">
                    <tr style="border: none;">
                        <td style="border: none; text-align: center;">
                            <div class="linha-assinatura">Responsável Triagem</div>
                        </td>
                        <td style="border: none; text-align: center;">
                            <div class="linha-assinatura">Comitê de Ética</div>
                        </td>
                    </tr>
                </table>
                <div style="display: flex; justify-content: center; margin-top: 10px;">
                    <div class="linha-assinatura" style="width: 250px;">Diretoria Executiva / Presidência</div>
                </div>
            </div>

            <div class="token-footer">
                <span><b>VALIDAÇÃO (TOKEN):</b> {token_auth}</span>
                <span>Impressão em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</span>
            </div>
        </div>
    </body>
    </html>
    """
    return make_response(conteudo_html)

# ============================================================
# === [EXECUTOR DO APP]                                    ===
# ============================================================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000, use_reloader=False)