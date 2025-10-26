import os
import sqlite3
from flask import Flask, jsonify, request, g
from flask_cors import CORS
import bcrypt

app = Flask(__name__)

# ========================================
# CONFIGURAÇÃO DE CORS CORRIGIDA
# Permite explicitamente a origem do seu frontend no GitHub Pages
# ========================================
CORS(app, resources={
    r"/*": {
        "origins": "https://75895.github.io",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

DATABASE = 'restaurante.db'

def get_db_connection():
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
    """Inicializa o banco de dados com o schema"""
    with app.app_context():
        db = get_db_connection()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def migrar_tabela_insumos():
    """Adiciona colunas faltantes na tabela insumos"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Tenta adicionar as colunas (se já existirem, vai dar erro mas não tem problema)
        try:
            cursor.execute("ALTER TABLE insumos ADD COLUMN quantidade_estoque REAL DEFAULT 0")
            print("✅ Coluna quantidade_estoque adicionada")
        except:
            print("⚠️ Coluna quantidade_estoque já existe")
        
        try:
            cursor.execute("ALTER TABLE insumos ADD COLUMN estoque_minimo REAL DEFAULT 0")
            print("✅ Coluna estoque_minimo adicionada")
        except:
            print("⚠️ Coluna estoque_minimo já existe")
        
        try:
            cursor.execute("ALTER TABLE insumos ADD COLUMN preco_unitario REAL DEFAULT 0")
            print("✅ Coluna preco_unitario adicionada")
        except:
            print("⚠️ Coluna preco_unitario já existe")
        
        try:
            cursor.execute("ALTER TABLE insumos ADD COLUMN fornecedor TEXT")
            print("✅ Coluna fornecedor adicionada")
        except:
            print("⚠️ Coluna fornecedor já existe")
        
        conn.commit()
    except Exception as e:
        print(f"❌ Erro na migração: {e}")

@app.teardown_appcontext
def close_connection(exception):
    """Fecha a conexão com o banco ao final de cada requisição"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

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
        db = get_db_connection()
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
# ROTAS DE INSUMOS
# ========================================

@app.route('/api/insumos', methods=['GET'])
def get_insumos():
    """Lista todos os insumos"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute('''
    SELECT id, nome, unidade_medida, estoque_atual 
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

# Rota de adicionar insumo corrigida para ter o prefixo /api
@app.route('/api/insumos', methods=['POST']) 
def add_insumo():
    """Adiciona um novo insumo"""
    try:
        data = request.get_json()
        
        if not data or 'nome' not in data or 'unidade_medida' not in data:
            return jsonify({'error': 'Nome e unidade de medida são obrigatórios'}), 400
        
        nome = data['nome'].strip()
        unidade_medida = data['unidade_medida'].strip()
        # Garantir que estoque_atual seja um float, com 0 como padrão seguro
        estoque_atual = float(data.get('estoque_atual', 0))
        
        if not nome or not unidade_medida:
            return jsonify({'error': 'Nome e unidade de medida não podem estar vazios'}), 400
        
        if estoque_atual < 0:
            return jsonify({'error': 'Estoque não pode ser negativo'}), 400
        
        db = get_db_connection()
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
        if 'estoque_atual' in data:
             # Garante que o valor é numérico e não negativo
            estoque_atual = float(data['estoque_atual'])
            if estoque_atual < 0:
                return jsonify({'error': 'Estoque não pode ser negativo'}), 400
            updates.append('estoque_atual = %s' if is_postgres else 'estoque_atual = ?')
            values.append(estoque_atual)
            
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
        return jsonify({'error': f'Erro ao remover insumo: {str(e)}'}), 500


# ========================================
# ROTAS DE PRODUTOS
# ========================================

@app.route('/produtos', methods=['GET'])
def get_produtos():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute('SELECT id, nome, preco_venda FROM produtos')
    produtos = cursor.fetchall()
    return jsonify([dict(row) for row in produtos])

@app.route('/produtos', methods=['POST'])
def add_produto():
    """Adiciona um novo produto"""
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
    db = get_db_connection()
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
        
        db = get_db_connection()
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

    db = get_db_connection()
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
        db = get_db_connection()
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
        
        db = get_db_connection()
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
        
        db = get_db_connection()
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
        db = get_db_connection()
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
        
        db = get_db_connection()
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
        db = get_db_connection()
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

# ========================================
# NOVAS ROTAS DE DASHBOARD E ESTATÍSTICAS
# ========================================

@app.route('/api/par/estatisticas', methods=['GET'])
def get_estatisticas_gerais():
    """Retorna dados gerais para o Dashboard (como vendas nos últimos 30 dias)"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # Receita 30 dias
        if is_postgres:
            query_vendas_30_dias = '''
                SELECT SUM(total) as receita
                FROM comandas
                WHERE status = 'fechada' AND data_fechamento >= NOW() - INTERVAL '30 days'
            '''
            cursor.execute(query_vendas_30_dias)
        else:
            query_vendas_30_dias = '''
                SELECT SUM(total) as receita
                FROM comandas
                WHERE status = 'fechada' AND data_fechamento >= strftime('%Y-%m-%d %H:%M:%S', date('now', '-30 days'))
            '''
            cursor.execute(query_vendas_30_dias)
            
        receita = cursor.fetchone()
        receita_30_dias = float(receita['receita']) if receita and receita['receita'] else 0.0

        return jsonify({
            'receita_30_dias': round(receita_30_dias, 2),
            # Adicionar outras estatísticas conforme o frontend precisar
        }), 200

    except Exception as e:
        print(f"Erro ao buscar estatísticas gerais: {str(e)}")
        return jsonify({'error': f'Erro ao buscar estatísticas gerais: {str(e)}'}), 500

@app.route('/api/vendas/por-dia', methods=['GET'])
def get_vendas_por_dia():
    """Retorna o total de vendas por dia (ex: últimos 7 dias)"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None

        if is_postgres:
            # PostgreSQL
            query = '''
                SELECT 
                    DATE(data_fechamento) as dia,
                    SUM(total) as total_dia
                FROM comandas
                WHERE status = 'fechada' AND data_fechamento >= NOW() - INTERVAL '7 days'
                GROUP BY 1
                ORDER BY 1;
            '''
            cursor.execute(query)
        else:
            # SQLite
            query = '''
                SELECT 
                    strftime('%Y-%m-%d', data_fechamento) as dia,
                    SUM(total) as total_dia
                FROM comandas
                WHERE status = 'fechada' AND data_fechamento >= strftime('%Y-%m-%d %H:%M:%S', date('now', '-7 days'))
                GROUP BY 1
                ORDER BY 1;
            '''
            cursor.execute(query)

        vendas = cursor.fetchall()
        return jsonify([{
            'dia': row['dia'], 
            'total': float(row['total_dia'])
        } for row in vendas]), 200

    except Exception as e:
        print(f"Erro ao buscar vendas por dia: {str(e)}")
        return jsonify({'error': f'Erro ao buscar vendas por dia: {str(e)}'}), 500

@app.route('/api/produtos/o-mais-vendidos', methods=['GET'])
def get_mais_vendidos():
    """Retorna os top X produtos mais vendidos (ex: últimos 30 dias)"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        # Retorna o top 5 produtos mais vendidos nas comandas fechadas
        if is_postgres:
            # PostgreSQL
            query = '''
                SELECT 
                    p.nome as produto_nome,
                    SUM(ic.quantidade) as total_vendido
                FROM itens_comanda ic
                JOIN produtos p ON ic.produto_id = p.id
                JOIN comandas c ON ic.comanda_id = c.id
                WHERE c.status = 'fechada' AND c.data_fechamento >= NOW() - INTERVAL '30 days'
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 5;
            '''
        else:
            # SQLite
            query = '''
                SELECT 
                    p.nome as produto_nome,
                    SUM(ic.quantidade) as total_vendido
                FROM itens_comanda ic
                JOIN produtos p ON ic.produto_id = p.id
                JOIN comandas c ON ic.comanda_id = c.id
                WHERE c.status = 'fechada' AND c.data_fechamento >= strftime('%Y-%m-%d %H:%M:%S', date('now', '-30 days'))
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 5;
            '''
        
        cursor.execute(query)
        vendidos = cursor.fetchall()
        return jsonify([dict(row) for row in vendidos]), 200
        
    except Exception as e:
        print(f"Erro ao buscar mais vendidos: {str(e)}")
        return jsonify({'error': f'Erro ao buscar mais vendidos: {str(e)}'}), 500

@app.route('/api/insumos/estoque-baixo', methods=['GET'])
def get_insumos_estoque_baixo():
    """Retorna insumos com estoque abaixo de um limite mínimo (assumindo estoque_minimo)"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Esta rota depende que você tenha a coluna `estoque_minimo` na tabela `insumos`
        query = '''
            SELECT id, nome, estoque_atual, estoque_minimo, unidade_medida
            FROM insumos
            WHERE estoque_atual <= estoque_minimo AND estoque_minimo > 0
            ORDER BY estoque_atual ASC;
        '''
        
        cursor.execute(query)
        insumos = cursor.fetchall()
        return jsonify([dict(row) for row in insumos]), 200
        
    except Exception as e:
        # Se a tabela insumos não tiver estoque_minimo (erro no schema), esta exceção ajuda a diagnosticar.
        print(f"Erro ao buscar estoque baixo: {str(e)}")
        return jsonify({'error': 'Erro ao buscar estoque baixo. Verifique se o schema do banco está atualizado (tabela insumos possui estoque_minimo).'}), 500


if __name__ == '__main__':
    # Este bloco só executa se você rodar o arquivo Python diretamente (localmente)
    # No Render, a inicialização geralmente é feita por um comando Gunicorn/Waitress, mas este bloco é essencial para testar localmente.
    app.run(debug=True)