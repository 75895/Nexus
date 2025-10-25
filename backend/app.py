import os
import sqlite3
from flask import Flask, jsonify, request, g
from flask_cors import CORS
import bcrypt

app = Flask(__name__)
CORS(app)

DATABASE = 'restaurante.db'

def get_db():
    """Retorna conexão com o banco de dados (SQLite local ou PostgreSQL no Render)"""
    db = getattr(g, '_database', None)
    if db is None:
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # Produção: PostgreSQL
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            # Corrige URL se necessário
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

def init_db():
    """Inicializa o banco de dados com as tabelas necessárias"""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Verifica se está usando PostgreSQL ou SQLite
        database_url = os.environ.get('DATABASE_URL')
        is_postgres = database_url is not None
        
        # Ajusta o tipo de dados conforme o banco
        if is_postgres:
            # PostgreSQL
            schema = """
            DROP TABLE IF EXISTS itens_comanda CASCADE;
            DROP TABLE IF EXISTS comandas CASCADE;
            DROP TABLE IF EXISTS mesas CASCADE;
            DROP TABLE IF EXISTS vendas CASCADE;
            DROP TABLE IF EXISTS ficha_tecnica CASCADE;
            DROP TABLE IF EXISTS produtos CASCADE;
            DROP TABLE IF EXISTS insumos CASCADE;
            DROP TABLE IF EXISTS usuarios CASCADE;

            CREATE TABLE IF NOT EXISTS insumos (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                unidade_medida TEXT NOT NULL,
                estoque_atual REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS produtos (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                preco_venda REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ficha_tecnica (
                id SERIAL PRIMARY KEY,
                produto_id INTEGER NOT NULL,
                insumo_id INTEGER NOT NULL,
                quantidade_necessaria REAL NOT NULL,
                FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE CASCADE,
                FOREIGN KEY (insumo_id) REFERENCES insumos (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS vendas (
                id SERIAL PRIMARY KEY,
                produto_id INTEGER NOT NULL,
                quantidade_vendida INTEGER NOT NULL,
                data_venda TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                data_criacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS mesas (
                id SERIAL PRIMARY KEY,
                numero INTEGER NOT NULL UNIQUE,
                capacidade INTEGER NOT NULL,
                localizacao TEXT,
                status TEXT NOT NULL DEFAULT 'disponivel',
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS comandas (
                id SERIAL PRIMARY KEY,
                mesa_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'aberta',
                total DECIMAL(10,2) DEFAULT 0,
                data_abertura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_fechamento TIMESTAMP,
                FOREIGN KEY (mesa_id) REFERENCES mesas(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS itens_comanda (
                id SERIAL PRIMARY KEY,
                comanda_id INTEGER NOT NULL,
                produto_id INTEGER NOT NULL,
                quantidade INTEGER NOT NULL,
                preco_unitario DECIMAL(10,2) NOT NULL,
                subtotal DECIMAL(10,2) NOT NULL,
                observacoes TEXT,
                data_adicao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (comanda_id) REFERENCES comandas(id) ON DELETE CASCADE,
                FOREIGN KEY (produto_id) REFERENCES produtos(id)
            );
            """
        else:
            # SQLite
            with app.open_resource('schema.sql', mode='r') as f:
                schema = f.read()
        
        cursor.executescript(schema) if not is_postgres else [cursor.execute(stmt) for stmt in schema.split(';') if stmt.strip()]
        db.commit()
        print("✅ Banco de dados inicializado com sucesso!")

@app.route('/init_db')
def initialize_db_route():
    try:
        init_db()
        return jsonify({'message': 'Banco de dados inicializado com sucesso!'})
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
        
        db = get_db()
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
        
        # Converte para dict se necessário (PostgreSQL)
        if hasattr(usuario, '_asdict'):
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
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM usuarios")
        resultado = cursor.fetchone()
        total_usuarios = resultado['total'] if isinstance(resultado, dict) else resultado[0]
        
        cursor.execute("SELECT id, username, data_criacao FROM usuarios")
        usuarios = cursor.fetchall()
        
        # Converte para dict se necessário
        usuarios_list = []
        for u in usuarios:
            if hasattr(u, '_asdict'):
                usuarios_list.append(dict(u))
            else:
                usuarios_list.append(dict(u))
        
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
        db = get_db()
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
# ROTAS DE INSUMOS
# ========================================

@app.route('/api/insumos', methods=['GET'])
def get_insumos():
    """Lista todos os insumos"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id, nome, unidade_medida, estoque_atual FROM insumos ORDER BY nome')
        insumos = cursor.fetchall()
        
        # Converte para lista de dicionários
        insumos_list = []
        for insumo in insumos:
            insumos_list.append(dict(insumo))
        
        return jsonify(insumos_list), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar insumos: {str(e)}'}), 500

@app.route('/insumos', methods=['POST'])
def add_insumo():
    """Adiciona um novo insumo"""
    try:
        data = request.get_json()
        
        if not data or 'nome' not in data or 'unidade_medida' not in data:
            return jsonify({'error': 'Nome e unidade de medida são obrigatórios'}), 400
        
        nome = data['nome'].strip()
        unidade_medida = data['unidade_medida'].strip()
        estoque_atual = float(data.get('estoque_atual', 0))
        
        if not nome or not unidade_medida:
            return jsonify({'error': 'Nome e unidade de medida não podem estar vazios'}), 400
        
        if estoque_atual < 0:
            return jsonify({'error': 'Estoque não pode ser negativo'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        if is_postgres:
            cursor.execute(
                'INSERT INTO insumos (nome, unidade_medida, estoque_atual) VALUES (%s, %s, %s) RETURNING id, nome, unidade_medida, estoque_atual',
                (nome, unidade_medida, estoque_atual)
            )
            insumo = dict(cursor.fetchone())
        else:
            cursor.execute(
                'INSERT INTO insumos (nome, unidade_medida, estoque_atual) VALUES (?, ?, ?)',
                (nome, unidade_medida, estoque_atual)
            )
            new_id = cursor.lastrowid
            insumo = {
                'id': new_id,
                'nome': nome,
                'unidade_medida': unidade_medida,
                'estoque_atual': float(estoque_atual)
            }
        
        db.commit()
        return jsonify(insumo), 201
        
    except ValueError as e:
        return jsonify({'error': f'Valor inválido: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao adicionar insumo: {str(e)}'}), 500


# ========================================
# ROTAS DE PRODUTOS
# ========================================

@app.route('/produtos', methods=['GET'])
def get_produtos():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, nome, preco_venda FROM produtos')
    produtos = cursor.fetchall()
    return jsonify([dict(row) for row in produtos])

@app.route('/produtos', methods=['POST'])
def add_produto():
    """Adiciona um novo produto"""
    try:
        db = get_db()
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
            produto = {'id': produto_id, 'nome': nome, 'preco_venda': float(preco_venda)}
        
        db.commit()
        return jsonify(produto), 201
        
    except ValueError as e:
        return jsonify({'error': f'Valor inválido: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Erro ao adicionar produto: {str(e)}'}), 500


# ========================================
# ROTAS DE FICHA TÉCNICA
# ========================================

@app.route('/fichas_tecnicas/<int:produto_id>', methods=['GET'])
def get_ficha_tecnica(produto_id):
    db = get_db()
    cursor = db.cursor()
    
    is_postgres = os.environ.get('DATABASE_URL') is not None
    query = '''
        SELECT ft.id, ft.quantidade_necessaria, i.nome as insumo_nome, i.unidade_medida, i.id as insumo_id
        FROM ficha_tecnica ft
        JOIN insumos i ON ft.insumo_id = i.id
        WHERE ft.produto_id = %s
    ''' if is_postgres else '''
        SELECT ft.id, ft.quantidade_necessaria, i.nome as insumo_nome, i.unidade_medida, i.id as insumo_id
        FROM ficha_tecnica ft
        JOIN insumos i ON ft.insumo_id = i.id
        WHERE ft.produto_id = ?
    '''
    
    cursor.execute(query, (produto_id,))
    fichas = cursor.fetchall()
    return jsonify([dict(row) for row in fichas])

@app.route('/fichas_tecnicas', methods=['POST'])
def add_ficha_tecnica():
    """Adiciona um item à ficha técnica de um produto"""
    try:
        data = request.get_json()
        
        if not data or 'produto_id' not in data or 'insumo_id' not in data or 'quantidade_necessaria' not in data:
            return jsonify({'error': 'Dados incompletos'}), 400
        
        produto_id = int(data['produto_id'])
        insumo_id = int(data['insumo_id'])
        quantidade_necessaria = float(data['quantidade_necessaria'])
        
        if quantidade_necessaria <= 0:
            return jsonify({'error': 'Quantidade deve ser maior que zero'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        if is_postgres:
            cursor.execute(
                'INSERT INTO ficha_tecnica (produto_id, insumo_id, quantidade_necessaria) VALUES (%s, %s, %s) RETURNING id',
                (produto_id, insumo_id, quantidade_necessaria)
            )
            result = cursor.fetchone()
            new_id = result['id'] if isinstance(result, dict) else result[0]
        else:
            cursor.execute(
                'INSERT INTO ficha_tecnica (produto_id, insumo_id, quantidade_necessaria) VALUES (?, ?, ?)',
                (produto_id, insumo_id, quantidade_necessaria)
            )
            new_id = cursor.lastrowid
        
        db.commit()
        return jsonify({'id': new_id, 'message': 'Item adicionado à ficha técnica com sucesso'}), 201
    
    except ValueError as e:
        return jsonify({'error': f'Valor inválido: {str(e)}'}), 400
    except Exception as e:
        print(f"Erro ao adicionar ficha técnica: {str(e)}")
        return jsonify({'error': f'Erro ao adicionar ficha técnica: {str(e)}'}), 500

# ========================================
# ROTAS DE VENDAS
# ========================================

@app.route('/vendas', methods=['POST'])
def registrar_venda_pdv():
    data = request.get_json()
    itens_carrinho = data.get('itens', [])

    if not itens_carrinho:
        return jsonify({'error': 'Carrinho de compras vazio.'}), 400

    db = get_db()
    cursor = db.cursor()
    
    is_postgres = os.environ.get('DATABASE_URL') is not None

    try:
        for item in itens_carrinho:
            produto_id = item['produto_id']
            quantidade_vendida = item['quantidade']

            query_ficha = 'SELECT insumo_id, quantidade_necessaria FROM ficha_tecnica WHERE produto_id = %s' if is_postgres else 'SELECT insumo_id, quantidade_necessaria FROM ficha_tecnica WHERE produto_id = ?'
            cursor.execute(query_ficha, (produto_id,))
            ficha_tecnica = cursor.fetchall()

            if not ficha_tecnica:
                raise ValueError(f'Produto ID {produto_id} sem ficha técnica cadastrada.')

            for row in ficha_tecnica:
                row_dict = dict(row) if not isinstance(row, dict) else row
                insumo_id = row_dict['insumo_id']
                necessario_por_unidade = row_dict['quantidade_necessaria']
                necessario_total = necessario_por_unidade * quantidade_vendida

                query_insumo = 'SELECT nome, estoque_atual FROM insumos WHERE id = %s' if is_postgres else 'SELECT nome, estoque_atual FROM insumos WHERE id = ?'
                cursor.execute(query_insumo, (insumo_id,))
                resultado_insumo = cursor.fetchone()
                
                if resultado_insumo is None:
                    raise ValueError(f"Insumo ID {insumo_id} não encontrado.")

                insumo_dict = dict(resultado_insumo) if not isinstance(resultado_insumo, dict) else resultado_insumo
                insumo_nome = insumo_dict['nome']
                estoque_atual = insumo_dict['estoque_atual']

                if estoque_atual < necessario_total:
                    raise ValueError(f'Estoque insuficiente para o insumo: "{insumo_nome}". Necessário: {necessario_total}, Disponível: {estoque_atual}')

                query_update = 'UPDATE insumos SET estoque_atual = estoque_atual - %s WHERE id = %s' if is_postgres else 'UPDATE insumos SET estoque_atual = estoque_atual - ? WHERE id = ?'
                cursor.execute(query_update, (necessario_total, insumo_id))
            
            query_venda = 'INSERT INTO vendas (produto_id, quantidade_vendida, data_venda) VALUES (%s, %s, CURRENT_TIMESTAMP)' if is_postgres else 'INSERT INTO vendas (produto_id, quantidade_vendida, data_venda) VALUES (?, ?, CURRENT_TIMESTAMP)'
            cursor.execute(query_venda, (produto_id, quantidade_vendida))
        
        db.commit()
        return jsonify({'message': 'Venda registrada e estoque atualizado com sucesso!'}), 200

    except (Exception, ValueError) as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
# ========================================
# ROTAS DE MESAS
# ========================================

@app.route('/api/mesas', methods=['GET'])
def get_mesas():
    """Lista todas as mesas com status e comanda ativa"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # Query para buscar mesas com informações de comanda ativa
        query = '''
            SELECT 
                m.id, m.numero, m.capacidade, m.localizacao, m.status,
                c.id as comanda_id, c.total as comanda_total
            FROM mesas m
            LEFT JOIN comandas c ON m.id = c.mesa_id AND c.status = 'aberta'
            ORDER BY m.numero
        '''
        
        cursor.execute(query)
        mesas = cursor.fetchall()
        
        mesas_list = []
        for mesa in mesas:
            mesa_dict = dict(mesa) if not isinstance(mesa, dict) else mesa
            mesas_list.append({
                'id': mesa_dict['id'],
                'numero': mesa_dict['numero'],
                'capacidade': mesa_dict['capacidade'],
                'localizacao': mesa_dict['localizacao'],
                'status': mesa_dict['status'],
                'comanda_ativa': {
                    'id': mesa_dict.get('comanda_id'),
                    'total': float(mesa_dict.get('comanda_total', 0)) if mesa_dict.get('comanda_total') else 0
                } if mesa_dict.get('comanda_id') else None
            })
        
        return jsonify(mesas_list), 200
    except Exception as e:
        print(f"Erro ao buscar mesas: {str(e)}")
        return jsonify({'error': f'Erro ao buscar mesas: {str(e)}'}), 500


@app.route('/api/mesas', methods=['POST'])
def add_mesa():
    """Cadastra uma nova mesa"""
    try:
        data = request.get_json()
        
        if not data or 'numero' not in data or 'capacidade' not in data:
            return jsonify({'error': 'Número e capacidade são obrigatórios'}), 400
        
        numero = int(data['numero'])
        capacidade = int(data['capacidade'])
        localizacao = data.get('localizacao', '')
        
        if numero <= 0 or capacidade <= 0:
            return jsonify({'error': 'Número e capacidade devem ser maiores que zero'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        if is_postgres:
            cursor.execute(
                'INSERT INTO mesas (numero, capacidade, localizacao) VALUES (%s, %s, %s) RETURNING id, numero, capacidade, localizacao, status',
                (numero, capacidade, localizacao)
            )
            result = cursor.fetchone()
            mesa = dict(result) if isinstance(result, dict) else {
                'id': result[0], 'numero': result[1], 'capacidade': result[2],
                'localizacao': result[3], 'status': result[4]
            }
        else:
            cursor.execute(
                'INSERT INTO mesas (numero, capacidade, localizacao) VALUES (?, ?, ?)',
                (numero, capacidade, localizacao)
            )
            new_id = cursor.lastrowid
            mesa = {
                'id': new_id,
                'numero': numero,
                'capacidade': capacidade,
                'localizacao': localizacao,
                'status': 'disponivel'
            }
        
        db.commit()
        return jsonify(mesa), 201
        
    except Exception as e:
        print(f"Erro ao adicionar mesa: {str(e)}")
        return jsonify({'error': f'Erro ao adicionar mesa: {str(e)}'}), 500


@app.route('/api/mesas/<int:mesa_id>', methods=['PUT'])
def update_mesa(mesa_id):
    """Atualiza informações de uma mesa"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Dados não fornecidos'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # Monta query dinamicamente baseado nos campos fornecidos
        updates = []
        values = []
        
        if 'numero' in data:
            updates.append('numero = %s' if is_postgres else 'numero = ?')
            values.append(int(data['numero']))
        if 'capacidade' in data:
            updates.append('capacidade = %s' if is_postgres else 'capacidade = ?')
            values.append(int(data['capacidade']))
        if 'localizacao' in data:
            updates.append('localizacao = %s' if is_postgres else 'localizacao = ?')
            values.append(data['localizacao'])
        if 'status' in data:
            updates.append('status = %s' if is_postgres else 'status = ?')
            values.append(data['status'])
        
        if not updates:
            return jsonify({'error': 'Nenhum campo para atualizar'}), 400
        
        values.append(mesa_id)
        query = f"UPDATE mesas SET {', '.join(updates)} WHERE id = {'%s' if is_postgres else '?'}"
        
        cursor.execute(query, values)
        db.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Mesa não encontrada'}), 404
        
        return jsonify({'message': 'Mesa atualizada com sucesso'}), 200
        
    except Exception as e:
        print(f"Erro ao atualizar mesa: {str(e)}")
        return jsonify({'error': f'Erro ao atualizar mesa: {str(e)}'}), 500


@app.route('/api/mesas/<int:mesa_id>', methods=['DELETE'])
def delete_mesa(mesa_id):
    """Remove uma mesa"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        query = 'DELETE FROM mesas WHERE id = %s' if is_postgres else 'DELETE FROM mesas WHERE id = ?'
        
        cursor.execute(query, (mesa_id,))
        db.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Mesa não encontrada'}), 404
        
        return jsonify({'message': 'Mesa removida com sucesso'}), 200
        
    except Exception as e:
        print(f"Erro ao remover mesa: {str(e)}")
        return jsonify({'error': f'Erro ao remover mesa: {str(e)}'}), 500


# ========================================
# ROTAS DE COMANDAS
# ========================================

@app.route('/api/comandas', methods=['GET'])
def get_comandas():
    """Lista todas as comandas (pode filtrar por status)"""
    try:
        status_filter = request.args.get('status', None)
        
        db = get_db()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        if status_filter:
            query = '''
                SELECT c.id, c.mesa_id, m.numero as mesa_numero, c.status, c.total, 
                       c.data_abertura, c.data_fechamento
                FROM comandas c
                JOIN mesas m ON c.mesa_id = m.id
                WHERE c.status = %s
                ORDER BY c.data_abertura DESC
            ''' if is_postgres else '''
                SELECT c.id, c.mesa_id, m.numero as mesa_numero, c.status, c.total, 
                       c.data_abertura, c.data_fechamento
                FROM comandas c
                JOIN mesas m ON c.mesa_id = m.id
                WHERE c.status = ?
                ORDER BY c.data_abertura DESC
            '''
            cursor.execute(query, (status_filter,))
        else:
            query = '''
                SELECT c.id, c.mesa_id, m.numero as mesa_numero, c.status, c.total, 
                       c.data_abertura, c.data_fechamento
                FROM comandas c
                JOIN mesas m ON c.mesa_id = m.id
                ORDER BY c.data_abertura DESC
            '''
            cursor.execute(query)
        
        comandas = cursor.fetchall()
        
        comandas_list = []
        for comanda in comandas:
            comanda_dict = dict(comanda) if not isinstance(comanda, dict) else comanda
            comandas_list.append({
                'id': comanda_dict['id'],
                'mesa_id': comanda_dict['mesa_id'],
                'mesa_numero': comanda_dict['mesa_numero'],
                'status': comanda_dict['status'],
                'total': float(comanda_dict['total']) if comanda_dict['total'] else 0,
                'data_abertura': str(comanda_dict['data_abertura']),
                'data_fechamento': str(comanda_dict['data_fechamento']) if comanda_dict.get('data_fechamento') else None
            })
        
        return jsonify(comandas_list), 200
    except Exception as e:
        print(f"Erro ao buscar comandas: {str(e)}")
        return jsonify({'error': f'Erro ao buscar comandas: {str(e)}'}), 500


@app.route('/api/comandas/<int:comanda_id>', methods=['GET'])
def get_comanda_detalhes(comanda_id):
    """Retorna detalhes de uma comanda com seus itens"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # Buscar comanda
        query_comanda = '''
            SELECT c.id, c.mesa_id, m.numero as mesa_numero, c.status, c.total, 
                   c.data_abertura, c.data_fechamento
            FROM comandas c
            JOIN mesas m ON c.mesa_id = m.id
            WHERE c.id = %s
        ''' if is_postgres else '''
            SELECT c.id, c.mesa_id, m.numero as mesa_numero, c.status, c.total, 
                   c.data_abertura, c.data_fechamento
            FROM comandas c
            JOIN mesas m ON c.mesa_id = m.id
            WHERE c.id = ?
        '''
        
        cursor.execute(query_comanda, (comanda_id,))
        comanda = cursor.fetchone()
        
        if not comanda:
            return jsonify({'error': 'Comanda não encontrada'}), 404
        
        comanda_dict = dict(comanda) if not isinstance(comanda, dict) else comanda
        
        # Buscar itens da comanda
        query_itens = '''
            SELECT ic.id, ic.produto_id, p.nome as produto_nome, ic.quantidade, 
                   ic.preco_unitario, ic.subtotal, ic.observacoes
            FROM itens_comanda ic
            JOIN produtos p ON ic.produto_id = p.id
            WHERE ic.comanda_id = %s
            ORDER BY ic.data_adicao
        ''' if is_postgres else '''
            SELECT ic.id, ic.produto_id, p.nome as produto_nome, ic.quantidade, 
                   ic.preco_unitario, ic.subtotal, ic.observacoes
            FROM itens_comanda ic
            JOIN produtos p ON ic.produto_id = p.id
            WHERE ic.comanda_id = ?
            ORDER BY ic.data_adicao
        '''
        
        cursor.execute(query_itens, (comanda_id,))
        itens = cursor.fetchall()
        
        itens_list = []
        for item in itens:
            item_dict = dict(item) if not isinstance(item, dict) else item
            itens_list.append({
                'id': item_dict['id'],
                'produto_id': item_dict['produto_id'],
                'produto_nome': item_dict['produto_nome'],
                'quantidade': item_dict['quantidade'],
                'preco_unitario': float(item_dict['preco_unitario']),
                'subtotal': float(item_dict['subtotal']),
                'observacoes': item_dict.get('observacoes', '')
            })
        
        resultado = {
            'id': comanda_dict['id'],
            'mesa_id': comanda_dict['mesa_id'],
            'mesa_numero': comanda_dict['mesa_numero'],
            'status': comanda_dict['status'],
            'total': float(comanda_dict['total']) if comanda_dict['total'] else 0,
            'data_abertura': str(comanda_dict['data_abertura']),
            'data_fechamento': str(comanda_dict['data_fechamento']) if comanda_dict.get('data_fechamento') else None,
            'itens': itens_list
        }
        
        return jsonify(resultado), 200
    except Exception as e:
        print(f"Erro ao buscar detalhes da comanda: {str(e)}")
        return jsonify({'error': f'Erro ao buscar detalhes da comanda: {str(e)}'}), 500


@app.route('/api/comandas', methods=['POST'])
def abrir_comanda():
    """Abre uma nova comanda em uma mesa"""
    try:
        data = request.get_json()
        
        if not data or 'mesa_id' not in data:
            return jsonify({'error': 'ID da mesa é obrigatório'}), 400
        
        mesa_id = int(data['mesa_id'])
        
        db = get_db()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # Verificar se a mesa existe
        query_check_mesa = 'SELECT id, status FROM mesas WHERE id = %s' if is_postgres else 'SELECT id, status FROM mesas WHERE id = ?'
        cursor.execute(query_check_mesa, (mesa_id,))
        mesa = cursor.fetchone()
        
        if not mesa:
            return jsonify({'error': 'Mesa não encontrada'}), 404
        
        mesa_dict = {'id': mesa['id'], 'status': mesa['status']} if isinstance(mesa, dict) else {'id': mesa[0], 'status': mesa[1]}
        
        # Verificar se já existe comanda aberta para esta mesa
        query_check_comanda = 'SELECT id FROM comandas WHERE mesa_id = %s AND status = %s' if is_postgres else 'SELECT id FROM comandas WHERE mesa_id = ? AND status = ?'
        cursor.execute(query_check_comanda, (mesa_id, 'aberta'))
        comanda_existente = cursor.fetchone()
        
        if comanda_existente:
            return jsonify({'error': 'Já existe uma comanda aberta para esta mesa'}), 400
        
        # Criar comanda
        if is_postgres:
            cursor.execute(
                'INSERT INTO comandas (mesa_id) VALUES (%s) RETURNING id, mesa_id, status, total, data_abertura',
                (mesa_id,)
            )
            result = cursor.fetchone()
            # Corrigido: PostgreSQL com RealDictCursor retorna dicionário
            if isinstance(result, dict):
                comanda = {
                    'id': result['id'],
                    'mesa_id': result['mesa_id'],
                    'status': result['status'],
                    'total': float(result['total']) if result['total'] else 0,
                    'data_abertura': str(result['data_abertura'])
                }
            else:
                comanda = {
                    'id': result[0],
                    'mesa_id': result[1],
                    'status': result[2],
                    'total': float(result[3]) if result[3] else 0,
                    'data_abertura': str(result[4])
                }
        else:
            cursor.execute(
                'INSERT INTO comandas (mesa_id) VALUES (?)',
                (mesa_id,)
            )
            new_id = cursor.lastrowid
            comanda = {
                'id': new_id,
                'mesa_id': mesa_id,
                'status': 'aberta',
                'total': 0,
                'data_abertura': None  # SQLite preenche automaticamente
            }
        
        # Atualizar status da mesa para 'ocupada'
        query_update_mesa = 'UPDATE mesas SET status = %s WHERE id = %s' if is_postgres else 'UPDATE mesas SET status = ? WHERE id = ?'
        cursor.execute(query_update_mesa, ('ocupada', mesa_id))
        
        db.commit()
        
        return jsonify({
            'id': comanda['id'],
            'mesa_id': comanda['mesa_id'],
            'status': comanda['status'],
            'total': float(comanda['total']) if comanda['total'] else 0,
            'message': 'Comanda aberta com sucesso'
        }), 201
        
    except Exception as e:
        print(f"Erro ao abrir comanda: {str(e)}")
        return jsonify({'error': f'Erro ao abrir comanda: {str(e)}'}), 500


@app.route('/api/comandas/<int:comanda_id>/itens', methods=['POST'])
def add_item_comanda(comanda_id):
    """Adiciona um item à comanda"""
    try:
        data = request.get_json()
        
        if not data or 'produto_id' not in data or 'quantidade' not in data:
            return jsonify({'error': 'Produto e quantidade são obrigatórios'}), 400
        
        produto_id = int(data['produto_id'])
        quantidade = int(data['quantidade'])
        observacoes = data.get('observacoes', '')
        
        if quantidade <= 0:
            return jsonify({'error': 'Quantidade deve ser maior que zero'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # Verificar se a comanda existe e está aberta
        query_check_comanda = 'SELECT id, status FROM comandas WHERE id = %s' if is_postgres else 'SELECT id, status FROM comandas WHERE id = ?'
        cursor.execute(query_check_comanda, (comanda_id,))
        comanda = cursor.fetchone()
        
        if not comanda:
            return jsonify({'error': 'Comanda não encontrada'}), 404
        
        comanda_dict = {'id': comanda['id'], 'status': comanda['status']} if isinstance(comanda, dict) else {'id': comanda[0], 'status': comanda[1]}
        
        if comanda_dict['status'] != 'aberta':
            return jsonify({'error': 'Comanda não está aberta'}), 400
        
        # Buscar preço do produto
        query_produto = 'SELECT id, preco_venda FROM produtos WHERE id = %s' if is_postgres else 'SELECT id, preco_venda FROM produtos WHERE id = ?'
        cursor.execute(query_produto, (produto_id,))
        produto = cursor.fetchone()
        
        if not produto:
            return jsonify({'error': 'Produto não encontrado'}), 404
        
        produto_dict = {'id': produto['id'], 'preco_venda': produto['preco_venda']} if isinstance(produto, dict) else {'id': produto[0], 'preco_venda': produto[1]}
        preco_unitario = float(produto_dict['preco_venda'])
        subtotal = preco_unitario * quantidade
        
        # Adicionar item à comanda
        if is_postgres:
            cursor.execute(
                'INSERT INTO itens_comanda (comanda_id, produto_id, quantidade, preco_unitario, subtotal, observacoes) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
                (comanda_id, produto_id, quantidade, preco_unitario, subtotal, observacoes)
            )
            result = cursor.fetchone()
            item_id = result['id'] if isinstance(result, dict) else result[0]
        else:
            cursor.execute(
                'INSERT INTO itens_comanda (comanda_id, produto_id, quantidade, preco_unitario, subtotal, observacoes) VALUES (?, ?, ?, ?, ?, ?)',
                (comanda_id, produto_id, quantidade, preco_unitario, subtotal, observacoes)
            )
            item_id = cursor.lastrowid
        
        # Atualizar total da comanda
        query_update_total = 'UPDATE comandas SET total = total + %s WHERE id = %s' if is_postgres else 'UPDATE comandas SET total = total + ? WHERE id = ?'
        cursor.execute(query_update_total, (subtotal, comanda_id))
        
        db.commit()
        
        return jsonify({
            'id': item_id,
            'comanda_id': comanda_id,
            'produto_id': produto_id,
            'quantidade': quantidade,
            'preco_unitario': preco_unitario,
            'subtotal': subtotal,
            'observacoes': observacoes,
            'message': 'Item adicionado com sucesso'
        }), 201
        
    except Exception as e:
        print(f"Erro ao adicionar item à comanda: {str(e)}")
        return jsonify({'error': f'Erro ao adicionar item à comanda: {str(e)}'}), 500


@app.route('/api/comandas/<int:comanda_id>/itens/<int:item_id>', methods=['DELETE'])
def remove_item_comanda(comanda_id, item_id):
    """Remove um item da comanda"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # Buscar o item para pegar o subtotal
        query_item = 'SELECT subtotal FROM itens_comanda WHERE id = %s AND comanda_id = %s' if is_postgres else 'SELECT subtotal FROM itens_comanda WHERE id = ? AND comanda_id = ?'
        cursor.execute(query_item, (item_id, comanda_id))
        item = cursor.fetchone()
        
        if not item:
            return jsonify({'error': 'Item não encontrado'}), 404
        
        item_dict = {'subtotal': item['subtotal']} if isinstance(item, dict) else {'subtotal': item[0]}
        subtotal = float(item_dict['subtotal'])
        
        # Remover item
        query_delete = 'DELETE FROM itens_comanda WHERE id = %s' if is_postgres else 'DELETE FROM itens_comanda WHERE id = ?'
        cursor.execute(query_delete, (item_id,))
        
        # Atualizar total da comanda
        query_update_total = 'UPDATE comandas SET total = total - %s WHERE id = %s' if is_postgres else 'UPDATE comandas SET total = total - ? WHERE id = ?'
        cursor.execute(query_update_total, (subtotal, comanda_id))
        
        db.commit()
        
        return jsonify({'message': 'Item removido com sucesso'}), 200
        
    except Exception as e:
        print(f"Erro ao remover item da comanda: {str(e)}")
        return jsonify({'error': f'Erro ao remover item da comanda: {str(e)}'}), 500


@app.route('/api/comandas/<int:comanda_id>/fechar', methods=['POST'])
def fechar_comanda(comanda_id):
    """Fecha a comanda e registra as vendas"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # Buscar comanda
        query_comanda = 'SELECT id, mesa_id, status FROM comandas WHERE id = %s' if is_postgres else 'SELECT id, mesa_id, status FROM comandas WHERE id = ?'
        cursor.execute(query_comanda, (comanda_id,))
        comanda = cursor.fetchone()
        
        if not comanda:
            return jsonify({'error': 'Comanda não encontrada'}), 404
        
        comanda_dict = {'id': comanda['id'], 'mesa_id': comanda['mesa_id'], 'status': comanda['status']} if isinstance(comanda, dict) else {'id': comanda[0], 'mesa_id': comanda[1], 'status': comanda[2]}
        
        if comanda_dict['status'] != 'aberta':
            return jsonify({'error': 'Comanda não está aberta'}), 400
        
        # Buscar itens da comanda
        query_itens = 'SELECT produto_id, quantidade FROM itens_comanda WHERE comanda_id = %s' if is_postgres else 'SELECT produto_id, quantidade FROM itens_comanda WHERE comanda_id = ?'
        cursor.execute(query_itens, (comanda_id,))
        itens = cursor.fetchall()
        
        # Registrar vendas para cada item
        for item in itens:
            item_dict = {'produto_id': item['produto_id'], 'quantidade': item['quantidade']} if isinstance(item, dict) else {'produto_id': item[0], 'quantidade': item[1]}
            
            if is_postgres:
                cursor.execute(
                    'INSERT INTO vendas (produto_id, quantidade_vendida) VALUES (%s, %s)',
                    (item_dict['produto_id'], item_dict['quantidade'])
                )
            else:
                cursor.execute(
                    'INSERT INTO vendas (produto_id, quantidade_vendida) VALUES (?, ?)',
                    (item_dict['produto_id'], item_dict['quantidade'])
                )
        
        # Fechar comanda
        query_fechar = 'UPDATE comandas SET status = %s, data_fechamento = CURRENT_TIMESTAMP WHERE id = %s' if is_postgres else 'UPDATE comandas SET status = ?, data_fechamento = CURRENT_TIMESTAMP WHERE id = ?'
        cursor.execute(query_fechar, ('fechada', comanda_id))
        
        # Liberar mesa
        query_liberar_mesa = 'UPDATE mesas SET status = %s WHERE id = %s' if is_postgres else 'UPDATE mesas SET status = ? WHERE id = ?'
        cursor.execute(query_liberar_mesa, ('disponivel', comanda_dict['mesa_id']))
        
        db.commit()
        
        return jsonify({'message': 'Comanda fechada com sucesso'}), 200
        
    except Exception as e:
        print(f"Erro ao fechar comanda: {str(e)}")
        return jsonify({'error': f'Erro ao fechar comanda: {str(e)}'}), 500


@app.route('/api/comandas/<int:comanda_id>/cancelar', methods=['POST'])
def cancelar_comanda(comanda_id):
    """Cancela a comanda sem registrar vendas"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # Buscar comanda
        query_comanda = 'SELECT id, mesa_id, status FROM comandas WHERE id = %s' if is_postgres else 'SELECT id, mesa_id, status FROM comandas WHERE id = ?'
        cursor.execute(query_comanda, (comanda_id,))
        comanda = cursor.fetchone()
        
        if not comanda:
            return jsonify({'error': 'Comanda não encontrada'}), 404
        
        comanda_dict = {'id': comanda['id'], 'mesa_id': comanda['mesa_id'], 'status': comanda['status']} if isinstance(comanda, dict) else {'id': comanda[0], 'mesa_id': comanda[1], 'status': comanda[2]}
        
        if comanda_dict['status'] != 'aberta':
            return jsonify({'error': 'Comanda não está aberta'}), 400
        
        # Cancelar comanda
        query_cancelar = 'UPDATE comandas SET status = %s, data_fechamento = CURRENT_TIMESTAMP WHERE id = %s' if is_postgres else 'UPDATE comandas SET status = ?, data_fechamento = CURRENT_TIMESTAMP WHERE id = ?'
        cursor.execute(query_cancelar, ('cancelada', comanda_id))
        
        # Liberar mesa
        query_liberar_mesa = 'UPDATE mesas SET status = %s WHERE id = %s' if is_postgres else 'UPDATE mesas SET status = ? WHERE id = ?'
        cursor.execute(query_liberar_mesa, ('disponivel', comanda_dict['mesa_id']))
        
        db.commit()
        
        return jsonify({'message': 'Comanda cancelada com sucesso'}), 200
        
    except Exception as e:
        print(f"Erro ao cancelar comanda: {str(e)}")
        return jsonify({'error': f'Erro ao cancelar comanda: {str(e)}'}), 500

# ========================================
# ROTAS DE ESTATÍSTICAS E DASHBOARD
# ========================================

@app.route('/dashboard/estatisticas', methods=['GET'])
def get_estatisticas_dashboard():
    """Retorna estatísticas gerais para o dashboard"""
    try:
        db = get_db()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # Total de vendas (últimos 30 dias)
        query_vendas = """
            SELECT COUNT(*) as total_vendas, 
                   SUM(v.quantidade_vendida) as total_produtos_vendidos,
                   SUM(v.quantidade_vendida * p.preco_venda) as receita_total
            FROM vendas v
            JOIN produtos p ON v.produto_id = p.id
            WHERE v.data_venda >= CURRENT_DATE - INTERVAL '30 days'
        """ if is_postgres else """
            SELECT COUNT(*) as total_vendas,
                   SUM(v.quantidade_vendida) as total_produtos_vendidos,
                   SUM(v.quantidade_vendida * p.preco_venda) as receita_total
            FROM vendas v
            JOIN produtos p ON v.produto_id = p.id
            WHERE v.data_venda >= date('now', '-30 days')
        """
        
        cursor.execute(query_vendas)
        stats_vendas = dict(cursor.fetchone())
        
        # Total de produtos cadastrados
        cursor.execute("SELECT COUNT(*) as total FROM produtos")
        total_produtos = dict(cursor.fetchone())['total']
        
        # Total de insumos cadastrados
        cursor.execute("SELECT COUNT(*) as total FROM insumos")
        total_insumos = dict(cursor.fetchone())['total']
        
        # Insumos com estoque baixo (menos de 10 unidades)
        cursor.execute("SELECT COUNT(*) as total FROM insumos WHERE estoque_atual < 10")
        insumos_baixo_estoque = dict(cursor.fetchone())['total']
        
        return jsonify({
            'vendas_30_dias': stats_vendas['total_vendas'] or 0,
            'produtos_vendidos_30_dias': stats_vendas['total_produtos_vendidos'] or 0,
            'receita_30_dias': float(stats_vendas['receita_total'] or 0),
            'total_produtos': total_produtos,
            'total_insumos': total_insumos,
            'alertas_estoque_baixo': insumos_baixo_estoque
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar estatísticas: {str(e)}'}), 500


@app.route('/dashboard/produtos-mais-vendidos', methods=['GET'])
def get_produtos_mais_vendidos():
    """Retorna os produtos mais vendidos (últimos 30 dias)"""
    try:
        db = get_db()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        query = """
            SELECT p.id, p.nome, 
                   SUM(v.quantidade_vendida) as total_vendido,
                   SUM(v.quantidade_vendida * p.preco_venda) as receita_produto
            FROM vendas v
            JOIN produtos p ON v.produto_id = p.id
            WHERE v.data_venda >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY p.id, p.nome
            ORDER BY total_vendido DESC
            LIMIT 10
        """ if is_postgres else """
            SELECT p.id, p.nome,
                   SUM(v.quantidade_vendida) as total_vendido,
                   SUM(v.quantidade_vendida * p.preco_venda) as receita_produto
            FROM vendas v
            JOIN produtos p ON v.produto_id = p.id
            WHERE v.data_venda >= date('now', '-30 days')
            GROUP BY p.id, p.nome
            ORDER BY total_vendido DESC
            LIMIT 10
        """
        
        cursor.execute(query)
        produtos = cursor.fetchall()
        
        produtos_list = []
        for p in produtos:
            produto_dict = dict(p) if not isinstance(p, dict) else p
            produtos_list.append({
                'id': produto_dict['id'],
                'nome': produto_dict['nome'],
                'total_vendido': produto_dict['total_vendido'],
                'receita': float(produto_dict['receita_produto'])
            })
        
        return jsonify(produtos_list), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar produtos mais vendidos: {str(e)}'}), 500


@app.route('/dashboard/estoque-baixo', methods=['GET'])
def get_estoque_baixo():
    """Retorna insumos com estoque baixo (menos de 10 unidades)"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        query = """
            SELECT id, nome, unidade_medida, estoque_atual
            FROM insumos
            WHERE estoque_atual < 10
            ORDER BY estoque_atual ASC
        """
        
        cursor.execute(query)
        insumos = cursor.fetchall()
        
        insumos_list = []
        for i in insumos:
            insumo_dict = dict(i) if not isinstance(i, dict) else i
            insumos_list.append({
                'id': insumo_dict['id'],
                'nome': insumo_dict['nome'],
                'unidade_medida': insumo_dict['unidade_medida'],
                'estoque_atual': float(insumo_dict['estoque_atual'])
            })
        
        return jsonify(insumos_list), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar estoque baixo: {str(e)}'}), 500


@app.route('/dashboard/vendas-por-dia', methods=['GET'])
def get_vendas_por_dia():
    """Retorna vendas agrupadas por dia (últimos 7 dias)"""
    try:
        db = get_db()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        query = """
            SELECT DATE(v.data_venda) as dia,
                   COUNT(*) as total_vendas,
                   SUM(v.quantidade_vendida * p.preco_venda) as receita_dia
            FROM vendas v
            JOIN produtos p ON v.produto_id = p.id
            WHERE v.data_venda >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(v.data_venda)
            ORDER BY dia ASC
        """ if is_postgres else """
            SELECT DATE(v.data_venda) as dia,
                   COUNT(*) as total_vendas,
                   SUM(v.quantidade_vendida * p.preco_venda) as receita_dia
            FROM vendas v
            JOIN produtos p ON v.produto_id = p.id
            WHERE v.data_venda >= date('now', '-7 days')
            GROUP BY DATE(v.data_venda)
            ORDER BY dia ASC
        """
        
        cursor.execute(query)
        vendas = cursor.fetchall()
        
        vendas_list = []
        for v in vendas:
            venda_dict = dict(v) if not isinstance(v, dict) else v
            vendas_list.append({
                'dia': str(venda_dict['dia']),
                'total_vendas': venda_dict['total_vendas'],
                'receita': float(venda_dict['receita_dia'])
            })
        
        return jsonify(vendas_list), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar vendas por dia: {str(e)}'}), 500
# ==================== INSUMOS ====================

@app.route('/insumos', methods=['GET'])
def listar_insumos():
    """Listar todos os insumos"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, nome, unidade_medida, quantidade_estoque, 
                   estoque_minimo, preco_unitario, fornecedor
            FROM insumos
            ORDER BY nome
        ''')
        
        insumos = []
        for row in cursor.fetchall():
            insumos.append({
                'id': row[0],
                'nome': row[1],
                'unidade_medida': row[2],
                'quantidade_estoque': row[3],
                'estoque_minimo': row[4],
                'preco_unitario': row[5],
                'fornecedor': row[6]
            })
        
        conn.close()
        return jsonify(insumos), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/insumos', methods=['POST'])
def cadastrar_insumo():
    """Cadastrar novo insumo"""
    try:
        data = request.json
        nome = data.get('nome')
        unidade_medida = data.get('unidade_medida')
        quantidade_estoque = data.get('quantidade_estoque', 0)
        estoque_minimo = data.get('estoque_minimo', 0)
        preco_unitario = data.get('preco_unitario', 0)
        fornecedor = data.get('fornecedor', '')
        
        if not nome or not unidade_medida:
            return jsonify({'error': 'Nome e unidade de medida são obrigatórios'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO insumos (nome, unidade_medida, quantidade_estoque, 
                               estoque_minimo, preco_unitario, fornecedor)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (nome, unidade_medida, quantidade_estoque, estoque_minimo, 
              preco_unitario, fornecedor))
        
        conn.commit()
        insumo_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'id': insumo_id,
            'nome': nome,
            'unidade_medida': unidade_medida,
            'quantidade_estoque': quantidade_estoque,
            'estoque_minimo': estoque_minimo,
            'preco_unitario': preco_unitario,
            'fornecedor': fornecedor
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/insumos/<int:insumo_id>', methods=['PUT'])
def atualizar_insumo(insumo_id):
    """Atualizar insumo existente"""
    try:
        data = request.json
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE insumos 
            SET nome = ?, unidade_medida = ?, quantidade_estoque = ?,
                estoque_minimo = ?, preco_unitario = ?, fornecedor = ?
            WHERE id = ?
        ''', (data.get('nome'), data.get('unidade_medida'), 
              data.get('quantidade_estoque'), data.get('estoque_minimo'),
              data.get('preco_unitario'), data.get('fornecedor'), insumo_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Insumo atualizado com sucesso'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/insumos/<int:insumo_id>', methods=['DELETE'])
def deletar_insumo(insumo_id):
    """Deletar insumo"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM insumos WHERE id = ?', (insumo_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Insumo deletado com sucesso'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import os
    # Só inicializa o banco se ele não existir
    if not os.path.exists(DATABASE):
        with app.app_context():
            init_db()
            print("⚠️  Banco de dados criado pela primeira vez!")
    else:
        print("✅ Banco de dados já existe. Usando o banco existente.")
    
    app.run(debug=True, host='0.0.0.0', port=5000)