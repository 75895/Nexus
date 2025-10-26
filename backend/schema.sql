-- ========================================
-- RESET E TABELAS PRINCIPAIS (INALTERADAS)
-- ========================================

DROP TABLE IF EXISTS insumos;
DROP TABLE IF EXISTS produtos;
DROP TABLE IF EXISTS ficha_tecnica;
DROP TABLE IF EXISTS comanda_itens; -- NOVA TABELA
DROP TABLE IF EXISTS comandas;      -- NOVA TABELA
DROP TABLE IF EXISTS mesas;         -- NOVA TABELA
DROP TABLE IF EXISTS vendas;        -- TABELA ALTERADA
DROP TABLE IF EXISTS usuarios;

CREATE TABLE insumos (
    id SERIAL PRIMARY KEY, -- Forma padrão para PostgreSQL
-- ou: id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    unidade_medida TEXT NOT NULL,
    quantidade_estoque REAL NOT NULL DEFAULT 0,
    estoque_minimo REAL NOT NULL DEFAULT 0,
    preco_unitario REAL NOT NULL DEFAULT 0,
    fornecedor TEXT
);

CREATE TABLE produtos (
    id SERIAL PRIMARY KEY, -- Forma padrão para PostgreSQL
-- ou: id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    preco_venda REAL NOT NULL
);

CREATE TABLE ficha_tecnica (
    id SERIAL PRIMARY KEY, -- Forma padrão para PostgreSQL
-- ou: id INTEGER PRIMARY KEY,
    produto_id INTEGER NOT NULL,
    insumo_id INTEGER NOT NULL,
    quantidade_necessaria REAL NOT NULL,
    FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE CASCADE,
    FOREIGN KEY (insumo_id) REFERENCES insumos (id) ON DELETE CASCADE
);

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY, -- Forma padrão para PostgreSQL
-- ou: id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    data_criacao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- NOVAS TABELAS PARA PDV/COMANDAS/MESAS
-- ========================================

CREATE TABLE mesas (
    id SERIAL PRIMARY KEY, -- Forma padrão para PostgreSQL
-- ou: id INTEGER PRIMARY KEY,
    numero INTEGER NOT NULL UNIQUE,
    capacidade INTEGER NOT NULL,
    localizacao TEXT,
    -- Status pode ser 'disponivel', 'ocupada', 'suja'
    status TEXT NOT NULL DEFAULT 'disponivel' 
);

CREATE TABLE comandas (
    id SERIAL PRIMARY KEY, -- Forma padrão para PostgreSQL
-- ou: id INTEGER PRIMARY KEY,
    mesa_id INTEGER NOT NULL,
    data_abertura TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_fechamento TEXT,
    -- Status pode ser 'aberta', 'fechada', 'paga'
    status TEXT NOT NULL DEFAULT 'aberta', 
    total REAL NOT NULL DEFAULT 0.00,
    FOREIGN KEY (mesa_id) REFERENCES mesas (id) ON DELETE RESTRICT
);

CREATE TABLE comanda_itens (
    id SERIAL PRIMARY KEY, -- Forma padrão para PostgreSQL
-- ou: id INTEGER PRIMARY KEY,
    comanda_id INTEGER NOT NULL,
    produto_id INTEGER NOT NULL,
    quantidade INTEGER NOT NULL,
    preco_unitario REAL NOT NULL, -- Preço na hora da inclusão
    observacoes TEXT,
    FOREIGN KEY (comanda_id) REFERENCES comandas (id) ON DELETE CASCADE,
    FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE RESTRICT
);

-- ========================================
-- TABELA VENDAS RESTRUTURADA PARA REGISTRO DE PAGAMENTO FINAL
-- ========================================
-- ATENÇÃO: Esta tabela é onde a rota POST /api/vendas vai inserir o registro final.

CREATE TABLE vendas (
    id SERIAL PRIMARY KEY, -- Forma padrão para PostgreSQL
-- ou: id INTEGER PRIMARY KEY,
    
    -- Campos de Pagamento (Nova Estrutura)
    valor_total REAL NOT NULL,
    valor_pago REAL NOT NULL,
    troco REAL NOT NULL DEFAULT 0.00,
    metodo_pagamento TEXT NOT NULL, 
    
    -- Rastreamento da Origem
    comanda_id INTEGER, -- Permite NULL se for venda PDV rápida sem comanda/mesa
    data_venda TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    observacoes TEXT,
    
    FOREIGN KEY (comanda_id) REFERENCES comandas (id) ON DELETE SET NULL
);