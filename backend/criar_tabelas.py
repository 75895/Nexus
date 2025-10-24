import os
import psycopg2

# Pegar URL do banco de dados do Render
DATABASE_URL = "postgresql://nexus_db_6etf_user:Dl2kDm5JihEQjFQGTool4zoCBPXh1IzQ@dpg-d3t8ib63jp1c738jooa0-a.ohio-postgres.render.com/nexus_db_6etf"

print("Conectando ao banco de dados...")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

print("Criando tabelas...")

# Criar tabela de mesas
cursor.execute("""
CREATE TABLE IF NOT EXISTS mesas (
    id SERIAL PRIMARY KEY,
    numero INTEGER NOT NULL UNIQUE,
    capacidade INTEGER NOT NULL,
    localizacao TEXT,
    status TEXT NOT NULL DEFAULT 'disponivel',
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")
print("✅ Tabela 'mesas' criada!")

# Criar tabela de comandas
cursor.execute("""
CREATE TABLE IF NOT EXISTS comandas (
    id SERIAL PRIMARY KEY,
    mesa_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'aberta',
    total DECIMAL(10,2) DEFAULT 0,
    data_abertura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_fechamento TIMESTAMP,
    FOREIGN KEY (mesa_id) REFERENCES mesas(id) ON DELETE CASCADE
);
""")
print("✅ Tabela 'comandas' criada!")

# Criar tabela de itens_comanda
cursor.execute("""
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
""")
print("✅ Tabela 'itens_comanda' criada!")

conn.commit()
cursor.close()
conn.close()

print("\n🎉 Todas as tabelas foram criadas com sucesso!")
