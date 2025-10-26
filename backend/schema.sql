-- ========================================
-- RESET E TABELAS PRINCIPAIS (ORDEM CORRIGIDA FINAL)
-- Excluir tabelas dependentes ANTES das tabelas principais.
-- ========================================

DROP TABLE IF EXISTS ficha_itens; -- Novo!
DROP TABLE IF EXISTS fichas_tecnicas; -- Novo!
DROP TABLE IF EXISTS comanda_itens;
DROP TABLE IF EXISTS vendas;
DROP TABLE IF EXISTS comandas;
DROP TABLE IF EXISTS mesas;
DROP TABLE IF EXISTS insumos;
DROP TABLE IF EXISTS produtos;
DROP TABLE IF EXISTS usuarios;

-- ========================================
-- CRIAÇÃO DE TABELAS
-- ========================================

CREATE TABLE insumos (
    id SERIAL PRIMARY KEY, 
    nome TEXT NOT NULL UNIQUE, -- Adicionado UNIQUE
    unidade_medida TEXT NOT NULL,
    quantidade_estoque REAL NOT NULL DEFAULT 0.0,
    estoque_minimo REAL NOT NULL DEFAULT 0.0,
    preco_unitario REAL NOT NULL DEFAULT 0.0,
    fornecedor TEXT
);

CREATE TABLE produtos (
    id SERIAL PRIMARY KEY, 
    nome TEXT NOT NULL UNIQUE, -- Adicionado UNIQUE
    preco_venda REAL NOT NULL
);

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY, 
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    -- CORREÇÃO: Usar tipo TIMESTAMP nativo
    data_criacao TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- FICHAS TÉCNICAS (ESTRUTURA CORRIGIDA para 1:N)
-- ========================================

CREATE TABLE fichas_tecnicas ( -- Tabela Principal da Ficha
    id SERIAL PRIMARY KEY,
    produto_id INTEGER NOT NULL UNIQUE, -- Uma ficha por produto
    nome TEXT,
    descricao TEXT,
    FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE CASCADE
);

CREATE TABLE ficha_itens ( -- Tabela de Insumos da Ficha
    id SERIAL PRIMARY KEY,
    ficha_id INTEGER NOT NULL,
    insumo_id INTEGER NOT NULL,
    quantidade_necessaria REAL NOT NULL,
    FOREIGN KEY (ficha_id) REFERENCES fichas_tecnicas (id) ON DELETE CASCADE,
    FOREIGN KEY (insumo_id) REFERENCES insumos (id) ON DELETE RESTRICT,
    UNIQUE (ficha_id, insumo_id) -- Garante que um insumo só aparece uma vez na mesma ficha
);

-- ========================================
-- TABELAS PDV/COMANDAS/MESAS
-- ========================================

CREATE TABLE mesas (
    id SERIAL PRIMARY KEY, 
    numero INTEGER NOT NULL UNIQUE,
    capacidade INTEGER NOT NULL,
    localizacao TEXT,
    -- Status pode ser 'disponivel', 'ocupada', 'suja', 'reservada'
    status TEXT NOT NULL DEFAULT 'disponivel' 
);

CREATE TABLE comandas (
    id SERIAL PRIMARY KEY, 
    mesa_id INTEGER NOT NULL,
    -- CORREÇÃO: Usar tipo TIMESTAMP nativo
    data_abertura TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    data_fechamento TIMESTAMP WITHOUT TIME ZONE,
    -- Status pode ser 'aberta', 'paga', 'cancelada'
    status TEXT NOT NULL DEFAULT 'aberta', 
    total REAL NOT NULL DEFAULT 0.00,
    FOREIGN KEY (mesa_id) REFERENCES mesas (id) ON DELETE RESTRICT
);

CREATE TABLE comanda_itens (
    id SERIAL PRIMARY KEY, 
    comanda_id INTEGER NOT NULL,
    produto_id INTEGER NOT NULL,
    quantidade INTEGER NOT NULL,
    preco_unitario REAL NOT NULL, 
    observacoes TEXT,
    FOREIGN KEY (comanda_id) REFERENCES comandas (id) ON DELETE CASCADE,
    FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE RESTRICT
);

-- ========================================
-- TABELA VENDAS (Corrigida a restrição)
-- ========================================

CREATE TABLE vendas (
    id SERIAL PRIMARY KEY, 
    
    -- Rastreamento da Origem
    comanda_id INTEGER UNIQUE NOT NULL, -- CRÍTICO: comanda_id deve ser UNIQUE e NOT NULL na venda
    
    -- Campos de Pagamento 
    valor_total REAL NOT NULL,
    valor_pago REAL NOT NULL,
    troco REAL NOT NULL DEFAULT 0.00,
    metodo_pagamento TEXT NOT NULL, 
    
    -- CORREÇÃO: Usar tipo TIMESTAMP nativo
    data_venda TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    observacoes TEXT,
    
    -- CRÍTICO: Garantir integridade referencial com RESTRICT
    FOREIGN KEY (comanda_id) REFERENCES comandas (id) ON DELETE RESTRICT
);