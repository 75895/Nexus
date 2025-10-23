DROP TABLE IF EXISTS insumos;
DROP TABLE IF EXISTS produtos;
DROP TABLE IF EXISTS ficha_tecnica;
DROP TABLE IF EXISTS vendas;
DROP TABLE IF EXISTS usuarios;

CREATE TABLE insumos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    unidade_medida TEXT NOT NULL,
    estoque_atual REAL NOT NULL DEFAULT 0
);

CREATE TABLE produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    preco_venda REAL NOT NULL
);

CREATE TABLE ficha_tecnica (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER NOT NULL,
    insumo_id INTEGER NOT NULL,
    quantidade_necessaria REAL NOT NULL,
    FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE CASCADE,
    FOREIGN KEY (insumo_id) REFERENCES insumos (id) ON DELETE CASCADE
);

CREATE TABLE vendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER NOT NULL,
    quantidade_vendida INTEGER NOT NULL,
    data_venda TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE CASCADE
);

-- Nova tabela para armazenar usuários com senhas seguras
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    data_criacao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
