import os
from datetime import date as date_type, datetime
from decimal import Decimal

DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Render uses "postgres://" but psycopg needs "postgresql://"
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

USE_PG = bool(DATABASE_URL)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vida.db')


def _normalize_row(row):
    """Converte tipos PostgreSQL (date, Decimal, etc) para tipos simples."""
    if not isinstance(row, dict):
        return row
    result = {}
    for key, value in row.items():
        if isinstance(value, date_type) and not isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result


def get_db():
    """Retorna conexao com PostgreSQL (producao) ou SQLite (local)."""
    if USE_PG:
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=False)
        return conn
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def execute(conn, sql, params=None):
    """Executa query adaptando parametros para o banco correto."""
    if USE_PG:
        sql = sql.replace('?', '%s')
        cursor = conn.execute(sql, params or ())
        return cursor
    else:
        return conn.execute(sql, params or ())


def fetchall(conn, sql, params=None):
    """Executa e retorna todas as linhas como lista de dicts normalizados."""
    cursor = execute(conn, sql, params)
    rows = cursor.fetchall()
    return [_normalize_row(dict(r)) for r in rows]


def fetchone(conn, sql, params=None):
    """Executa e retorna uma linha como dict normalizado (ou None)."""
    cursor = execute(conn, sql, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return _normalize_row(dict(row))


def fetchval(conn, sql, params=None):
    """Executa e retorna o primeiro valor da primeira linha."""
    cursor = execute(conn, sql, params)
    row = cursor.fetchone()
    if row is None:
        return None
    if isinstance(row, dict):
        val = list(row.values())[0]
    else:
        val = row[0]
    if isinstance(val, Decimal):
        return float(val)
    return val


# ─── SQL helpers para datas (diferem entre SQLite e PG) ──────────────

def sql_month(column):
    """Retorna SQL para extrair mes de uma coluna DATE."""
    if USE_PG:
        return f"EXTRACT(MONTH FROM {column})::int"
    else:
        return f"CAST(strftime('%m', {column}) AS INTEGER)"


def sql_year(column):
    """Retorna SQL para extrair ano de uma coluna DATE."""
    if USE_PG:
        return f"EXTRACT(YEAR FROM {column})::int"
    else:
        return f"CAST(strftime('%Y', {column}) AS INTEGER)"


# ─── INIT ─────────────────────────────────────────────────────────────

def init_db():
    conn = get_db()

    if USE_PG:
        _init_pg(conn)
    else:
        _init_sqlite(conn)

    conn.commit()
    conn.close()


def _init_pg(conn):
    """Cria tabelas no PostgreSQL."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS receitas (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            categoria TEXT DEFAULT 'Outros',
            data DATE NOT NULL,
            recorrente INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS gastos (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            categoria TEXT DEFAULT 'Outros',
            tipo TEXT DEFAULT 'variavel',
            data DATE NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS dividas (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
            nome TEXT NOT NULL,
            valor_total REAL NOT NULL,
            valor_pago REAL DEFAULT 0,
            parcelas_total INTEGER DEFAULT 1,
            parcelas_pagas INTEGER DEFAULT 0,
            juros_mensal REAL DEFAULT 0,
            valor_parcela REAL DEFAULT 0,
            data_inicio DATE NOT NULL,
            paga INTEGER DEFAULT 0,
            prioridade INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tarefas (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
            titulo TEXT NOT NULL,
            descricao TEXT,
            data DATE NOT NULL,
            concluida INTEGER DEFAULT 0,
            hora_conclusao TIMESTAMP,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS historico (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
            data DATE NOT NULL,
            saldo REAL DEFAULT 0,
            total_dividas REAL DEFAULT 0,
            total_receitas REAL DEFAULT 0,
            total_gastos REAL DEFAULT 0,
            tarefas_total INTEGER DEFAULT 0,
            tarefas_concluidas INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS regras_disciplina (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
            regra TEXT NOT NULL,
            ativa INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS metas (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
            titulo TEXT NOT NULL,
            valor_alvo REAL NOT NULL,
            valor_atual REAL DEFAULT 0,
            prazo DATE NOT NULL,
            categoria TEXT DEFAULT 'Geral',
            concluida INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orcamentos (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
            categoria TEXT NOT NULL,
            limite REAL NOT NULL,
            mes INTEGER NOT NULL,
            ano INTEGER NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    _insert_defaults(conn)


def _init_sqlite(conn):
    """Cria tabelas no SQLite."""
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS receitas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL DEFAULT 1,
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            categoria TEXT DEFAULT 'Outros',
            data DATE NOT NULL,
            recorrente INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL DEFAULT 1,
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            categoria TEXT DEFAULT 'Outros',
            tipo TEXT DEFAULT 'variavel',
            data DATE NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS dividas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL DEFAULT 1,
            nome TEXT NOT NULL,
            valor_total REAL NOT NULL,
            valor_pago REAL DEFAULT 0,
            parcelas_total INTEGER DEFAULT 1,
            parcelas_pagas INTEGER DEFAULT 0,
            juros_mensal REAL DEFAULT 0,
            valor_parcela REAL DEFAULT 0,
            data_inicio DATE NOT NULL,
            paga INTEGER DEFAULT 0,
            prioridade INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL DEFAULT 1,
            titulo TEXT NOT NULL,
            descricao TEXT,
            data DATE NOT NULL,
            concluida INTEGER DEFAULT 0,
            hora_conclusao TIMESTAMP,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL DEFAULT 1,
            data DATE NOT NULL,
            saldo REAL DEFAULT 0,
            total_dividas REAL DEFAULT 0,
            total_receitas REAL DEFAULT 0,
            total_gastos REAL DEFAULT 0,
            tarefas_total INTEGER DEFAULT 0,
            tarefas_concluidas INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS regras_disciplina (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL DEFAULT 1,
            regra TEXT NOT NULL,
            ativa INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS metas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL DEFAULT 1,
            titulo TEXT NOT NULL,
            valor_alvo REAL NOT NULL,
            valor_atual REAL DEFAULT 0,
            prazo DATE NOT NULL,
            categoria TEXT DEFAULT 'Geral',
            concluida INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS orcamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL DEFAULT 1,
            categoria TEXT NOT NULL,
            limite REAL NOT NULL,
            mes INTEGER NOT NULL,
            ano INTEGER NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );
    ''')

    _insert_defaults(conn)


def _insert_defaults(conn):
    """Insere usuario padrao e regras se nao existirem."""
    from werkzeug.security import generate_password_hash

    count = fetchval(conn, "SELECT COUNT(*) FROM usuarios")
    if count == 0:
        execute(conn, "INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?)",
                ('Admin', 'admin@vida.com', generate_password_hash('admin123')))

    count = fetchval(conn, "SELECT COUNT(*) FROM regras_disciplina")
    if count == 0:
        regras = [
            'Sem gastos desnecessarios - cada real conta',
            'Foco total em quitar dividas - liberdade financeira e prioridade',
            'Executar TODAS as tarefas do dia - sem excecoes',
            'Registrar cada gasto - consciencia financeira',
            'Revisar financas toda semana - controle e previsao',
            'Nao fazer dividas novas - ciclo de pobreza acaba aqui',
            'Investir em conhecimento - o melhor retorno possivel',
            'Dormir cedo e acordar cedo - disciplina comeca no basico',
        ]
        for regra in regras:
            execute(conn, "INSERT INTO regras_disciplina (usuario_id, regra) VALUES (?, ?)",
                    (1, regra))
