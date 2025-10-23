"""
Script para cadastrar novos usuários no sistema de restaurante.
Execute este script sempre que precisar criar um novo usuário.

IMPORTANTE: Execute este script a partir da pasta 'backend' do seu projeto.
Comando: python cadastrar_usuario.py
"""

import sqlite3
import bcrypt
import os

# Nome do banco de dados (deve estar na mesma pasta que o app.py)
DATABASE = 'restaurante.db'

def verificar_banco_existe():
    """Verifica se o banco de dados existe."""
    if not os.path.exists(DATABASE):
        print(f"❌ ERRO: O arquivo '{DATABASE}' não foi encontrado!")
        print(f"   Certifique-se de estar executando este script na pasta 'backend'")
        print(f"   onde o arquivo '{DATABASE}' está localizado.")
        return False
    return True

def verificar_tabela_usuarios():
    """Verifica se a tabela de usuários existe no banco."""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'")
        resultado = cursor.fetchone()
        conn.close()
        
        if not resultado:
            print("\n⚠️  AVISO: A tabela 'usuarios' não existe no banco de dados.")
            print("   Você precisa atualizar o arquivo 'schema.sql' primeiro.")
            print("   Veja as instruções que foram fornecidas.")
            return False
        return True
    except Exception as e:
        print(f"❌ Erro ao verificar tabela: {e}")
        return False

def usuario_existe(username):
    """Verifica se um usuário já existe no banco."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE username = ?", (username,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None

def cadastrar_usuario():
    """Função principal para cadastrar um novo usuário."""
    print("\n" + "="*50)
    print("    CADASTRO DE NOVO USUÁRIO - SISTEMA RESTAURANTE")
    print("="*50 + "\n")
    
    # Verificações iniciais
    if not verificar_banco_existe():
        return
    
    if not verificar_tabela_usuarios():
        return
    
    # Solicita dados do usuário
    while True:
        username = input("Digite o nome de usuário desejado: ").strip()
        
        if not username:
            print("❌ O nome de usuário não pode estar vazio. Tente novamente.\n")
            continue
        
        if len(username) < 3:
            print("❌ O nome de usuário deve ter pelo menos 3 caracteres. Tente novamente.\n")
            continue
        
        # Verifica se o usuário já existe
        if usuario_existe(username):
            print(f"❌ O usuário '{username}' já existe. Escolha outro nome.\n")
            continue
        
        break
    
    while True:
        password = input("Digite a senha desejada: ").strip()
        
        if not password:
            print("❌ A senha não pode estar vazia. Tente novamente.\n")
            continue
        
        if len(password) < 4:
            print("❌ A senha deve ter pelo menos 4 caracteres. Tente novamente.\n")
            continue
        
        password_confirmacao = input("Confirme a senha: ").strip()
        
        if password != password_confirmacao:
            print("❌ As senhas não coincidem. Tente novamente.\n")
            continue
        
        break
    
    # --- Processo de Hashing da Senha ---
    try:
        # 1. Codifica a senha para bytes
        password_bytes = password.encode('utf-8')
        
        # 2. Gera o salt e cria o hash usando bcrypt
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password_bytes, salt)
        
        # 3. Converte o hash para string para salvar no banco
        hashed_password_str = hashed_password.decode('utf-8')
        
        # --- Salvando no Banco de Dados ---
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO usuarios (username, password_hash) VALUES (?, ?)",
            (username, hashed_password_str)
        )
        
        conn.commit()
        conn.close()
        
        print("\n" + "="*50)
        print("✅ USUÁRIO CADASTRADO COM SUCESSO!")
        print("="*50)
        print(f"   Nome de usuário: {username}")
        print(f"   Senha: {'*' * len(password)} (armazenada de forma segura)")
        print("\nAgora você pode fazer login no sistema com estas credenciais.")
        print("="*50 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERRO ao cadastrar usuário: {e}\n")

if __name__ == "__main__":
    try:
        cadastrar_usuario()
    except KeyboardInterrupt:
        print("\n\n⚠️  Cadastro cancelado pelo usuário.\n")
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}\n")