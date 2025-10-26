import os
import sqlite3
from flask import Flask, jsonify, request, g
from flask_cors import CORS
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

app = Flask(__name__)

# ========================================
# CONFIGURAÇÃO DE CORS CORRIGIDA
# ========================================
CORS(app, resources={
    r"/*": {
        "origins": "https://75895.github.io",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

DATABASE = 'restaurante.db'

# ========================================
# FUNÇÕES DE CONEXÃO COM O BANCO DE DADOS
# ========================================
def get_db_connection():
    """Retorna conexão com o banco de dados (SQLite local ou PostgreSQL no Render)"""
    db = getattr(g, '_database', None)
    if db is None:
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # Produção: PostgreSQL
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
            # Para PostgreSQL, usamos cursor_factory em vez de row_factory
            db = g._database = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        else:
            # Desenvolvimento: SQLite
            db = g._database = sqlite3.connect(DATABASE)
            db.row_factory = sqlite3.Row
    
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# =================================================================
# FUNÇÃO CRÍTICA: INICIALIZAÇÃO DO DB
# =================================================================
def init_db():
    """Inicializa o banco de dados com o schema, adaptado para PostgreSQL e SQLite."""
    with app.app_context():
        db = get_db_connection()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        with app.open_resource('schema.sql', mode='r') as f:
            sql_script = f.read()

        try:
            cursor = db.cursor()
            
            if is_postgres:
                # PostgreSQL usa cursor.execute() para executar o bloco inteiro
                cursor.execute(sql_script)
            else:
                # SQLite usa executescript() na conexão (db)
                db.executescript(sql_script) 
                
            db.commit()
            return True
            
        except Exception as e:
            db.rollback() 
            raise e 

@app.route('/init_db')
def initialize_db_route():
    try:
        init_db()
        return jsonify({'message': 'Banco de dados inicializado com sucesso!'}), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao inicializar o banco de dados: {e}'}), 500

# ========================================
# ROTAS DE AUTENTICAÇÃO
# ========================================

@app.route('/login', methods=['POST'])
def login():
    """Rota para autenticação de usuários"""
    try:
        data = request.get_json()
        
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({
                'success': False,
                'message': 'Nome de usuário e senha são obrigatórios.'
            }), 400
        
        username = data['username'].strip()
        password = data['password']
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': 'Nome de usuário e senha não podem estar vazios.'
            }), 400
        
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "SELECT id, username, password_hash FROM usuarios WHERE username = %s" if os.environ.get('DATABASE_URL') else "SELECT id, username, password_hash FROM usuarios WHERE username = ?",
            (username,)
        )
        usuario = cursor.fetchone()
        
        if not usuario:
            return jsonify({
                'success': False,
                'message': 'Usuário ou senha incorretos.'
            }), 401
        
        # Converte para dict se for necessário (RealDictCursor já retorna dict)
        if hasattr(usuario, '_asdict'):
            usuario = dict(usuario)
        elif not isinstance(usuario, dict) and hasattr(usuario, 'keys'):
            usuario = dict(usuario)

        
        password_hash_armazenado = usuario['password_hash'].encode('utf-8')
        password_fornecida = password.encode('utf-8')
        
        if bcrypt.checkpw(password_fornecida, password_hash_armazenado):
            return jsonify({
                'success': True,
                'message': 'Login realizado com sucesso!',
                'user': {
                    'id': usuario['id'],
                    'username': usuario['username']
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Usuário ou senha incorretos.'
            }), 401
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro no servidor: {str(e)}'
        }), 500

@app.route('/verificar_usuarios', methods=['GET'])
def verificar_usuarios():
    """Rota auxiliar para verificar usuários cadastrados"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM usuarios")
        resultado = cursor.fetchone()
        
        if isinstance(resultado, dict) or (resultado and hasattr(resultado, 'keys')):
            total_usuarios = resultado['total']
        else:
            total_usuarios = resultado[0] if resultado else 0
        
        cursor.execute("SELECT id, username, data_criacao FROM usuarios")
        usuarios = cursor.fetchall()
        
        usuarios_list = []
        for u in usuarios:
            if hasattr(u, '_asdict'):
                usuarios_list.append(dict(u))
            elif hasattr(u, 'keys'):
                usuarios_list.append(dict(u))
            else:
                usuarios_list.append(u)

        return jsonify({
            'total': total_usuarios,
            'usuarios': usuarios_list
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Erro ao verificar usuários: {str(e)}'}), 500
        
@app.route('/cadastrar', methods=['POST'])
def cadastrar_usuario():
    """Rota para cadastrar novos usuários"""
    try:
        data = request.get_json()
        
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({
                'success': False,
                'message': 'Nome de usuário e senha são obrigatórios.'
            }), 400
        
        username = data['username'].strip()
        password = data['password']
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': 'Nome de usuário e senha não podem estar vazios.'
            }), 400
        
        if len(username) < 3:
            return jsonify({
                'success': False,
                'message': 'O nome de usuário deve ter pelo menos 3 caracteres.'
            }), 400
        
        if len(password) < 4:
            return jsonify({
                'success': False,
                'message': 'A senha deve ter pelo menos 4 caracteres.'
            }), 400
        
        # Verifica se o usuário já existe
        db = get_db_connection()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        query_check = "SELECT id FROM usuarios WHERE username = %s" if is_postgres else "SELECT id FROM usuarios WHERE username = ?"
        cursor.execute(query_check, (username,))
        usuario_existente = cursor.fetchone()
        
        if usuario_existente:
            return jsonify({
                'success': False,
                'message': f'O usuário "{username}" já existe. Escolha outro nome.'
            }), 400
        
        # Cria o hash da senha
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password_bytes, salt)
        hashed_password_str = hashed_password.decode('utf-8')
        
        # Insere o novo usuário
        query_insert = "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)" if is_postgres else "INSERT INTO usuarios (username, password_hash) VALUES (?, ?)"
        cursor.execute(query_insert, (username, hashed_password_str))
        db.commit()
        
        return jsonify({
            'success': True,
            'message': f'Usuário "{username}" cadastrado com sucesso!'
        }), 201
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro no servidor: {str(e)}'
        }), 500

# ========================================
# ROTAS DE MESAS
# ========================================

@app.route('/api/mesas', methods=['GET'])
def list_mesas():
    """Lista todas as mesas ou filtra por status."""
    try:
        status_filter = request.args.get('status')
        db = get_db_connection()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        query = 'SELECT id, numero, capacidade, localizacao, status FROM mesas'
        params = ()
        
        if status_filter:
            query += ' WHERE status = %s' if is_postgres else ' WHERE status = ?'
            params = (status_filter,)
            
        query += ' ORDER BY numero'
        
        cursor.execute(query, params)
        mesas = cursor.fetchall()
        
        return jsonify([dict(m) for m in mesas]), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao listar mesas: {str(e)}'}), 500

@app.route('/api/mesas', methods=['POST'])
def add_mesa():
    """Adiciona uma nova mesa."""
    try:
        data = request.get_json()
        if not data or 'numero' not in data or 'capacidade' not in data:
            return jsonify({'error': 'Número e capacidade são obrigatórios'}), 400
            
        numero = int(data['numero'])
        capacidade = int(data['capacidade'])
        localizacao = data.get('localizacao', '').strip()
        
        db = get_db_connection()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        query = 'INSERT INTO mesas (numero, capacidade, localizacao) VALUES (%s, %s, %s) RETURNING id, numero, capacidade, localizacao, status' if is_postgres else 'INSERT INTO mesas (numero, capacidade, localizacao) VALUES (?, ?, ?)'
        
        cursor.execute(query, (numero, capacidade, localizacao))
        
        if is_postgres:
            mesa_nova = dict(cursor.fetchone())
        else:
            mesa_id = cursor.lastrowid
            cursor.execute('SELECT id, numero, capacidade, localizacao, status FROM mesas WHERE id = ?', (mesa_id,))
            mesa_nova = dict(cursor.fetchone())
            
        db.commit()
        return jsonify(mesa_nova), 201
    
    except Exception as e:
        # Tenta pegar a mensagem de erro do Postgres para o erro de chave duplicada
        if 'duplicate key value violates unique constraint "mesas_numero_key"' in str(e):
             return jsonify({'error': 'Já existe uma mesa com este número.'}), 409
        
        return jsonify({'error': f'Erro ao adicionar mesa: {str(e)}'}), 500

@app.route('/api/mesas/<int:mesa_id>', methods=['PUT'])
def update_mesa(mesa_id):
    """Atualiza o status de uma mesa."""
    try:
        data = request.get_json()
        status = data.get('status')
        
        if not status or status not in ['disponivel', 'ocupada', 'reservada', 'suja']: # Adicionado 'suja'
            return jsonify({'error': 'Status inválido. Deve ser disponivel, ocupada, reservada ou suja.'}), 400
        
        db = get_db_connection()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        query = 'UPDATE mesas SET status = %s WHERE id = %s' if is_postgres else 'UPDATE mesas SET status = ? WHERE id = ?'
        
        cursor.execute(query, (status, mesa_id))
        db.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Mesa não encontrada.'}), 404
            
        return jsonify({'message': f'Status da Mesa {mesa_id} atualizado para {status}'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro ao atualizar mesa: {str(e)}'}), 500

# ========================================
# ROTAS DE COMANDAS E PDV (NOVAS E CORRIGIDAS)
# ========================================

@app.route('/api/comandas', methods=['POST'])
def abrir_comanda():
    """Abre uma nova comanda para uma mesa e muda o status da mesa para 'ocupada'."""
    try:
        data = request.get_json()
        
        if not data or 'mesa_id' not in data:
            return jsonify({'error': 'ID da mesa é obrigatório para abrir uma comanda.'}), 400
            
        mesa_id = int(data['mesa_id'])
        
        db = get_db_connection()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # 1. Verificar se a mesa existe e está disponível
        query_mesa_check = "SELECT id, status FROM mesas WHERE id = %s" if is_postgres else "SELECT id, status FROM mesas WHERE id = ?"
        cursor.execute(query_mesa_check, (mesa_id,))
        mesa = cursor.fetchone()
        
        if not mesa:
            return jsonify({'error': f'Mesa ID {mesa_id} não encontrada.'}), 404
            
        mesa_status = dict(mesa).get('status')
        if mesa_status != 'disponivel':
            return jsonify({'error': f'Mesa {mesa_id} não está disponível (Status: {mesa_status}).'}), 409

        # 2. Inserir a nova comanda
        query_insert_comanda = 'INSERT INTO comandas (mesa_id) VALUES (%s) RETURNING id' if is_postgres else 'INSERT INTO comandas (mesa_id) VALUES (?)'
        cursor.execute(query_insert_comanda, (mesa_id,))
        
        if is_postgres:
            comanda_id = dict(cursor.fetchone()).get('id')
        else:
            comanda_id = cursor.lastrowid
            
        # 3. Atualizar o status da mesa para 'ocupada'
        query_update_mesa = "UPDATE mesas SET status = %s WHERE id = %s" if is_postgres else "UPDATE mesas SET status = ? WHERE id = ?"
        cursor.execute(query_update_mesa, ('ocupada', mesa_id))
        
        db.commit()
        return jsonify({
            'message': f'Comanda {comanda_id} aberta com sucesso para a Mesa {mesa_id}.',
            'comanda_id': comanda_id,
            'mesa_id': mesa_id,
            'status_mesa': 'ocupada'
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({'error': f'Erro ao abrir comanda: {str(e)}'}), 500


@app.route('/api/comandas', methods=['GET'])
def list_comandas():
    """Lista todas as comandas, com filtro opcional por status (ex: status=aberta)."""
    try:
        status_filter = request.args.get('status')
        db = get_db_connection()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # Query para calcular o total usando preco_unitario da comanda_itens (CORREÇÃO)
        query = '''
            SELECT 
                c.id, c.data_abertura, c.data_fechamento, c.status,
                m.numero as numero_mesa, m.id as mesa_id,
                COALESCE(SUM(ci.quantidade * ci.preco_unitario), 0.0) as valor_total
            FROM comandas c
            JOIN mesas m ON c.mesa_id = m.id
            LEFT JOIN comanda_itens ci ON c.id = ci.comanda_id
            -- LEFT JOIN produtos p ON ci.produto_id = p.id -- Não precisamos mais do p.preco_venda aqui
        '''
        params = ()
        
        if status_filter:
            query += ' WHERE c.status = %s' if is_postgres else ' WHERE c.status = ?'
            params = (status_filter,)
            
        query += ' GROUP BY c.id, m.id, m.numero, c.data_abertura, c.data_fechamento, c.status ORDER BY c.data_abertura DESC'
        
        cursor.execute(query, params)
        comandas = cursor.fetchall()
        
        comandas_list = []
        for comanda in comandas:
            comanda_dict = dict(comanda)
            # Garante que o valor total seja float
            comanda_dict['valor_total'] = float(comanda_dict['valor_total'])
            comandas_list.append(comanda_dict)
            
        return jsonify(comandas_list), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro ao listar comandas: {str(e)}'}), 500


# Rota para adicionar itens a uma comanda (CORRIGIDA)
@app.route('/api/comandas/<int:comanda_id>/itens', methods=['POST'])
def add_item_comanda(comanda_id):
    """Adiciona um item a uma comanda existente, fixando o preco_unitario na comanda_itens."""
    data = request.get_json()
    produto_id = data.get('produto_id')
    quantidade = int(data.get('quantidade', 1))

    if not produto_id or quantidade <= 0:
        return jsonify({'error': 'Produto ID e quantidade válida são obrigatórios.'}), 400

    db = get_db_connection()
    cursor = db.cursor()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    
    try:
        # 1. Verificar se a comanda está aberta e OBTEM o preço de venda do produto
        query_data = '''
            SELECT c.status, p.preco_venda 
            FROM comandas c, produtos p 
            WHERE c.id = %s AND p.id = %s
        ''' if is_postgres else '''
            SELECT c.status, p.preco_venda 
            FROM comandas c, produtos p 
            WHERE c.id = ? AND p.id = ?
        '''
        cursor.execute(query_data, (comanda_id, produto_id))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'error': 'Comanda ou Produto não encontrado.'}), 404
        
        result_dict = dict(result)
        preco_unitario = float(result_dict['preco_venda'])
        
        if result_dict['status'] != 'aberta':
            return jsonify({'error': 'Comanda não está aberta.'}), 409

        # 2. Inserir/Atualizar o item na comanda_itens (incluindo o preco_unitario)
        if is_postgres:
            # PostgreSQL: Tenta inserir. Se a combinação (comanda_id, produto_id) 
            # já existir, atualiza APENAS a quantidade (mantém o preco_unitario original)
            query_insert = '''
                INSERT INTO comanda_itens (comanda_id, produto_id, quantidade, preco_unitario) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (comanda_id, produto_id) 
                DO UPDATE SET quantidade = comanda_itens.quantidade + EXCLUDED.quantidade 
                RETURNING id
            '''
            cursor.execute(query_insert, (comanda_id, produto_id, quantidade, preco_unitario))
        else:
            # SQLite: Tenta atualizar, se falhar, insere
            query_update = "UPDATE comanda_itens SET quantidade = quantidade + ? WHERE comanda_id = ? AND produto_id = ?"
            cursor.execute(query_update, (quantidade, comanda_id, produto_id))
            
            if cursor.rowcount == 0:
                query_insert = "INSERT INTO comanda_itens (comanda_id, produto_id, quantidade, preco_unitario) VALUES (?, ?, ?, ?)"
                cursor.execute(query_insert, (comanda_id, produto_id, quantidade, preco_unitario))

        db.commit()
        return jsonify({'message': f'Item ID {produto_id} adicionado à comanda {comanda_id} (x{quantidade})'}), 201

    except Exception as e:
        db.rollback()
        return jsonify({'error': f'Erro ao adicionar item à comanda: {str(e)}'}), 500


# ROTA CRÍTICA: FECHAMENTO E PAGAMENTO DE COMANDA (NOVA)
@app.route('/api/comandas/<int:comanda_id>/pagar', methods=['POST'])
def registrar_pagamento_comanda(comanda_id):
    """Fecha uma comanda, registra a venda na tabela 'vendas' e libera a mesa."""
    data = request.get_json()
    valor_pago = float(data.get('valor_pago', 0.0))
    metodo_pagamento = data.get('metodo_pagamento')
    
    if not metodo_pagamento or valor_pago <= 0:
        return jsonify({'error': 'Método de pagamento e valor pago são obrigatórios.'}), 400

    db = get_db_connection()
    cursor = db.cursor()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    
    try:
        # 1. Calcular o Valor Total da Comanda (usando preco_unitario de comanda_itens)
        query_total = '''
            SELECT 
                c.mesa_id, c.status,
                COALESCE(SUM(ci.quantidade * ci.preco_unitario), 0.0) as valor_total
            FROM comandas c
            LEFT JOIN comanda_itens ci ON c.id = ci.comanda_id
            WHERE c.id = %s GROUP BY c.id, c.mesa_id, c.status
        ''' if is_postgres else '''
            SELECT 
                c.mesa_id, c.status,
                COALESCE(SUM(ci.quantidade * ci.preco_unitario), 0.0) as valor_total
            FROM comandas c
            LEFT JOIN comanda_itens ci ON c.id = ci.comanda_id
            WHERE c.id = ? GROUP BY c.id, c.mesa_id, c.status
        '''
        cursor.execute(query_total, (comanda_id,))
        comanda_info = cursor.fetchone()
        
        if not comanda_info:
            return jsonify({'error': f'Comanda ID {comanda_id} não encontrada.'}), 404

        comanda_dict = dict(comanda_info)
        mesa_id = comanda_dict['mesa_id']
        valor_total = float(comanda_dict['valor_total'])
        troco = max(0.0, valor_pago - valor_total) # Calcula o troco

        if comanda_dict['status'] != 'aberta':
            return jsonify({'error': f'Comanda {comanda_id} não está aberta.'}), 409

        # 2. Registrar a Venda na tabela 'vendas'
        query_insert_venda = '''
            INSERT INTO vendas (comanda_id, valor_total, valor_pago, troco, metodo_pagamento) 
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        ''' if is_postgres else '''
            INSERT INTO vendas (comanda_id, valor_total, valor_pago, troco, metodo_pagamento) 
            VALUES (?, ?, ?, ?, ?)
        '''
        cursor.execute(query_insert_venda, (comanda_id, valor_total, valor_pago, troco, metodo_pagamento))
        
        # 3. Fechar a Comanda (Atualiza status para 'paga' e data_fechamento)
        now_str = datetime.now().isoformat()
        query_update_comanda = "UPDATE comandas SET status = %s, data_fechamento = %s, total = %s WHERE id = %s" if is_postgres else "UPDATE comandas SET status = ?, data_fechamento = ?, total = ? WHERE id = ?"
        cursor.execute(query_update_comanda, ('paga', now_str, valor_total, comanda_id))
        
        # 4. Liberar a Mesa (Atualiza status para 'disponivel')
        query_update_mesa = "UPDATE mesas SET status = %s WHERE id = %s" if is_postgres else "UPDATE mesas SET status = ? WHERE id = ?"
        cursor.execute(query_update_mesa, ('disponivel', mesa_id))
        
        db.commit()
        
        return jsonify({
            'message': f'Comanda {comanda_id} paga e fechada. Mesa {mesa_id} liberada.',
            'valor_total': valor_total,
            'troco': troco
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({'error': f'Erro na transação de pagamento/comanda: {str(e)}'}), 500


# ========================================
# ROTAS DE INSUMOS 
# ========================================

@app.route('/api/insumos', methods=['GET'])
def get_insumos():
    """Lista todos os insumos"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute('''
    SELECT id, nome, unidade_medida, quantidade_estoque, estoque_minimo, preco_unitario, fornecedor 
    FROM insumos ORDER BY nome
''')
        insumos = cursor.fetchall()
        
        # Converte para lista de dicionários
        insumos_list = []
        for insumo in insumos:
            insumos_list.append(dict(insumo))
        
        return jsonify(insumos_list), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar insumos: {str(e)}'}), 500

# Rota de adicionar insumo corrigida para ter o prefixo /api e método POST
@app.route('/api/insumos', methods=['POST']) 
def add_insumo():
    """Adiciona um novo insumo (Resolve Erro 405 ao Cadastrar)"""
    try:
        data = request.get_json()
        
        if not data or 'nome' not in data or 'unidade_medida' not in data:
            return jsonify({'error': 'Nome e unidade de medida são obrigatórios'}), 400
        
        nome = data['nome'].strip()
        unidade_medida = data['unidade_medida'].strip()
        quantidade_estoque = float(data.get('quantidade_estoque', 0))
        estoque_minimo = float(data.get('estoque_minimo', 0))
        preco_unitario = float(data.get('preco_unitario', 0.0))
        fornecedor = data.get('fornecedor', '').strip()
        
        if not nome or not unidade_medida:
            return jsonify({'error': 'Nome e unidade de medida não podem estar vazios'}), 400
        
        if quantidade_estoque < 0 or estoque_minimo < 0 or preco_unitario < 0:
            return jsonify({'error': 'Valores numéricos não podem ser negativos'}), 400
        
        db = get_db_connection()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # Inserir todos os campos que estão no schema.sql
        if is_postgres:
            query = '''
                INSERT INTO insumos (nome, unidade_medida, quantidade_estoque, estoque_minimo, preco_unitario, fornecedor) 
                VALUES (%s, %s, %s, %s, %s, %s) 
                RETURNING id, nome, unidade_medida, quantidade_estoque, estoque_minimo, preco_unitario, fornecedor
            '''
            cursor.execute(
                query,
                (nome, unidade_medida, quantidade_estoque, estoque_minimo, preco_unitario, fornecedor)
            )
            insumo = dict(cursor.fetchone())
        else:
            query = '''
                INSERT INTO insumos (nome, unidade_medida, quantidade_estoque, estoque_minimo, preco_unitario, fornecedor) 
                VALUES (?, ?, ?, ?, ?, ?)
            '''
            cursor.execute(
                query,
                (nome, unidade_medida, quantidade_estoque, estoque_minimo, preco_unitario, fornecedor)
            )
            new_id = cursor.lastrowid
            # Busca o insumo completo para retornar
            cursor.execute('SELECT id, nome, unidade_medida, quantidade_estoque, estoque_minimo, preco_unitario, fornecedor FROM insumos WHERE id = ?', (new_id,))
            insumo = dict(cursor.fetchone())

        db.commit()
        return jsonify(insumo), 201
        
    except ValueError as e:
        return jsonify({'error': f'Valor inválido: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao adicionar insumo: {str(e)}'}), 500

# ROTA NOVA: Atualizar Insumo (PUT)
@app.route('/api/insumos/<int:insumo_id>', methods=['PUT'])
def update_insumo(insumo_id):
    """Atualiza um insumo existente pelo ID"""
    try:
        data = request.get_json()
        db = get_db_connection()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        updates = []
        values = []

        if 'nome' in data:
            updates.append('nome = %s' if is_postgres else 'nome = ?')
            values.append(data['nome'].strip())
        if 'unidade_medida' in data:
            updates.append('unidade_medida = %s' if is_postgres else 'unidade_medida = ?')
            values.append(data['unidade_medida'].strip())
        if 'quantidade_estoque' in data:
            quantidade_estoque = float(data['quantidade_estoque'])
            if quantidade_estoque < 0:
                return jsonify({'error': 'Estoque não pode ser negativo'}), 400
            updates.append('quantidade_estoque = %s' if is_postgres else 'quantidade_estoque = ?')
            values.append(quantidade_estoque)
        if 'estoque_minimo' in data:
            estoque_minimo = float(data['estoque_minimo'])
            if estoque_minimo < 0:
                return jsonify({'error': 'Estoque mínimo não pode ser negativo'}), 400
            updates.append('estoque_minimo = %s' if is_postgres else 'estoque_minimo = ?')
            values.append(estoque_minimo)
        if 'preco_unitario' in data:
            preco_unitario = float(data['preco_unitario'])
            if preco_unitario < 0:
                return jsonify({'error': 'Preço unitário não pode ser negativo'}), 400
            updates.append('preco_unitario = %s' if is_postgres else 'preco_unitario = ?')
            values.append(preco_unitario)
        if 'fornecedor' in data:
            updates.append('fornecedor = %s' if is_postgres else 'fornecedor = ?')
            values.append(data['fornecedor'].strip())

        if not updates:
            return jsonify({'error': 'Nenhum campo para atualizar'}), 400
        
        values.append(insumo_id)
        query = f"UPDATE insumos SET {', '.join(updates)} WHERE id = {'%s' if is_postgres else '?'}"
        
        cursor.execute(query, values)
        db.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Insumo não encontrado'}), 404
        
        return jsonify({'message': 'Insumo atualizado com sucesso'}), 200
        
    except ValueError:
        return jsonify({'error': 'Valor de estoque ou unidade inválido'}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao atualizar insumo: {str(e)}'}), 500

# ROTA NOVA: Deletar Insumo (DELETE)
@app.route('/api/insumos/<int:insumo_id>', methods=['DELETE'])
def delete_insumo(insumo_id):
    """Remove um insumo existente pelo ID"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        query = 'DELETE FROM insumos WHERE id = %s' if is_postgres else 'DELETE FROM insumos WHERE id = ?'
        
        cursor.execute(query, (insumo_id,))
        db.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Insumo não encontrado'}), 404
        
        return jsonify({'message': 'Insumo removido com sucesso'}), 200
        
    except Exception as e:
        if 'violates foreign key constraint' in str(e):
             return jsonify({'error': 'Não é possível remover. Este insumo é usado em uma Ficha Técnica.'}), 409
        return jsonify({'error': f'Erro ao remover insumo: {str(e)}'}), 500


# ========================================
# ROTAS DE DASHBOARD/ESTOQUE
# ========================================

# ROTA: Alerta de Estoque Baixo 
@app.route('/api/estoque-baixo', methods=['GET'])
def estoque_baixo():
    """Retorna a lista de insumos com estoque abaixo do mínimo"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        query = '''
            SELECT id, nome, unidade_medida, quantidade_estoque, estoque_minimo
            FROM insumos
            WHERE quantidade_estoque <= estoque_minimo
            ORDER BY nome
        '''
        
        cursor.execute(query)
        alertas = cursor.fetchall()
        
        alertas_list = []
        for alerta in alertas:
            alerta_dict = dict(alerta) if not isinstance(alerta, dict) else alerta
            alertas_list.append({
                "id": alerta_dict['id'],
                "nome": alerta_dict['nome'],
                "estoque_atual": alerta_dict['quantidade_estoque'],
                "unidade_medida": alerta_dict['unidade_medida'],
                "estoque_minimo": alerta_dict['estoque_minimo']
            })
            
        return jsonify(alertas_list), 200
    
    except Exception as e:
        print(f"Erro ao buscar estoque baixo: {str(e)}")
        return jsonify({'error': f'Erro ao buscar alertas de estoque: {str(e)}'}), 500

# ROTA: Total de Produtos
@app.route('/api/produtos/total', methods=['GET'])
def total_produtos():
    """Retorna o número total de produtos cadastrados"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM produtos")
        resultado = cursor.fetchone()
        
        if isinstance(resultado, dict) or (resultado and hasattr(resultado, 'keys')):
            total_produtos = resultado['total']
        else:
            total_produtos = resultado[0] if resultado else 0
        
        return jsonify({"total_produtos": total_produtos}), 200
    except Exception as e:
        print(f"Erro ao buscar total de produtos: {str(e)}")
        return jsonify({"total_produtos": 0, "error": str(e)}), 500

# Rotas do Dashboard (MOCKADOS para não quebrar o frontend)
@app.route('/api/par/estatisticas', methods=['GET'])
def estatisticas_parciais():
    return jsonify({"receita_30_dias": 0.00}), 200 

@app.route('/api/vendas/por-dia', methods=['GET'])
def vendas_por_dia():
    return jsonify([]), 200 

@app.route('/api/produtos/o-mais-vendidos', methods=['GET'])
def produtos_mais_vendidos():
    return jsonify([]), 200

# ========================================
# ROTAS DE PRODUTOS (AJUSTADAS E COMPLETAS)
# ========================================

@app.route('/api/produtos', methods=['GET'])
def get_produtos():
    """Lista todos os produtos."""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute('SELECT id, nome, preco_venda FROM produtos ORDER BY nome')
        produtos = cursor.fetchall()
        return jsonify([dict(row) for row in produtos]), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao listar produtos: {str(e)}'}), 500

@app.route('/api/produtos', methods=['POST'])
def add_produto():
    """Adiciona um novo produto."""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        data = request.get_json()
        
        if not data or 'nome' not in data or 'preco_venda' not in data:
            return jsonify({'error': 'Nome e preço de venda são obrigatórios'}), 400
        
        nome = data['nome'].strip()
        preco_venda = float(data['preco_venda'])
        
        if not nome:
            return jsonify({'error': 'Nome não pode estar vazio'}), 400
        
        if preco_venda <= 0:
            return jsonify({'error': 'Preço deve ser maior que zero'}), 400
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        if is_postgres:
            query = 'INSERT INTO produtos (nome, preco_venda) VALUES (%s, %s) RETURNING id, nome, preco_venda'
            cursor.execute(query, (nome, preco_venda))
            produto = dict(cursor.fetchone())
        else:
            query = 'INSERT INTO produtos (nome, preco_venda) VALUES (?, ?)'
            cursor.execute(query, (nome, preco_venda))
            produto_id = cursor.lastrowid
            cursor.execute('SELECT id, nome, preco_venda FROM produtos WHERE id = ?', (produto_id,))
            produto = dict(cursor.fetchone())

        db.commit()
        return jsonify(produto), 201
        
    except ValueError as e:
        return jsonify({'error': f'Valor inválido: {str(e)}'}), 400
    except Exception as e:
        db.rollback()
        return jsonify({'error': f'Erro ao adicionar produto: {str(e)}'}), 500

@app.route('/api/produtos/<int:produto_id>', methods=['PUT'])
def update_produto(produto_id):
    """Atualiza um produto existente."""
    try:
        data = request.get_json()
        db = get_db_connection()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        updates = []
        values = []

        if 'nome' in data:
            updates.append('nome = %s' if is_postgres else 'nome = ?')
            values.append(data['nome'].strip())
        if 'preco_venda' in data:
            preco_venda = float(data['preco_venda'])
            if preco_venda <= 0:
                return jsonify({'error': 'Preço deve ser maior que zero'}), 400
            updates.append('preco_venda = %s' if is_postgres else 'preco_venda = ?')
            values.append(preco_venda)

        if not updates:
            return jsonify({'error': 'Nenhum campo para atualizar'}), 400
        
        values.append(produto_id)
        query = f"UPDATE produtos SET {', '.join(updates)} WHERE id = {'%s' if is_postgres else '?'}"
        
        cursor.execute(query, values)
        db.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Produto não encontrado'}), 404
        
        return jsonify({'message': 'Produto atualizado com sucesso'}), 200
        
    except ValueError:
        return jsonify({'error': 'Valor de preço inválido'}), 400
    except Exception as e:
        db.rollback()
        return jsonify({'error': f'Erro ao atualizar produto: {str(e)}'}), 500

@app.route('/api/produtos/<int:produto_id>', methods=['DELETE'])
def delete_produto(produto_id):
    """Remove um produto existente."""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        query = 'DELETE FROM produtos WHERE id = %s' if is_postgres else 'DELETE FROM produtos WHERE id = ?'
        
        cursor.execute(query, (produto_id,))
        db.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Produto não encontrado'}), 404
        
        return jsonify({'message': 'Produto removido com sucesso'}), 200
        
    except Exception as e:
        # Verifica se o erro é de chave estrangeira
        if 'violates foreign key constraint' in str(e) or 'FOREIGN KEY constraint failed' in str(e):
            db.rollback()
            return jsonify({'error': 'Não é possível remover. Este produto está em uma Comanda ou Ficha Técnica.'}), 409
        
        db.rollback()
        return jsonify({'error': f'Erro ao remover produto: {str(e)}'}), 500


if __name__ == '__main__':
    # Cria o banco de dados SQLite local se não existir
    if not os.environ.get('DATABASE_URL') and not os.path.exists(DATABASE):
        try:
            init_db()
            print("Banco de dados SQLite inicializado (desenvolvimento).")
        except Exception as e:
            print(f"Atenção: Falha ao inicializar o DB no startup: {e}")
            
    port = int(os.environ.get('PORT', 5000))
    # Para o Render, use host='0.0.0.0'
    app.run(host='0.0.0.0', port=port, debug=True)