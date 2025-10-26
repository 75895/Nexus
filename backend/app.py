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

# =================================================================
# FUNÇÃO CRÍTICA CORRIGIDA: INICIALIZAÇÃO DO DB
# Soluciona o erro: 'RealDictCursor' object has no attribute 'executescript'
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
                # SQLite usa executescript()
                cursor.executescript(sql_script)

            db.commit()
            return True
        
        except Exception as e:
            db.rollback() 
            raise e 

@app.route('/init_db')
def initialize_db_route():
    try:
        init_db()
        # migrate_table_insumos() # Não chame a migração aqui, o schema.sql já faz o reset
        return jsonify({'message': 'Banco de dados inicializado com sucesso!'}), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao inicializar o banco de dados: {e}'}), 500

# ========================================
# ROTAS DE AUTENTICAÇÃO (MANTIDAS)
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
# ROTAS DE INSUMOS (CORRIGIDAS)
# ========================================

@app.route('/api/insumos', methods=['GET'])
def get_insumos():
    """Lista todos os insumos"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        # SELECT para buscar as colunas básicas
        cursor.execute('''
    SELECT id, nome, unidade_medida, quantidade_estoque
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
        # Usamos 'quantidade_estoque' que é o nome correto do campo na tabela insumos
        quantidade_estoque = float(data.get('quantidade_estoque', 0))
        
        if not nome or not unidade_medida:
            return jsonify({'error': 'Nome e unidade de medida não podem estar vazios'}), 400
        
        if quantidade_estoque < 0:
            return jsonify({'error': 'Estoque não pode ser negativo'}), 400
        
        db = get_db_connection()
        cursor = db.cursor()
        
        is_postgres = os.environ.get('DATABASE_URL') is not None
        
        if is_postgres:
            # Query ajustada para o que realmente tem na tabela
            cursor.execute(
                'INSERT INTO insumos (nome, unidade_medida, quantidade_estoque) VALUES (%s, %s, %s) RETURNING id, nome, unidade_medida, quantidade_estoque',
                (nome, unidade_medida, quantidade_estoque)
            )
            insumo = dict(cursor.fetchone())
        else:
            cursor.execute(
                'INSERT INTO insumos (nome, unidade_medida, quantidade_estoque) VALUES (?, ?, ?)',
                (nome, unidade_medida, quantidade_estoque)
            )
            new_id = cursor.lastrowid
            insumo = {
                'id': new_id,
                'nome': nome,
                'unidade_medida': unidade_medida,
                'quantidade_estoque': float(quantidade_estoque)
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
        if 'quantidade_estoque' in data:
            # Garante que o valor é numérico e não negativo
            quantidade_estoque = float(data['quantidade_estoque'])
            if quantidade_estoque < 0:
                return jsonify({'error': 'Estoque não pode ser negativo'}), 400
            updates.append('quantidade_estoque = %s' if is_postgres else 'quantidade_estoque = ?')
            values.append(quantidade_estoque)
            
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
# ROTAS DE DASHBOARD/ESTOQUE (CORRIGIDAS)
# ========================================

# NOVA ROTA: Alerta de Estoque Baixo (CORRIGIDA - Resolve Erro 500)
# Renomeada a coluna 'estoque_atual' e removido o 'estoque_minimo' que causa problemas se não estiver no schema
@app.route('/api/estoque-baixo', methods=['GET'])
def estoque_baixo():
    """Retorna a lista de insumos com estoque abaixo do mínimo (ou 10)"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # CORREÇÃO CRÍTICA: Removemos 'estoque_minimo' do SELECT para evitar o erro 500
        # e usamos a coluna correta 'quantidade_estoque' no SELECT e WHERE.
        query = '''
            SELECT id, nome, unidade_medida, quantidade_estoque 
            FROM insumos
            WHERE quantidade_estoque <= 10  -- Usando um threshold seguro (ex: 10)
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
                "estoque_minimo": 10 # Retornamos 10 para o Frontend saber o threshold
            })
            
        return jsonify(alertas_list), 200
    
    except Exception as e:
        print(f"Erro ao buscar estoque baixo: {str(e)}")
        # Retorna 500 com a mensagem de erro para o frontend ver no console
        return jsonify({'error': f'Erro ao buscar alertas de estoque: {str(e)}'}), 500

# NOVA ROTA: Total de Produtos (Para o card "Produtos Cadastrados")
@app.route('/api/produtos/total', methods=['GET'])
def total_produtos():
    """Retorna o número total de produtos cadastrados (Resolve N/A no Dashboard)"""
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

# Rota de Estatísticas (Receita 30 dias) - Endpoint usado pelo Frontend
@app.route('/api/par/estatisticas', methods=['GET'])
def estatisticas_parciais():
    """Retorna estatísticas parciais do dashboard (ex: receita total)"""
    # MOCK DATA para evitar 404/500 se as tabelas de vendas/comandas não tiverem dados.
    return jsonify({"receita_30_dias": 0.00}), 200 

# Rota de Vendas por Dia
@app.route('/api/vendas/por-dia', methods=['GET'])
def vendas_por_dia():
    # MOCK DATA para evitar 404/500.
    return jsonify([]), 200 

# Rota de Produtos Mais Vendidos
@app.route('/api/produtos/o-mais-vendidos', methods=['GET'])
def produtos_mais_vendidos():
    # MOCK DATA para evitar 404/500.
    return jsonify([]), 200

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
def registrar_venda_pdv_estoque():
    data = request.get_json()
    itens_carrinho = data.get('itens', [])
    
    if not itens_carrinho:
        return jsonify({'error': 'Carrinho de compras vazio.'}), 400

    db = get_db_connection()
    cursor = db.cursor()
    
    is_postgres = os.environ.get('DATABASE_URL') is not None

    try:
        # Lógica de Controle de Estoque (Se aplicável)
        for item in itens_carrinho:
            produto_id = item['produto_id']
            quantidade_vendida = item['quantidade']

            query_ficha = 'SELECT insumo_id, quantidade_necessaria FROM ficha_tecnica WHERE produto_id = %s' if is_postgres else 'SELECT insumo_id, quantidade_necessaria FROM ficha_tecnica WHERE produto_id = ?'
            cursor.execute(query_ficha, (produto_id,))
            ficha_tecnica = cursor.fetchall()

            if not ficha_tecnica:
                continue 

            for row in ficha_tecnica:
                row_dict = dict(row) if not isinstance(row, dict) else row
                insumo_id = row_dict['insumo_id']
                necessario_por_unidade = row_dict['quantidade_necessaria']
                necessario_total = necessario_por_unidade * quantidade_vendida

                query_insumo = 'SELECT nome, quantidade_estoque FROM insumos WHERE id = %s' if is_postgres else 'SELECT nome, quantidade_estoque FROM insumos WHERE id = ?'
                cursor.execute(query_insumo, (insumo_id,))
                resultado_insumo = cursor.fetchone()
                
                if resultado_insumo is None:
                    raise ValueError(f"Insumo ID {insumo_id} não encontrado.")

                insumo_dict = dict(resultado_insumo) if not isinstance(resultado_insumo, dict) else resultado_insumo
                insumo_nome = insumo_dict['nome']
                # ATENÇÃO: Mudança de 'estoque_atual' para 'quantidade_estoque'
                estoque_atual = insumo_dict['quantidade_estoque'] 

                if estoque_atual < necessario_total:
                    raise ValueError(f'Estoque insuficiente para o insumo: "{insumo_nome}". Necessário: {necessario_total}, Disponível: {estoque_atual}')

                # ATENÇÃO: Mudança de 'estoque_atual' para 'quantidade_estoque' no UPDATE
                query_update = 'UPDATE insumos SET quantidade_estoque = quantidade_estoque - %s WHERE id = %s' if is_postgres else 'UPDATE insumos SET quantidade_estoque = quantidade_estoque - ? WHERE id = ?'
                cursor.execute(query_update, (necessario_total, insumo_id))
            
            # Registro da Venda
            query_venda = 'INSERT INTO vendas (produto_id, quantidade_vendida, data_venda) VALUES (%s, %s, CURRENT_TIMESTAMP)' if is_postgres else 'INSERT INTO vendas (produto_id, quantidade_vendida, data_venda) VALUES (?, ?, DATETIME("now"))'
            cursor.execute(query_venda, (produto_id, quantidade_vendida))
        
        db.commit()
        return jsonify({'message': 'Venda registrada e estoque atualizado com sucesso!'}), 200

    except (Exception, ValueError) as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500


# ========================================
# ROTA PRINCIPAL: REGISTRAR PAGAMENTO DE COMANDA (PDV)
# ========================================

@app.route('/api/vendas', methods=['POST'])
def registrar_pagamento_comanda():
    """Registra o pagamento de uma venda (ou comanda) e libera a mesa."""
    data = request.get_json()

    # Validação básica dos dados do pagamento
    if not data or 'valor_total' not in data or 'metodo_pagamento' not in data:
        return jsonify({'error': 'Dados de pagamento incompletos.'}), 400

    valor_total = float(data.get('valor_total'))
    valor_pago = float(data.get('valor_pago', valor_total)) # Valor pago é opcional, usa total como padrão
    metodo_pagamento = data.get('metodo_pagamento')
    comanda_id = data.get('comanda_id') # O CAMPO CHAVE
    observacoes = data.get('observacoes', '')
    troco = valor_pago - valor_total

    if valor_pago < valor_total:
        return jsonify({'error': 'Valor pago é insuficiente.'}), 400

    db = get_db_connection()
    cursor = db.cursor()
    is_postgres = os.environ.get('DATABASE_URL') is not None
    
    try:
        # 1. Registro da Venda/Pagamento na tabela 'vendas'
        venda_columns = "valor_total, valor_pago, troco, metodo_pagamento, comanda_id, data_venda, observacoes"
        venda_placeholders = "%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s" if is_postgres else "?, ?, ?, ?, ?, DATETIME('now'), ?"
        venda_values = (valor_total, valor_pago, troco, metodo_pagamento, comanda_id, observacoes)

        query_venda = f"INSERT INTO vendas ({venda_columns}) VALUES ({venda_placeholders})"
        
        # Para PostgreSQL, precisamos do RETURNING ID para confirmar
        if is_postgres:
            query_venda += " RETURNING id"
        
        cursor.execute(query_venda, venda_values)

        if is_postgres:
            venda_id = dict(cursor.fetchone()).get('id')
        else:
            venda_id = cursor.lastrowid
            
        
        # 2. Lógica Condicional para Comanda
        if comanda_id:
            comanda_id = int(comanda_id)
            
            # A) Obter a Mesa ID da Comanda
            query_comanda = "SELECT mesa_id, status FROM comandas WHERE id = %s" if is_postgres else "SELECT mesa_id, status FROM comandas WHERE id = ?"
            cursor.execute(query_comanda, (comanda_id,))
            comanda_db = cursor.fetchone()

            if not comanda_db:
                db.rollback()
                return jsonify({'error': f"Comanda ID {comanda_id} não encontrada."}), 404

            mesa_id = comanda_db['mesa_id']
            comanda_status = comanda_db['status']
            
            if comanda_status == 'aberta':
                 print(f"Aviso: Comanda {comanda_id} ainda estava 'aberta', forçando para 'paga'.")


            # B) Atualizar Status da Comanda para 'paga'
            query_update_comanda = "UPDATE comandas SET status = %s WHERE id = %s" if is_postgres else "UPDATE comandas SET status = ? WHERE id = ?"
            cursor.execute(query_update_comanda, ('paga', comanda_id))
            
            # C) Liberar a Mesa
            query_update_mesa = "UPDATE mesas SET status = %s WHERE id = %s" if is_postgres else "UPDATE mesas SET status = ? WHERE id = ?"
            cursor.execute(query_update_mesa, ('disponivel', mesa_id)) 
            
            
        db.commit()
        return jsonify({
            'message': 'Pagamento registrado com sucesso!', 
            'venda_id': venda_id,
            'comanda_id_paga': comanda_id or None
        }), 201

    except Exception as e:
        db.rollback()
        print(f"Erro na transação de pagamento/comanda: {str(e)}")
        return jsonify({'error': f'Erro na transação de pagamento/comanda: {str(e)}'}), 500

# FIM do código