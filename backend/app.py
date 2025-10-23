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

# ========================================
# ROTAS DE INSUMOS
# ========================================

@app.route('/insumos', methods=['GET'])
def get_insumos():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, nome, unidade_medida, estoque_atual FROM insumos')
    insumos = cursor.fetchall()
    return jsonify([dict(row) for row in insumos])

@app.route('/insumos', methods=['POST'])
def add_insumo():
    data = request.get_json()
    nome = data['nome']
    unidade_medida = data['unidade_medida']
    estoque_atual = data.get('estoque_atual', 0)
    
    db = get_db()
    cursor = db.cursor()
    
    is_postgres = os.environ.get('DATABASE_URL') is not None
    if is_postgres:
        cursor.execute(
            'INSERT INTO insumos (nome, unidade_medida, estoque_atual) VALUES (%s, %s, %s) RETURNING id',
            (nome, unidade_medida, estoque_atual)
        )
        new_id = cursor.fetchone()[0]
    else:
        cursor.execute(
            'INSERT INTO insumos (nome, unidade_medida, estoque_atual) VALUES (?, ?, ?)',
            (nome, unidade_medida, estoque_atual)
        )
        new_id = cursor.lastrowid
    
    db.commit()
    return jsonify({'id': new_id, 'nome': nome}), 201

@app.route('/insumos/<int:insumo_id>', methods=['PUT'])
def update_insumo(insumo_id):
    data = request.get_json()
    db = get_db()
    cursor = db.cursor()
    
    is_postgres = os.environ.get('DATABASE_URL') is not None
    query = 'UPDATE insumos SET nome = %s, unidade_medida = %s, estoque_atual = %s WHERE id = %s' if is_postgres else 'UPDATE insumos SET nome = ?, unidade_medida = ?, estoque_atual = ? WHERE id = ?'
    
    cursor.execute(query, (data['nome'], data['unidade_medida'], data['estoque_atual'], insumo_id))
    db.commit()
    return jsonify({'message': 'Insumo atualizado com sucesso'})

@app.route('/insumos/<int:insumo_id>', methods=['DELETE'])
def delete_insumo(insumo_id):
    db = get_db()
    cursor = db.cursor()
    
    is_postgres = os.environ.get('DATABASE_URL') is not None
    query_check = 'SELECT 1 FROM ficha_tecnica WHERE insumo_id = %s' if is_postgres else 'SELECT 1 FROM ficha_tecnica WHERE insumo_id = ?'
    query_delete = 'DELETE FROM insumos WHERE id = %s' if is_postgres else 'DELETE FROM insumos WHERE id = ?'
    
    cursor.execute(query_check, (insumo_id,))
    ficha = cursor.fetchone()
    if ficha:
        return jsonify({'error': 'Não é possível excluir. Este insumo está sendo usado em uma ficha técnica.'}), 400
        
    cursor.execute(query_delete, (insumo_id,))
    db.commit()
    return jsonify({'message': 'Insumo excluído com sucesso'})

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
    data = request.get_json()
    nome = data['nome']
    preco_venda = data['preco_venda']
    
    db = get_db()
    cursor = db.cursor()
    
    is_postgres = os.environ.get('DATABASE_URL') is not None
    if is_postgres:
        cursor.execute(
            'INSERT INTO produtos (nome, preco_venda) VALUES (%s, %s) RETURNING id',
            (nome, preco_venda)
        )
        new_id = cursor.fetchone()[0]
    else:
        cursor.execute(
            'INSERT INTO produtos (nome, preco_venda) VALUES (?, ?)',
            (nome, preco_venda)
        )
        new_id = cursor.lastrowid
    
    db.commit()
    return jsonify({'id': new_id, 'nome': nome}), 201

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
    data = request.get_json()
    produto_id = data['produto_id']
    insumo_id = data['insumo_id']
    quantidade_necessaria = data['quantidade_necessaria']
    
    db = get_db()
    cursor = db.cursor()
    
    is_postgres = os.environ.get('DATABASE_URL') is not None
    if is_postgres:
        cursor.execute(
            'INSERT INTO ficha_tecnica (produto_id, insumo_id, quantidade_necessaria) VALUES (%s, %s, %s) RETURNING id',
            (produto_id, insumo_id, quantidade_necessaria)
        )
        new_id = cursor.fetchone()[0]
    else:
        cursor.execute(
            'INSERT INTO ficha_tecnica (produto_id, insumo_id, quantidade_necessaria) VALUES (?, ?, ?)',
            (produto_id, insumo_id, quantidade_necessaria)
        )
        new_id = cursor.lastrowid
    
    db.commit()
    return jsonify({'id': new_id}), 201

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
