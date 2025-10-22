
import sqlite3
from flask import Flask, jsonify, request, g
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE = 'restaurante.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # Para retornar linhas como dicionários
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
        print("Banco de dados inicializado com sucesso!")

@app.route('/init_db')
def initialize_db_route():
    try:
        init_db()
        return jsonify({'message': 'Banco de dados inicializado com sucesso!'})
    except Exception as e:
        return jsonify({'error': f'Erro ao inicializar o banco de dados: {e}'}), 500

# --- Rotas de Insumos (Estoque) ---

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
    cursor.execute(
        'INSERT INTO insumos (nome, unidade_medida, estoque_atual) VALUES (?, ?, ?)',
        (nome, unidade_medida, estoque_atual)
    )
    db.commit()
    new_id = cursor.lastrowid
    return jsonify({'id': new_id, 'nome': nome}), 201

@app.route('/insumos/<int:insumo_id>', methods=['PUT'])
def update_insumo(insumo_id):
    data = request.get_json()
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'UPDATE insumos SET nome = ?, unidade_medida = ?, estoque_atual = ? WHERE id = ?',
        (data['nome'], data['unidade_medida'], data['estoque_atual'], insumo_id)
    )
    db.commit()
    return jsonify({'message': 'Insumo atualizado com sucesso'})

@app.route('/insumos/<int:insumo_id>', methods=['DELETE'])
def delete_insumo(insumo_id):
    db = get_db()
    cursor = db.cursor()
    
    # Verifica se o insumo está em alguma ficha técnica antes de excluir
    cursor.execute('SELECT 1 FROM ficha_tecnica WHERE insumo_id = ?', (insumo_id,))
    ficha = cursor.fetchone()
    if ficha:
        return jsonify({'error': 'Não é possível excluir. Este insumo está sendo usado em uma ficha técnica.'}), 400
        
    cursor.execute('DELETE FROM insumos WHERE id = ?', (insumo_id,))
    db.commit()
    return jsonify({'message': 'Insumo excluído com sucesso'}) 

# --- Rotas de Produtos (Cardápio) ---

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
    cursor.execute(
        'INSERT INTO produtos (nome, preco_venda) VALUES (?, ?)',
        (nome, preco_venda)
    )
    db.commit()
    new_id = cursor.lastrowid
    return jsonify({'id': new_id, 'nome': nome}), 201

# --- Rotas de Ficha Técnica ---

@app.route('/fichas_tecnicas/<int:produto_id>', methods=['GET'])
def get_ficha_tecnica(produto_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        '''
        SELECT ft.id, ft.quantidade_necessaria, i.nome as insumo_nome, i.unidade_medida, i.id as insumo_id
        FROM ficha_tecnica ft
        JOIN insumos i ON ft.insumo_id = i.id
        WHERE ft.produto_id = ?
        ''',
        (produto_id,)
    )
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
    cursor.execute(
        'INSERT INTO ficha_tecnica (produto_id, insumo_id, quantidade_necessaria) VALUES (?, ?, ?)',
        (produto_id, insumo_id, quantidade_necessaria)
    )
    db.commit()
    new_id = cursor.lastrowid
    return jsonify({'id': new_id}), 201

# --- Rota de Vendas (PDV - Ponto de Venda) ---

@app.route('/vendas', methods=['POST'])
def registrar_venda_pdv():
    data = request.get_json()
    itens_carrinho = data.get('itens', [])

    if not itens_carrinho:
        return jsonify({'error': 'Carrinho de compras vazio.'}), 400

    db = get_db()
    cursor = db.cursor()

    try:
        # Inicia a transação
        # SQLite gerencia transações implicitamente com commit/rollback
        for item in itens_carrinho:
            produto_id = item['produto_id']
            quantidade_vendida = item['quantidade']

            # 1. Buscar a ficha técnica do produto
            cursor.execute(
                'SELECT insumo_id, quantidade_necessaria FROM ficha_tecnica WHERE produto_id = ?',
                (produto_id,)
            )
            ficha_tecnica = cursor.fetchall()

            if not ficha_tecnica:
                raise ValueError(f'Produto ID {produto_id} sem ficha técnica cadastrada.')

            # 2. Para cada insumo, verificar e dar baixa no estoque
            for row in ficha_tecnica:
                insumo_id = row['insumo_id']
                necessario_por_unidade = row['quantidade_necessaria']
                necessario_total = necessario_por_unidade * quantidade_vendida

                cursor.execute(
                    'SELECT nome, estoque_atual FROM insumos WHERE id = ?',
                    (insumo_id,)
                )
                resultado_insumo = cursor.fetchone()
                if resultado_insumo is None:
                    raise ValueError(f"Insumo ID {insumo_id} não encontrado.")

                insumo_nome = resultado_insumo['nome']
                estoque_atual = resultado_insumo['estoque_atual']

                if estoque_atual < necessario_total:
                    raise ValueError(f'Estoque insuficiente para o insumo: "{insumo_nome}". Necessário: {necessario_total}, Disponível: {estoque_atual}')

                # Realiza a baixa
                cursor.execute(
                    'UPDATE insumos SET estoque_atual = estoque_atual - ? WHERE id = ?',
                    (necessario_total, insumo_id)
                )
            
            # 3. Registrar a venda
            cursor.execute(
                'INSERT INTO vendas (produto_id, quantidade_vendida, data_venda) VALUES (?, ?, CURRENT_TIMESTAMP)',
                (produto_id, quantidade_vendida)
            )
        
        db.commit()
        return jsonify({'message': 'Venda registrada e estoque atualizado com sucesso!'}), 200

    except (Exception, ValueError) as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        init_db() # Inicializa o DB na primeira execução, se não existir
    app.run(debug=True, host='0.0.0.0', port=5000)

