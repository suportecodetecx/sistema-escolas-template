"""
Módulo de Configuração e Inicialização - Sistema CodeTecx 2026
Versão com Sindicância, IP e Logs Forenses
"""
import os
import hashlib
import base64
import json
from bson import ObjectId
from datetime import datetime, timedelta, timezone

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    make_response,
    session,
    redirect,
    url_for
)

from flask_wtf.csrf import CSRFProtect, generate_csrf
from cryptography.fernet import Fernet
from pymongo import MongoClient
from werkzeug.utils import secure_filename

# ==========================================
# [CONFIGURAÇÃO DO ENCODER JSON PARA OBJECTID]
# ==========================================
class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)

# --- CONFIGURAÇÃO INICIAL ---
# Fuso horário de Brasília
FUSO_BR = timezone(timedelta(hours=-3))

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = 'chave_seguranca_codetecx_2026'

# Configurar o encoder JSON personalizado
app.json_encoder = JSONEncoder

# --- AJUSTE: SESSÃO PERMANENTE (30 DIAS) ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

@app.before_request
def fazer_sessao_permanente():
    """Define a sessão como permanente."""
    session.permanent = True

# ATIVAÇÃO DA PROTEÇÃO CSRF
csrf = CSRFProtect(app)

# --- CONFIGURAÇÃO MONGODB ---
MONGO_URI = "mongodb+srv://suporte_db_user:2kT3pEb8AcXFWNbk@cluster0.vw8vm8p.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(
    MONGO_URI,
    connectTimeoutMS=30000,
    serverSelectionTimeoutMS=30000,
    tlsAllowInvalidCertificates=True
)

# Banco de dados isolado
db = client['sistema_empresa']
col_config = db['config_admin']

# ============================================================
# === [NOVAS COLEÇÕES] ===
# ============================================================
# Logs forenses (centralizado)
col_logs = db['logs_forenses']

# ============================================================
# === [FUNÇÕES DE IP] ===
# ============================================================
def obter_ip():
    """Captura o IP real do usuário considerando proxies"""
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    else:
        ip = request.remote_addr
    return ip

def criptografar_ip(ip):
    """Criptografa o IP para armazenamento seguro"""
    if not ip:
        return None
    try:
        return cipher_suite.encrypt(ip.encode()).decode()
    except Exception as e:
        print(f"Erro ao criptografar IP: {e}")
        return None

def descriptografar_ip(ip_criptografado):
    """Descriptografa o IP quando necessário (apenas para uso interno)"""
    if not ip_criptografado:
        return None
    try:
        return cipher_suite.decrypt(ip_criptografado.encode()).decode()
    except Exception as e:
        print(f"Erro ao descriptografar IP: {e}")
        return None

def registrar_log_forense(acao, protocolo, usuario, ip_criptografado, empresa_slug=None, detalhes=None):
    """Registra ações em log forense para rastreabilidade"""
    try:
        if empresa_slug is None:
            empresa_slug = session.get('admin_unidade', 'geral')
            
        log_entry = {
            "acao": acao,
            "protocolo": protocolo,
            "usuario": usuario,
            "empresa_slug": empresa_slug,
            "ip": ip_criptografado,
            "data": datetime.now(FUSO_BR).strftime('%d/%m/%Y %H:%M:%S'),
            "detalhes": detalhes or {}
        }
        col_logs.insert_one(log_entry)
        return True
    except Exception as e:
        print(f"Erro ao registrar log: {e}")
        return False

def is_master():
    """Verifica se o usuário é master (suporte_codetecx)"""
    return session.get('admin_user') == 'suporte_codetecx'

# ============================================================
# === [MARCA/CORES] CONFIGURAÇÃO DE WHITE LABEL           ===
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
    "Uniao": {
        "primaria": "#475e93",    
        "secundaria": "#fb923c",  
        "tema": "light"
    },
    "Do-re-mi": {
        "primaria": "#6b69dc",    
        "secundaria": "#fb923c",  
        "tema": "light"
    }
}

# ============================================================
# === [EMPRESAS] CONFIGURAÇÃO MULTI-TENANT                ===
# ============================================================
CONFIG_EMPRESAS = {
    "sol-magico": {
        "nome": "Sol Mágico",
        "unidades": ["Sol Mágico I", "Sol Mágico II"],
        "slug": "sol-magico"
    },
    "lua-nova": {
        "nome": "Lua Nova",
        "unidades": ["Lua Nova I", "Lua Nova II"],
        "slug": "lua-nova"
    },
    "Uniao": {
        "nome": "União",
        "unidades": ["União I", "União II"],
        "slug": "Uniao"
    },
    "Do-re-mi": {
        "nome": "Do Re Mi",
        "unidades": ["Do Re Mi I", "Do Re Mi II"],
        "slug": "Do-re-mi"
    }
}

DOMINIOS_CLIENTES = {
    'uniao.codetecx.com': 'Uniao',
    'sol-magico.codetecx.com': 'sol-magico',
    'lua-nova.codetecx.com': 'lua-nova',
    'sistema-escolas-template.vercel.app': 'sol-magico',
    'localhost': 'sol-magico',
    '127.0.0.1': 'sol-magico',
    'solmagico.com.br': 'sol-magico',
    'luanova.com.br': 'lua-nova',
    'uniaogestao.com.br': 'Uniao',
    'doremi.com.br': 'Do-re-mi'
}

CHAVE_MESTRA = b'U2ZLBCXpcy_pEcsjdgCSxoZbYrbneHPDsSA47mso0xw='
cipher_suite = Fernet(CHAVE_MESTRA)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

# --- CONTEXT PROCESSOR (WHITE LABEL) ---
@app.context_processor
def inject_empresa_context():
    """Injeta contexto da empresa nos templates."""
    slug = request.view_args.get('empresa_slug') if request.view_args else None

    if not slug:
        ref = request.referrer or ""
        for s in CONFIG_EMPRESAS.keys():
            if f"/{s}" in ref:
                slug = s
                break

    if not slug:
        host_limpo = request.host.lower().strip().split(':')[0]
        slug = DOMINIOS_CLIENTES.get(host_limpo)

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

# --- INICIALIZAÇÃO DE SEGURANÇA ---
def inicializar_admin_config():
    """Inicializa configurações de acesso administrativo apenas se não existirem."""
    acessos_mestre = [
        {"user": "suporte_codetecx", "pass": "Code@", "nome": "Suporte Técnico", "unidade": "Geral", "empresa_exibicao": "Codetecx"},
        {"user": "admin", "pass": "2821", "nome": "Direção União", "unidade": "Uniao", "empresa_exibicao": "União"},
        {"user": "uniao2", "pass": "1234", "nome": "Auxiliar União", "unidade": "Uniao", "empresa_exibicao": "União"},
        {"user": "admin2", "pass": "1234", "nome": "Gestão Do Re Mi", "unidade": "Do-re-mi", "empresa_exibicao": "Do Re Mi"},
        {"user": "AdminSol", "pass": "1234", "nome": "Direção Sol Mágico", "unidade": "sol-magico", "empresa_exibicao": "Sol Mágico"},
        {"user": "AdminLua", "pass": "1234", "nome": "Direção Lua Nova", "unidade": "lua-nova", "empresa_exibicao": "Lua Nova"}
    ]

    for credencial in acessos_mestre:
        col_config.update_one(
            {"user": credencial["user"]},
            {"$setOnInsert": credencial},
            upsert=True
        )

# 🔥 DESCOMENTADO: Agora vai criar os usuários!
inicializar_admin_config()

# --- TRAVA DE LICENCIAMENTO POR EMPRESA ---
LICENCAS = {
    "uniao": "2026-12-24",
    "sol-magico": "2026-12-24",
    "lua-nova": "2026-12-24",
    "do-re-mi": "2026-12-24"
}

def verificar_licenca(slug_empresa=None):
    """Verifica se a empresa possui licença ativa para a data atual."""
    try:
        if not slug_empresa:
            slug_empresa = "uniao"
        slug_limpo = str(slug_empresa).lower()
        data_str = LICENCAS.get(slug_limpo)
        if not data_str:
            return False
        data_limite = datetime.strptime(data_str, "%Y-%m-%d")
        agora = datetime.now(FUSO_BR).replace(tzinfo=None)
        return agora <= data_limite
    except Exception:
        return False

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
# [ROTAS DO USUÁRIO]
# ==========================================

@app.route('/')
def home():
    host_limpo = request.host.lower().strip().split(':')[0]
    empresa_slug = DOMINIOS_CLIENTES.get(host_limpo)

    if not empresa_slug:
        empresa_slug = 'Uniao' 

    if not verificar_licenca(empresa_slug):
        return HTML_BLOQUEIO, 403
    
    if empresa_slug in CONFIG_EMPRESAS:
        config = CONFIG_EMPRESAS[empresa_slug]
        cores_atuais = CORES_SISTEMA.get(empresa_slug, CORES_SISTEMA['Uniao'])
        ultimo_visto = request.cookies.get('ultimo_protocolo', 'Nenhum')
        
        return render_template('denuncia.html', 
                                ultimo=ultimo_visto, 
                                nome_sistema=f"Portal {config['nome']}", 
                                unidades=config['unidades'],
                                slug_atual=empresa_slug,
                                cores=cores_atuais)

    return "Por favor, acesse pelo link enviado pela sua instituição (Ex: /sol-magico)", 404

@app.route('/<empresa_slug>')
def home_empresa(empresa_slug):
    if not verificar_licenca(empresa_slug.lower()): 
        return HTML_BLOQUEIO, 403
        
    config = CONFIG_EMPRESAS.get(empresa_slug)
    if not config:
        return "Empresa não encontrada", 404
        
    cores_atuais = CORES_SISTEMA.get(empresa_slug, CORES_SISTEMA.get('Uniao'))
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
    empresa_pela_url = None
    referer = request.referrer or ""
    
    for slug in CONFIG_EMPRESAS.keys():
        if f"/{slug}" in referer:
            empresa_pela_url = slug
            break
    
    if not empresa_pela_url:
        host_limpo = request.host.lower().strip().split(':')[0]
        empresa_pela_url = DOMINIOS_CLIENTES.get(host_limpo, 'sol-magico')
    
    if not verificar_licenca(empresa_pela_url): 
        return jsonify({"status": "Serviço Indisponível"}), 403

    colecao_da_empresa = f'denuncias_{empresa_pela_url}'
    
    if colecao_da_empresa in db.list_collection_names():
        doc = db[colecao_da_empresa].find_one({"protocolo": prot})
        
        if doc:
            status_final = doc.get('status', 'Recebido / Em Triagem')
            parecer_final = doc.get('parecer_comite', 'Aguardando parecer...')
            
            print(f"✅ Encontrado - Status: {status_final}, Parecer: {parecer_final}")
            
            resp = make_response(jsonify({
                "status": status_final,
                "parecer": parecer_final,
                "colecao": colecao_da_empresa,
                "empresa": empresa_pela_url
            }))
            
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            resp.set_cookie('ultimo_protocolo', prot, max_age=60*60*24*7)
            return resp
    
    return jsonify({"status": "Não encontrado", "parecer": ""}), 404

@app.route('/enviar', methods=['POST'])
def enviar():
    try:
        slug = request.form.get('empresa_slug', 'geral')
        
        if not verificar_licenca(slug):
            return jsonify({"status": "erro", "msg": "Licença expirada"}), 403

        col_atual = db[f'denuncias_{slug}']
        
        # 🔥 Captura e criptografa IP do denunciante
        ip_denunciante = obter_ip()
        ip_criptografado = criptografar_ip(ip_denunciante)
        
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
            "ip": ip_criptografado,  # 🔥 NOVO: IP criptografado
            "unidade": request.form.get('unidade'),
            "categoria": request.form.get('categoria'),
            "assunto": request.form.get('titulo'),
            "relato": request.form.get('relato'),
            "anexo": conteudo_anexo_final,
            "email_contato": request.form.get('email_opcional', 'ANÔNIMO'),
            "status": "Recebido / Em Triagem",
            "parecer_comite": "",
            "lida": False  # 🔥 NOVO: Controle de notificações
        }
        
        col_atual.insert_one(nova_denuncia)
        
        # 🔥 Registra log forense
        registrar_log_forense(
            acao="DENUNCIA_ENVIADA",
            protocolo=protocolo,
            usuario="ANONIMO",
            ip_criptografado=ip_criptografado,
            empresa_slug=slug,
            detalhes={"unidade": request.form.get('unidade')}
        )
        
        resp = make_response(jsonify({"status": "sucesso", "protocolo": protocolo}))
        resp.set_cookie('ultimo_protocolo', protocolo, max_age=60*60*24*30)
        return resp
    except Exception as e: 
        print(f"Erro ao enviar denúncia: {e}")
        return jsonify({"status": "erro", "msg": str(e)}), 500

# ==========================================
# [ROTAS DE NOTIFICAÇÕES] - CORRIGIDAS
# ==========================================
@app.route('/api/notificacoes')
def api_notificacoes():
    if not session.get('admin_logado'):
        return jsonify({"erro": "Não autorizado"}), 403
    
    unidade_admin = session.get('admin_unidade')
    
    if unidade_admin == "Geral":
        # Master vê de todas as empresas
        todas_denuncias = []
        total = 0
        for nome_col in db.list_collection_names():
            if nome_col.startswith("denuncias_"):
                denuncias = list(db[nome_col].find(
                    {
                        "status": {"$regex": "Recebido", "$options": "i"},
                        "lida": {"$ne": True}
                    },
                    {'_id': 0, 'protocolo': 1, 'unidade': 1, 'assunto': 1, 'data': 1, 'status': 1}
                ).sort("data", -1).limit(5))
                todas_denuncias.extend(denuncias)
                total += db[nome_col].count_documents({
                    "status": {"$regex": "Recebido", "$options": "i"},
                    "lida": {"$ne": True}
                })
        
        # Ordena por data
        todas_denuncias.sort(key=lambda x: x.get('data', ''), reverse=True)
        denuncias = todas_denuncias[:5]
    else:
        colecao = f'denuncias_{unidade_admin}'
        denuncias = list(db[colecao].find(
            {
                "status": {"$regex": "Recebido", "$options": "i"},
                "lida": {"$ne": True}
            },
            {'_id': 0, 'protocolo': 1, 'unidade': 1, 'assunto': 1, 'data': 1, 'status': 1}
        ).sort("data", -1).limit(5))
        
        total = db[colecao].count_documents({
            "status": {"$regex": "Recebido", "$options": "i"},
            "lida": {"$ne": True}
        })
    
    return jsonify({
        "denuncias": denuncias,
        "total": total
    })

@app.route('/api/marcar-notificacao/<protocolo>', methods=['POST'])
def marcar_notificacao(protocolo):
    if not session.get('admin_logado'):
        return jsonify({"erro": "Não autorizado"}), 403
    
    unidade_admin = session.get('admin_unidade')
    
    if unidade_admin == "Geral":
        # Master - procura em todas as coleções
        for nome_col in db.list_collection_names():
            if nome_col.startswith("denuncias_"):
                db[nome_col].update_one(
                    {"protocolo": protocolo},
                    {"$set": {"lida": True}}
                )
    else:
        colecao = f'denuncias_{unidade_admin}'
        db[colecao].update_one(
            {"protocolo": protocolo},
            {"$set": {"lida": True}}
        )
    
    return jsonify({"status": "ok"})

@app.route('/api/marcar-todas-notificacoes', methods=['POST'])
def marcar_todas_notificacoes():
    if not session.get('admin_logado'):
        return jsonify({"erro": "Não autorizado"}), 403
    
    unidade_admin = session.get('admin_unidade')
    
    if unidade_admin == "Geral":
        # Master - marca todas de todas as empresas
        for nome_col in db.list_collection_names():
            if nome_col.startswith("denuncias_"):
                db[nome_col].update_many(
                    {
                        "status": {"$regex": "Recebido", "$options": "i"},
                        "lida": {"$ne": True}
                    },
                    {"$set": {"lida": True}}
                )
    else:
        colecao = f'denuncias_{unidade_admin}'
        db[colecao].update_many(
            {
                "status": {"$regex": "Recebido", "$options": "i"},
                "lida": {"$ne": True}
            },
            {"$set": {"lida": True}}
        )
    
    return jsonify({"status": "ok"})

@app.route('/api/notificacoes/contador')
def api_notificacoes_contador():
    if not session.get('admin_logado'):
        return jsonify({"erro": "Não autorizado"}), 403
    
    unidade_admin = session.get('admin_unidade')
    
    if unidade_admin == "Geral":
        total = 0
        for nome_col in db.list_collection_names():
            if nome_col.startswith("denuncias_"):
                total += db[nome_col].count_documents({
                    "status": {"$regex": "Recebido", "$options": "i"},
                    "lida": {"$ne": True}
                })
    else:
        colecao = f'denuncias_{unidade_admin}'
        total = db[colecao].count_documents({
            "status": {"$regex": "Recebido", "$options": "i"},
            "lida": {"$ne": True}
        })
    
    return jsonify({"total": total})

# ==========================================
# [GESTÃO E DASHBOARD]
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logado'): 
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        usuario_digitado = request.form.get('user')
        senha_digitada = request.form.get('pass')
        
        # 🔥 Captura IP do admin
        ip_admin = obter_ip()
        ip_criptografado = criptografar_ip(ip_admin)
        
        host_limpo = request.host.lower().strip().split(':')[0]
        slug_da_pagina_atual = DOMINIOS_CLIENTES.get(host_limpo)

        user_no_banco = col_config.find_one({"user": usuario_digitado})

        if user_no_banco and str(user_no_banco.get('pass')) == str(senha_digitada):
            unidade_do_user = user_no_banco.get('unidade')
            
            if unidade_do_user != "Geral" and unidade_do_user != slug_da_pagina_atual:
                registrar_log_forense(
                    acao="LOGIN_NEGADO",
                    protocolo=None,
                    usuario=usuario_digitado,
                    ip_criptografado=ip_criptografado,
                    empresa_slug=slug_da_pagina_atual,
                    detalhes={"motivo": "unidade_incorreta"}
                )
                return render_template('login.html', erro="Acesso negado: Este usuário não pertence a esta instituição.")

            session.clear()
            empresa_nome = user_no_banco.get('empresa_exibicao', 'Sistema')
            
            session.update({
                'admin_logado': True,
                'admin_user': user_no_banco.get('user'),
                'admin_nome': user_no_banco.get('nome', 'Administrador'),
                'admin_unidade': unidade_do_user,
                'admin_empresa_nome': empresa_nome
            })
            
            registrar_log_forense(
                acao="LOGIN_SUCESSO",
                protocolo=None,
                usuario=usuario_digitado,
                ip_criptografado=ip_criptografado,
                empresa_slug=unidade_do_user if unidade_do_user != "Geral" else None
            )
            
            return redirect(url_for('dashboard'))
        
        registrar_log_forense(
            acao="LOGIN_FALHA",
            protocolo=None,
            usuario=usuario_digitado,
            ip_criptografado=ip_criptografado,
            empresa_slug=slug_da_pagina_atual
        )
        
        return render_template('login.html', erro="Usuário ou senha incorretos")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    if session.get('admin_logado'):
        ip_admin = obter_ip()
        ip_criptografado = criptografar_ip(ip_admin)
        registrar_log_forense(
            acao="LOGOUT",
            protocolo=None,
            usuario=session.get('admin_nome'),
            ip_criptografado=ip_criptografado,
            empresa_slug=session.get('admin_unidade')
        )
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
                slug_empresa = nome_col.replace("denuncias_", "")
                for item in itens:
                    item['colecao_origem'] = nome_col
                    item['empresa_slug'] = slug_empresa
                    
                    # 🔥 Busca status da sindicância
                    col_sind = db[f'sindicancias_{slug_empresa}']
                    sind = col_sind.find_one({"protocolo": item['protocolo']}, {'status': 1})
                    item['sindicancia_status'] = sind.get('status') if sind else None
                    
                denuncias.extend(itens)
        denuncias.sort(key=lambda x: x.get('data', ''), reverse=True)
    else:
        nome_colecao = f'denuncias_{unidade_admin}'
        denuncias = list(db[nome_colecao].find({}, {'_id': 0}).sort("data", -1))
        
        # 🔥 Busca status da sindicância
        col_sind = db[f'sindicancias_{unidade_admin}']
        for d in denuncias:
            d['colecao_origem'] = nome_colecao
            sind = col_sind.find_one({"protocolo": d['protocolo']}, {'status': 1})
            d['sindicancia_status'] = sind.get('status') if sind else None

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

    # 🔥 Captura IP do admin
    ip_admin = obter_ip()
    ip_criptografado = criptografar_ip(ip_admin)

    if not colecao_alvo:
        unidade_admin = session.get('admin_unidade')
        colecao_alvo = f'denuncias_{unidade_admin}'

    db[colecao_alvo].update_one(
        {"protocolo": prot},
        {"$set": {
            "status": novo_status, 
            "parecer_comite": novo_parecer,
            "data_atualizacao": datetime.now().strftime('%d/%m/%Y %H:%M'),
            "ultimo_ip": ip_criptografado,
            "ultimo_usuario": session.get('admin_nome')
        }}
    )
    
    # 🔥 Registra log
    slug_empresa = colecao_alvo.replace("denuncias_", "")
    registrar_log_forense(
        acao="DENUNCIA_ATUALIZADA",
        protocolo=prot,
        usuario=session.get('admin_nome'),
        ip_criptografado=ip_criptografado,
        empresa_slug=slug_empresa,
        detalhes={"novo_status": novo_status}
    )
    
    return redirect(url_for('dashboard'))

# ==========================================
# [SISTEMA DE SINDICÂNCIA]
# ==========================================

@app.route('/sindicancia/<protocolo>')
def pagina_sindicancia(protocolo):
    if not session.get('admin_logado'):
        return redirect(url_for('login'))
    
    unidade_admin = session.get('admin_unidade')
    
    # Busca a denúncia
    if unidade_admin == "Geral":
        # Master - precisa encontrar em qual coleção está
        denuncia = None
        for nome_col in db.list_collection_names():
            if nome_col.startswith("denuncias_"):
                denuncia = db[nome_col].find_one({"protocolo": protocolo}, {'_id': 0})
                if denuncia:
                    slug_empresa = nome_col.replace("denuncias_", "")
                    denuncia['empresa_slug'] = slug_empresa
                    break
    else:
        colecao = f'denuncias_{unidade_admin}'
        denuncia = db[colecao].find_one({"protocolo": protocolo}, {'_id': 0})
        if denuncia:
            denuncia['empresa_slug'] = unidade_admin
    
    if not denuncia:
        return "Protocolo não encontrado", 404
    
    return render_template('sindicancia.html',
                          denuncia=denuncia,
                          csrf_token=generate_csrf())

# ==========================================
# [APIs da Sindicância]
# ==========================================

@app.route('/api/sindicancia/<protocolo>')
def api_get_sindicancia(protocolo):
    if not session.get('admin_logado'):
        return jsonify({"erro": "Não autorizado"}), 403
    
    unidade_admin = session.get('admin_unidade')
    
    if unidade_admin == "Geral":
        # Master - procura em todas as coleções
        for nome_col in db.list_collection_names():
            if nome_col.startswith("sindicancias_"):
                sindicancia = db[nome_col].find_one({"protocolo": protocolo}, {'_id': 0})
                if sindicancia:
                    return jsonify({"existe": True, "sindicancia": sindicancia})
        return jsonify({"existe": False})
    else:
        colecao = f'sindicancias_{unidade_admin}'
        sindicancia = db[colecao].find_one({"protocolo": protocolo}, {'_id': 0})
        if sindicancia:
            return jsonify({"existe": True, "sindicancia": sindicancia})
        return jsonify({"existe": False})

@app.route('/api/sindicancia/instaurar', methods=['POST'])
def api_instaurar_sindicancia():
    if not session.get('admin_logado'):
        return jsonify({"erro": "Não autorizado"}), 403
    
    data = request.json
    protocolo = data.get('protocolo')
    
    ip_admin = obter_ip()
    ip_criptografado = criptografar_ip(ip_admin)
    
    if not protocolo:
        return jsonify({"erro": "Protocolo não informado"}), 400
    
    unidade_admin = session.get('admin_unidade')
    
    if unidade_admin == "Geral":
        # Precisa descobrir de qual empresa é o protocolo
        slug_empresa = None
        for nome_col in db.list_collection_names():
            if nome_col.startswith("denuncias_"):
                denuncia = db[nome_col].find_one({"protocolo": protocolo})
                if denuncia:
                    slug_empresa = nome_col.replace("denuncias_", "")
                    break
        if not slug_empresa:
            return jsonify({"erro": "Denúncia não encontrada"}), 404
        colecao_sind = f'sindicancias_{slug_empresa}'
    else:
        slug_empresa = unidade_admin
        colecao_sind = f'sindicancias_{unidade_admin}'
    
    # Verifica se já existe sindicância
    existe = db[colecao_sind].find_one({"protocolo": protocolo})
    if existe:
        return jsonify({"erro": "Sindicância já existe"}), 400
    
    nova_sindicancia = {
        "protocolo": protocolo,
        "empresa_slug": slug_empresa,
        "data_instauracao": datetime.now(FUSO_BR).strftime('%d/%m/%Y'),
        "instaurado_por": session.get('admin_nome', 'Admin'),
        "instaurado_ip": ip_criptografado,
        "prazo_limite": (datetime.now(FUSO_BR) + timedelta(days=30)).strftime('%d/%m/%Y'),
        "comissao": [],
        "diligencias": [],
        "provas": [],
        "relatorio_final": "",
        "tipo_sindicancia": "investigativa",
        "conclusao": "",
        "data_conclusao": "",
        "status": "em_andamento",
        "criado_em": datetime.now(FUSO_BR).strftime('%d/%m/%Y %H:%M:%S'),
        "criado_por": session.get('admin_nome', 'Admin')
    }
    
    db[colecao_sind].insert_one(nova_sindicancia)
    
    registrar_log_forense(
        acao="SINDICANCIA_INSTAURADA",
        protocolo=protocolo,
        usuario=session.get('admin_nome'),
        ip_criptografado=ip_criptografado,
        empresa_slug=slug_empresa
    )
    
    return jsonify({"status": "ok", "sindicancia": nova_sindicancia})

# ==========================================
# [AS DEMAIS ROTAS DA SINDICÂNCIA CONTINUAM IGUAIS]
# ==========================================
# (mantenha todas as outras rotas de sindicância que você já tem)

# ==========================================
# [ROTA PARA ANEXO DA DENÚNCIA]
# ==========================================
@app.route('/anexo/<protocolo>')
def visualizar_anexo_denuncia(protocolo):
    if not session.get('admin_logado'):
        return redirect(url_for('login'))
    
    ip_admin = obter_ip()
    ip_criptografado = criptografar_ip(ip_admin)
    
    unidade_admin = session.get('admin_unidade')
    
    if unidade_admin == "Geral":
        denuncia = None
        slug_empresa = None
        for nome_col in db.list_collection_names():
            if nome_col.startswith("denuncias_"):
                denuncia = db[nome_col].find_one({"protocolo": protocolo})
                if denuncia:
                    slug_empresa = nome_col.replace("denuncias_", "")
                    break
        if not denuncia:
            return "Denúncia não encontrada", 404
    else:
        colecao = f'denuncias_{unidade_admin}'
        denuncia = db[colecao].find_one({"protocolo": protocolo})
        slug_empresa = unidade_admin
        if not denuncia:
            return "Denúncia não encontrada", 404
    
    anexo = denuncia.get('anexo', '')
    if not anexo or anexo == 'None' or anexo == 'Nenhum':
        return "Anexo não encontrado", 404
    
    registrar_log_forense(
        acao="ANEXO_VISUALIZADO",
        protocolo=protocolo,
        usuario=session.get('admin_nome'),
        ip_criptografado=ip_criptografado,
        empresa_slug=slug_empresa
    )
    
    if anexo.startswith('data:'):
        partes = anexo.split(',', 1)
        if len(partes) > 1:
            cabecalho = partes[0]
            conteudo = partes[1]
            
            mime_type = 'application/octet-stream'
            if ';' in cabecalho:
                tipo_parts = cabecalho.split(';')[0]
                if ':' in tipo_parts:
                    mime_type = tipo_parts.split(':')[1]
        else:
            conteudo = anexo
    else:
        conteudo = anexo
        mime_type = 'application/octet-stream'
    
    try:
        dados = base64.b64decode(conteudo)
        filename = f"anexo_{protocolo}"
        if mime_type.startswith('image/'):
            ext = mime_type.split('/')[1]
            filename = f"anexo_{protocolo}.{ext}"
        
        response = make_response(dados)
        response.headers.set('Content-Type', mime_type)
        response.headers.set('Content-Disposition', f'inline; filename="{filename}"')
        return response
    except Exception as e:
        print(f"Erro ao carregar anexo: {e}")
        return "Erro ao carregar anexo", 500

# ==========================================
# [ROTA DE CONSULTA DE IP - APENAS MASTER]
# ==========================================
@app.route('/api/consulta-ip/<protocolo>')
def consultar_ip_denuncia(protocolo):
    if not session.get('admin_logado'):
        return jsonify({"erro": "Não autorizado"}), 403
    
    # Apenas master pode ver IPs
    if not is_master():
        return jsonify({"erro": "Acesso restrito ao desenvolvedor"}), 403
    
    # Master vê em todas as coleções
    denuncia = None
    slug_empresa = None
    for nome_col in db.list_collection_names():
        if nome_col.startswith("denuncias_"):
            denuncia = db[nome_col].find_one({"protocolo": protocolo})
            if denuncia:
                slug_empresa = nome_col.replace("denuncias_", "")
                break
    
    if not denuncia:
        return jsonify({"erro": "Denúncia não encontrada"}), 404
    
    ip_criptografado = denuncia.get('ip')
    if not ip_criptografado:
        return jsonify({"ip": "Não registrado"})
    
    ip_real = descriptografar_ip(ip_criptografado)
    
    # Busca logs relacionados
    logs = list(col_logs.find({"protocolo": protocolo}, {'_id': 0}).sort("data", -1).limit(10))
    
    return jsonify({
        "protocolo": protocolo,
        "ip_denunciante": ip_real,
        "data_denuncia": denuncia.get('data'),
        "empresa": slug_empresa,
        "logs_acao": logs,
        "consulta_realizada_em": datetime.now(FUSO_BR).strftime('%d/%m/%Y %H:%M:%S')
    })

# ==========================================
# [DOSSIÊ DE SINDICÂNCIA]
# ==========================================
@app.route('/gestao/sindicancia/<protocolo>')
def dossie_sindicancia(protocolo):
    if not session.get('admin_logado'): 
        return redirect(url_for('login'))
    
    unidade_admin = session.get('admin_unidade')
    
    if unidade_admin == "Geral":
        sindicancia = None
        denuncia = None
        for nome_col in db.list_collection_names():
            if nome_col.startswith("sindicancias_"):
                sindicancia = db[nome_col].find_one({"protocolo": protocolo}, {'_id': 0})
                if sindicancia:
                    slug_empresa = nome_col.replace("sindicancias_", "")
                    break
        if not sindicancia:
            return "Sindicância não encontrada", 404
        # Busca denúncia correspondente
        denuncia = db[f'denuncias_{slug_empresa}'].find_one({"protocolo": protocolo}, {'_id': 0})
    else:
        colecao_sind = f'sindicancias_{unidade_admin}'
        colecao_den = f'denuncias_{unidade_admin}'
        sindicancia = db[colecao_sind].find_one({"protocolo": protocolo}, {'_id': 0})
        denuncia = db[colecao_den].find_one({"protocolo": protocolo}, {'_id': 0})
        if not sindicancia:
            return "Sindicância não encontrada", 404
    
    if not denuncia:
        return "Denúncia não encontrada", 404
    
    # Dados para o template
    data_impressao = datetime.now(FUSO_BR).strftime('%d/%m/%Y %H:%M:%S')
    usuario = session.get('admin_nome', 'Sistema')
    
    # Token de autenticidade
    token = hashlib.md5(f"{protocolo}{data_impressao}{usuario}".encode()).hexdigest().upper()[:20]
    
    # Formata a comissão
    comissao_html = ""
    if sindicancia.get('comissao') and len(sindicancia['comissao']) > 0:
        for membro in sindicancia['comissao']:
            comissao_html += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">{membro.get('nome', '')}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{membro.get('funcao', '')}</td>
            </tr>
            """
    else:
        comissao_html = "<tr><td colspan='2' style='padding: 8px; border: 1px solid #ddd; text-align: center;'>Nenhum membro designado</td></tr>"
    
    # Formata as diligências
    diligencias_html = ""
    if sindicancia.get('diligencias') and len(sindicancia['diligencias']) > 0:
        for i, diligencia in enumerate(sindicancia['diligencias'], 1):
            data_diligencia = diligencia.get('data', '')
            if data_diligencia and len(data_diligencia) == 10 and data_diligencia.count('-') == 2:
                partes = data_diligencia.split('-')
                data_diligencia = f"{partes[2]}/{partes[1]}/{partes[0]}"
            
            diligencias_html += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; width: 10%;">{i}</td>
                <td style="padding: 8px; border: 1px solid #ddd; width: 15%;">{data_diligencia}</td>
                <td style="padding: 8px; border: 1px solid #ddd; width: 25%;"><strong>{diligencia.get('titulo', '')}</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd; width: 40%;">{diligencia.get('descricao', '')}</td>
                <td style="padding: 8px; border: 1px solid #ddd; width: 10%;">{diligencia.get('registrado_por', '')}</td>
            </tr>
            """
    else:
        diligencias_html = "<tr><td colspan='5' style='padding: 8px; border: 1px solid #ddd; text-align: center;'>Nenhuma diligência registrada</td></tr>"
    
    # Formata as provas anexadas
    provas_html = ""
    if sindicancia.get('provas') and len(sindicancia['provas']) > 0:
        for i, prova in enumerate(sindicancia['provas'], 1):
            provas_html += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; width: 10%;">{i}</td>
                <td style="padding: 8px; border: 1px solid #ddd; width: 30%;">{prova.get('nome', '')}</td>
                <td style="padding: 8px; border: 1px solid #ddd; width: 25%;">{prova.get('descricao', '')}</td>
                <td style="padding: 8px; border: 1px solid #ddd; width: 20%;">{prova.get('tipo', 'documento')}</td>
                <td style="padding: 8px; border: 1px solid #ddd; width: 15%;">{prova.get('data_anexo', '')}</td>
            </tr>
            """
    else:
        provas_html = "<tr><td colspan='5' style='padding: 8px; border: 1px solid #ddd; text-align: center;'>Nenhuma prova anexada</td></tr>"
    
    # Conclusão formatada
    tipo_sindicancia_texto = {
        'investigativa': 'Investigativa (SINVE) - Autoria desconhecida',
        'punitiva': 'Acusatória/Punitiva (SINAC) - Autor identificado',
        'patrimonial': 'Patrimonial (SINPA) - Enriquecimento ilícito'
    }.get(sindicancia.get('tipo_sindicancia', ''), sindicancia.get('tipo_sindicancia', 'Não definido'))
    
    conclusao_texto = {
        'arquivar_improcedente': 'Arquivamento por improcedência (sem culpa)',
        'arquivar_autoria': 'Arquivamento por não identificação de autoria',
        'arquivar_prescricao': 'Arquivamento por prescrição',
        'advertencia': 'Advertência (Art. 129 da Lei 8.112/90)',
        'suspensao_10': 'Suspensão - até 10 dias',
        'suspensao_20': 'Suspensão - 11 a 20 dias',
        'suspensao_30': 'Suspensão - 21 a 30 dias',
        'pad': 'Instauração de Processo Administrativo Disciplinar (PAD)',
        'sindicancia_patrimonial': 'Conversão em Sindicância Patrimonial',
        'encaminhamento_mp': 'Encaminhamento ao Ministério Público',
        'encaminhamento_tc': 'Encaminhamento ao Tribunal de Contas'
    }.get(sindicancia.get('conclusao', ''), sindicancia.get('conclusao', 'Não definida'))
    
    # Template HTML profissional para o dossiê
    html = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <title>Dossiê de Sindicância - {protocolo}</title>
        <style>
            @page {{
                size: A4;
                margin: 2.5cm 2cm 2cm 2cm;
                @top-center {{
                    content: "PROCEDIMENTO DE SINDICÂNCIA";
                    font-size: 9pt;
                    color: #666;
                }}
                @bottom-center {{
                    content: "Página " counter(page) " de " counter(pages);
                    font-size: 9pt;
                    color: #666;
                }}
            }}
            
            * {{
                box-sizing: border-box;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            
            body {{
                font-family: 'Times New Roman', Times, serif;
                line-height: 1.5;
                color: #000;
                background: #fff;
                margin: 0;
                padding: 0;
            }}
            
            .container {{
                max-width: 100%;
                margin: 0 auto;
            }}
            
            .header {{
                text-align: center;
                margin-bottom: 30px;
                border-bottom: 2px solid #000;
                padding-bottom: 15px;
            }}
            
            .header h1 {{
                font-size: 18pt;
                font-weight: bold;
                text-transform: uppercase;
                margin: 0 0 5px 0;
                letter-spacing: 1px;
            }}
            
            .header h2 {{
                font-size: 14pt;
                font-weight: normal;
                margin: 0 0 10px 0;
            }}
            
            .header .protocolo {{
                font-size: 12pt;
                font-family: monospace;
                background: #f0f0f0;
                padding: 5px 10px;
                display: inline-block;
                border-radius: 4px;
            }}
            
            .confidencial {{
                background: #000;
                color: #fff;
                text-align: center;
                padding: 5px;
                font-size: 10pt;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 2px;
                margin-bottom: 20px;
            }}
            
            .section {{
                margin-bottom: 25px;
            }}
            
            .section-title {{
                font-size: 13pt;
                font-weight: bold;
                text-transform: uppercase;
                border-bottom: 1px solid #000;
                padding-bottom: 5px;
                margin-bottom: 15px;
                background: #f5f5f5;
                padding: 8px 10px;
            }}
            
            .subsection-title {{
                font-size: 12pt;
                font-weight: bold;
                margin: 15px 0 10px 0;
                border-left: 4px solid #666;
                padding-left: 10px;
            }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
                font-size: 11pt;
            }}
            
            th {{
                background: #e0e0e0;
                font-weight: bold;
                padding: 8px;
                border: 1px solid #000;
                text-align: center;
            }}
            
            td {{
                padding: 8px;
                border: 1px solid #000;
                vertical-align: top;
            }}
            
            .info-table td:first-child {{
                width: 30%;
                background: #f5f5f5;
                font-weight: bold;
            }}
            
            .info-table td:last-child {{
                width: 70%;
            }}
            
            .text-box {{
                border: 1px solid #000;
                padding: 15px;
                min-height: 100px;
                background: #fafafa;
                font-style: italic;
                white-space: pre-wrap;
            }}
            
            .signature {{
                margin-top: 40px;
                display: flex;
                justify-content: space-between;
            }}
            
            .signature-line {{
                border-top: 1px solid #000;
                width: 250px;
                margin: 40px auto 5px;
                text-align: center;
            }}
            
            .signature-text {{
                text-align: center;
                font-size: 10pt;
                font-weight: bold;
                text-transform: uppercase;
            }}
            
            .footer {{
                margin-top: 40px;
                font-size: 9pt;
                color: #666;
                border-top: 1px dashed #ccc;
                padding-top: 10px;
                display: flex;
                justify-content: space-between;
            }}
            
            .token {{
                font-family: monospace;
                font-size: 8pt;
                color: #333;
                background: #f0f0f0;
                padding: 3px 8px;
                border-radius: 3px;
            }}
            
            .status-badge {{
                display: inline-block;
                padding: 3px 10px;
                border-radius: 20px;
                font-size: 10pt;
                font-weight: bold;
                text-transform: uppercase;
            }}
            
            .status-andamento {{
                background: #fff3cd;
                color: #856404;
                border: 1px solid #ffeeba;
            }}
            
            .status-concluida {{
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }}
            
            .anexo-img {{
                max-width: 100%;
                max-height: 400px;
                display: block;
                margin: 10px auto;
                border: 1px solid #ccc;
            }}
            
            @media print {{
                .no-print {{
                    display: none;
                }}
                body {{
                    background: white;
                }}
            }}
            
            .btn-print {{
                position: fixed;
                top: 20px;
                right: 20px;
                background: #2563eb;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                cursor: pointer;
                font-weight: bold;
                z-index: 1000;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .btn-print:hover {{
                background: #1e40af;
            }}
        </style>
    </head>
    <body>
        <button class="btn-print no-print" onclick="window.print()">🖨️ IMPRIMIR / GERAR PDF</button>
        
        <div class="container">
            <div class="confidencial">DOCUMENTO ESTRITAMENTE CONFIDENCIAL - LEI 14.457/2022</div>
            
            <div class="header">
                <h1>PROCESSO DE SINDICÂNCIA ADMINISTRATIVA</h1>
                <h2>COMISSÃO DE ÉTICA E INTEGRIDADE</h2>
                <p class="protocolo">Protocolo: <strong>{protocolo}</strong></p>
                <p>Data de emissão: {data_impressao}</p>
                <p>Status: <span class="status-badge {'status-concluida' if sindicancia.get('status') == 'concluida' else 'status-andamento'}">{'CONCLUÍDA' if sindicancia.get('status') == 'concluida' else 'EM ANDAMENTO'}</span></p>
                <p>Tipo: <strong>{tipo_sindicancia_texto}</strong></p>
            </div>
            
            <!-- SEÇÃO 1: INFORMAÇÕES GERAIS -->
            <div class="section">
                <div class="section-title">1. INFORMAÇÕES GERAIS</div>
                <table class="info-table">
                    <tr>
                        <td>Data de Instauração:</td>
                        <td>{sindicancia.get('data_instauracao', denuncia.get('data', 'NÃO INFORMADA'))}</td>
                    </tr>
                    <tr>
                        <td>Instaurado por:</td>
                        <td>{sindicancia.get('instaurado_por', 'NÃO INFORMADO')}</td>
                    </tr>
                    <tr>
                        <td>Prazo Legal (30 dias):</td>
                        <td>{sindicancia.get('prazo_limite', 'NÃO DEFINIDO')}</td>
                    </tr>
                    <tr>
                        <td>Unidade de Origem:</td>
                        <td>{denuncia.get('unidade', 'NÃO INFORMADA')}</td>
                    </tr>
                    <tr>
                        <td>Categoria da Denúncia:</td>
                        <td>{denuncia.get('categoria', 'NÃO INFORMADA')}</td>
                    </tr>
                    <tr>
                        <td>Assunto:</td>
                        <td>{denuncia.get('assunto', 'NÃO INFORMADO')}</td>
                    </tr>
                </table>
            </div>
            
            <!-- SEÇÃO 2: COMISSÃO PROCESSANTE -->
            <div class="section">
                <div class="section-title">2. COMISSÃO PROCESSANTE</div>
                <table>
                    <thead>
                        <tr>
                            <th>NOME</th>
                            <th>FUNÇÃO</th>
                        </tr>
                    </thead>
                    <tbody>
                        {comissao_html}
                    </tbody>
                </table>
            </div>
            
            <!-- SEÇÃO 3: DENÚNCIA ORIGINAL -->
            <div class="section">
                <div class="section-title">3. DENÚNCIA ORIGINAL</div>
                <div class="text-box">{denuncia.get('relato', 'NÃO INFORMADO')}</div>
            </div>
            
            <!-- SEÇÃO 4: ANEXOS DA DENÚNCIA -->
            <div class="section">
                <div class="section-title">4. ANEXOS DA DENÚNCIA</div>
                <div class="text-box">
                    {f'<img src="{denuncia["anexo"]}" class="anexo-img" alt="Anexo da denúncia">' if denuncia.get('anexo') and denuncia['anexo'] != 'Nenhum' else 'Nenhum anexo enviado na denúncia original.'}
                </div>
            </div>
            
            <!-- SEÇÃO 5: DILIGÊNCIAS REALIZADAS -->
            <div class="section">
                <div class="section-title">5. DILIGÊNCIAS REALIZADAS</div>
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>DATA</th>
                            <th>TÍTULO</th>
                            <th>DESCRIÇÃO</th>
                            <th>RESPONSÁVEL</th>
                        </tr>
                    </thead>
                    <tbody>
                        {diligencias_html}
                    </tbody>
                </table>
            </div>
            
            <!-- SEÇÃO 6: PROVAS E DOCUMENTOS ANEXADOS -->
            <div class="section">
                <div class="section-title">6. PROVAS E DOCUMENTOS ANEXADOS</div>
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>ARQUIVO</th>
                            <th>DESCRIÇÃO</th>
                            <th>TIPO</th>
                            <th>DATA ANEXO</th>
                        </tr>
                    </thead>
                    <tbody>
                        {provas_html}
                    </tbody>
                </table>
                <p style="font-size: 9pt; margin-top: 10px;"><em>Nota: Os arquivos originais estão disponíveis no sistema para consulta.</em></p>
            </div>
            
            <!-- SEÇÃO 7: RELATÓRIO FINAL -->
            <div class="section">
                <div class="section-title">7. RELATÓRIO FINAL E PARECER</div>
                <div class="text-box">{sindicancia.get('relatorio_final', 'Relatório ainda não elaborado.')}</div>
            </div>
            
            <!-- SEÇÃO 8: CONCLUSÃO -->
            <div class="section">
                <div class="section-title">8. CONCLUSÃO</div>
                <table class="info-table">
                    <tr>
                        <td>Decisão:</td>
                        <td><strong>{conclusao_texto}</strong></td>
                    </tr>
                    <tr>
                        <td>Data da Conclusão:</td>
                        <td>{sindicancia.get('data_conclusao', 'NÃO FINALIZADO')}</td>
                    </tr>
                    <tr>
                        <td>Prazo Final:</td>
                        <td>{sindicancia.get('prazo_final', 'NÃO DEFINIDO')}</td>
                    </tr>
                </table>
            </div>
            
            <!-- SEÇÃO 9: ASSINATURAS -->
            <div class="section">
                <div class="section-title">9. ASSINATURAS</div>
                <div class="signature">
                    <div>
                        <div class="signature-line"></div>
                        <div class="signature-text">PRESIDENTE DA COMISSÃO</div>
                    </div>
                    <div>
                        <div class="signature-line"></div>
                        <div class="signature-text">MEMBRO</div>
                    </div>
                </div>
                <div style="text-align: center; margin-top: 30px;">
                    <div style="border-top: 1px solid #000; width: 350px; margin: 0 auto;"></div>
                    <div class="signature-text">DIRETORIA</div>
                </div>
            </div>
            
            <!-- RODAPÉ COM TOKEN DE AUTENTICIDADE -->
            <div class="footer">
                <div>Documento gerado eletronicamente em {data_impressao} por {usuario}</div>
                <div class="token">Token: {token}</div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return make_response(html)

# ✅ AJUSTE 4: Porta voltou para 8000
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)