import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """
    Retorna uma conexão com o banco de dados.
    Usa PostgreSQL em produção (Render) e SQLite localmente.
    """
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # Produção: PostgreSQL no Render
        # Render fornece a URL no formato postgres://, mas psycopg2 precisa de postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        conn = psycopg2.connect(database_url)
        conn.row_factory = RealDictCursor
        return conn, 'postgresql'
    else:
        # Desenvolvimento: SQLite local
        conn = sqlite3.connect('restaurante.db')
        conn.row_factory = sqlite3.Row
        return conn, 'sqlite'
