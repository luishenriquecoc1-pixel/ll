import sqlite3
from database import get_db, execute, fetchall, fetchone, fetchval, sql_month, sql_year
from datetime import datetime, date, timedelta


# ─── RECEITAS ─────────────────────────────────────────────────────────

def adicionar_receita(descricao, valor, categoria, data, usuario_id=1):
    db = get_db()
    execute(db, "INSERT INTO receitas (usuario_id, descricao, valor, categoria, data) VALUES (?, ?, ?, ?, ?)",
            (usuario_id, descricao, valor, categoria, data))
    db.commit()
    db.close()


def listar_receitas(usuario_id=1, mes=None, ano=None):
    db = get_db()
    if mes and ano:
        sql = f"SELECT * FROM receitas WHERE usuario_id = ? AND {sql_month('data')} = ? AND {sql_year('data')} = ? ORDER BY data DESC"
        rows = fetchall(db, sql, (usuario_id, int(mes), int(ano)))
    else:
        rows = fetchall(db, "SELECT * FROM receitas WHERE usuario_id = ? ORDER BY data DESC", (usuario_id,))
    db.close()
    return rows


def deletar_receita(receita_id):
    db = get_db()
    execute(db, "DELETE FROM receitas WHERE id = ?", (receita_id,))
    db.commit()
    db.close()


def total_receitas_mes(usuario_id=1, mes=None, ano=None):
    db = get_db()
    hoje = date.today()
    m = int(mes) if mes else hoje.month
    a = int(ano) if ano else hoje.year
    sql = f"SELECT COALESCE(SUM(valor), 0) FROM receitas WHERE usuario_id = ? AND {sql_month('data')} = ? AND {sql_year('data')} = ?"
    val = fetchval(db, sql, (usuario_id, m, a))
    db.close()
    return val or 0


# ─── GASTOS ───────────────────────────────────────────────────────────

def adicionar_gasto(descricao, valor, categoria, tipo, data, usuario_id=1):
    db = get_db()
    execute(db, "INSERT INTO gastos (usuario_id, descricao, valor, categoria, tipo, data) VALUES (?, ?, ?, ?, ?, ?)",
            (usuario_id, descricao, valor, categoria, tipo, data))
    db.commit()
    db.close()


def listar_gastos(usuario_id=1, mes=None, ano=None):
    db = get_db()
    if mes and ano:
        sql = f"SELECT * FROM gastos WHERE usuario_id = ? AND {sql_month('data')} = ? AND {sql_year('data')} = ? ORDER BY data DESC"
        rows = fetchall(db, sql, (usuario_id, int(mes), int(ano)))
    else:
        rows = fetchall(db, "SELECT * FROM gastos WHERE usuario_id = ? ORDER BY data DESC", (usuario_id,))
    db.close()
    return rows


def deletar_gasto(gasto_id):
    db = get_db()
    execute(db, "DELETE FROM gastos WHERE id = ?", (gasto_id,))
    db.commit()
    db.close()


def total_gastos_mes(usuario_id=1, mes=None, ano=None):
    db = get_db()
    hoje = date.today()
    m = int(mes) if mes else hoje.month
    a = int(ano) if ano else hoje.year
    sql = f"SELECT COALESCE(SUM(valor), 0) FROM gastos WHERE usuario_id = ? AND {sql_month('data')} = ? AND {sql_year('data')} = ?"
    val = fetchval(db, sql, (usuario_id, m, a))
    db.close()
    return val or 0


def gastos_por_categoria(usuario_id=1, mes=None, ano=None):
    db = get_db()
    hoje = date.today()
    m = int(mes) if mes else hoje.month
    a = int(ano) if ano else hoje.year
    sql = f"""SELECT categoria, SUM(valor) as total FROM gastos
              WHERE usuario_id = ? AND {sql_month('data')} = ? AND {sql_year('data')} = ?
              GROUP BY categoria ORDER BY total DESC"""
    rows = fetchall(db, sql, (usuario_id, m, a))
    db.close()
    return rows


# ─── DIVIDAS ──────────────────────────────────────────────────────────

def adicionar_divida(nome, valor_total, parcelas_total, juros_mensal, data_inicio, usuario_id=1):
    if juros_mensal > 0 and parcelas_total > 0:
        taxa = juros_mensal / 100
        if taxa == 0:
            valor_parcela = valor_total / parcelas_total
        else:
            valor_parcela = valor_total * (taxa * (1 + taxa) ** parcelas_total) / ((1 + taxa) ** parcelas_total - 1)
    else:
        valor_parcela = valor_total / parcelas_total if parcelas_total > 0 else valor_total

    db = get_db()
    execute(db,
            "INSERT INTO dividas (usuario_id, nome, valor_total, parcelas_total, juros_mensal, valor_parcela, data_inicio) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (usuario_id, nome, valor_total, parcelas_total, juros_mensal, round(valor_parcela, 2), data_inicio))
    db.commit()
    db.close()


def listar_dividas(usuario_id=1, apenas_ativas=False):
    db = get_db()
    sql = "SELECT * FROM dividas WHERE usuario_id = ?"
    params = [usuario_id]
    if apenas_ativas:
        sql += " AND paga = 0"
    sql += " ORDER BY paga ASC, juros_mensal DESC, valor_total ASC"
    rows = fetchall(db, sql, params)
    db.close()
    return rows


def pagar_parcela(divida_id):
    db = get_db()
    divida = fetchone(db, "SELECT * FROM dividas WHERE id = ?", (divida_id,))
    if divida and not divida['paga']:
        novas_pagas = divida['parcelas_pagas'] + 1
        novo_valor_pago = divida['valor_pago'] + divida['valor_parcela']
        paga = 1 if novas_pagas >= divida['parcelas_total'] else 0
        if paga:
            novo_valor_pago = divida['valor_total']
        execute(db, "UPDATE dividas SET parcelas_pagas = ?, valor_pago = ?, paga = ? WHERE id = ?",
                (novas_pagas, round(novo_valor_pago, 2), paga, divida_id))
        db.commit()
    db.close()


def marcar_divida_paga(divida_id):
    db = get_db()
    execute(db, "UPDATE dividas SET paga = 1, valor_pago = valor_total, parcelas_pagas = parcelas_total WHERE id = ?",
            (divida_id,))
    db.commit()
    db.close()


def deletar_divida(divida_id):
    db = get_db()
    execute(db, "DELETE FROM dividas WHERE id = ?", (divida_id,))
    db.commit()
    db.close()


def total_dividas(usuario_id=1):
    db = get_db()
    val = fetchval(db, "SELECT COALESCE(SUM(valor_total - valor_pago), 0) FROM dividas WHERE usuario_id = ? AND paga = 0",
                   (usuario_id,))
    db.close()
    return val or 0


def estrategia_bola_neve(usuario_id=1):
    db = get_db()
    rows = fetchall(db,
                    "SELECT *, (valor_total - valor_pago) as saldo_restante FROM dividas WHERE usuario_id = ? AND paga = 0 ORDER BY (valor_total - valor_pago) ASC",
                    (usuario_id,))
    db.close()
    return rows


def estrategia_avalanche(usuario_id=1):
    db = get_db()
    rows = fetchall(db,
                    "SELECT *, (valor_total - valor_pago) as saldo_restante FROM dividas WHERE usuario_id = ? AND paga = 0 ORDER BY juros_mensal DESC, (valor_total - valor_pago) ASC",
                    (usuario_id,))
    db.close()
    return rows


# ─── TAREFAS ──────────────────────────────────────────────────────────

def adicionar_tarefa(titulo, descricao, data, usuario_id=1):
    db = get_db()
    execute(db, "INSERT INTO tarefas (usuario_id, titulo, descricao, data) VALUES (?, ?, ?, ?)",
            (usuario_id, titulo, descricao, data))
    db.commit()
    db.close()


def listar_tarefas(data=None, usuario_id=1):
    db = get_db()
    if data:
        rows = fetchall(db,
                        "SELECT * FROM tarefas WHERE usuario_id = ? AND data = ? ORDER BY concluida ASC, criado_em ASC",
                        (usuario_id, data))
    else:
        rows = fetchall(db,
                        "SELECT * FROM tarefas WHERE usuario_id = ? ORDER BY data DESC, concluida ASC, criado_em ASC",
                        (usuario_id,))
    db.close()
    # Convert date objects to strings for template compatibility
    for row in rows:
        if isinstance(row.get('data'), date):
            row['data'] = row['data'].isoformat()
    return rows


def concluir_tarefa(tarefa_id):
    db = get_db()
    execute(db, "UPDATE tarefas SET concluida = 1, hora_conclusao = ? WHERE id = ?",
            (datetime.now().isoformat(), tarefa_id))
    db.commit()
    db.close()


def reabrir_tarefa(tarefa_id):
    db = get_db()
    execute(db, "UPDATE tarefas SET concluida = 0, hora_conclusao = NULL WHERE id = ?",
            (tarefa_id,))
    db.commit()
    db.close()


def deletar_tarefa(tarefa_id):
    db = get_db()
    execute(db, "DELETE FROM tarefas WHERE id = ?", (tarefa_id,))
    db.commit()
    db.close()


def progresso_tarefas(data=None, usuario_id=1):
    db = get_db()
    d = data or date.today().isoformat()
    total = fetchval(db, "SELECT COUNT(*) FROM tarefas WHERE usuario_id = ? AND data = ?",
                     (usuario_id, d))
    concluidas = fetchval(db, "SELECT COUNT(*) FROM tarefas WHERE usuario_id = ? AND data = ? AND concluida = 1",
                          (usuario_id, d))
    db.close()
    total = total or 0
    concluidas = concluidas or 0
    if total == 0:
        return {'total': 0, 'concluidas': 0, 'percentual': 0}
    return {
        'total': total,
        'concluidas': concluidas,
        'percentual': round((concluidas / total) * 100)
    }


def historico_tarefas(usuario_id=1, dias=30):
    db = get_db()
    data_inicio = (date.today() - timedelta(days=dias)).isoformat()
    rows = fetchall(db,
                    """SELECT data,
                              COUNT(*) as total,
                              SUM(CASE WHEN concluida = 1 THEN 1 ELSE 0 END) as concluidas
                       FROM tarefas
                       WHERE usuario_id = ? AND data >= ?
                       GROUP BY data
                       ORDER BY data DESC""",
                    (usuario_id, data_inicio))
    db.close()
    for row in rows:
        if isinstance(row.get('data'), date):
            row['data'] = row['data'].isoformat()
    return rows


# ─── HISTORICO ────────────────────────────────────────────────────────

def registrar_historico(usuario_id=1):
    hoje = date.today().isoformat()
    receitas = total_receitas_mes(usuario_id)
    gastos = total_gastos_mes(usuario_id)
    saldo = receitas - gastos
    dividas = total_dividas(usuario_id)
    prog = progresso_tarefas(hoje, usuario_id)

    db = get_db()
    existing = fetchone(db, "SELECT id FROM historico WHERE usuario_id = ? AND data = ?",
                        (usuario_id, hoje))

    if existing:
        execute(db,
                "UPDATE historico SET saldo = ?, total_dividas = ?, total_receitas = ?, total_gastos = ?, tarefas_total = ?, tarefas_concluidas = ? WHERE id = ?",
                (saldo, dividas, receitas, gastos, prog['total'], prog['concluidas'], existing['id']))
    else:
        execute(db,
                "INSERT INTO historico (usuario_id, data, saldo, total_dividas, total_receitas, total_gastos, tarefas_total, tarefas_concluidas) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (usuario_id, hoje, saldo, dividas, receitas, gastos, prog['total'], prog['concluidas']))
    db.commit()
    db.close()


def listar_historico(usuario_id=1, dias=90):
    db = get_db()
    data_inicio = (date.today() - timedelta(days=dias)).isoformat()
    rows = fetchall(db,
                    "SELECT * FROM historico WHERE usuario_id = ? AND data >= ? ORDER BY data ASC",
                    (usuario_id, data_inicio))
    db.close()
    for row in rows:
        if isinstance(row.get('data'), date):
            row['data'] = row['data'].isoformat()
    return rows


# ─── DISCIPLINA ───────────────────────────────────────────────────────

def listar_regras(usuario_id=1):
    db = get_db()
    rows = fetchall(db, "SELECT * FROM regras_disciplina WHERE usuario_id = ? ORDER BY id ASC",
                    (usuario_id,))
    db.close()
    return rows


def adicionar_regra(regra, usuario_id=1):
    db = get_db()
    execute(db, "INSERT INTO regras_disciplina (usuario_id, regra) VALUES (?, ?)",
            (usuario_id, regra))
    db.commit()
    db.close()


def deletar_regra(regra_id):
    db = get_db()
    execute(db, "DELETE FROM regras_disciplina WHERE id = ?", (regra_id,))
    db.commit()
    db.close()


# ─── METAS FINANCEIRAS ───────────────────────────────────────────────

def adicionar_meta(titulo, valor_alvo, valor_atual, prazo, categoria, usuario_id=1):
    db = get_db()
    execute(db,
            "INSERT INTO metas (usuario_id, titulo, valor_alvo, valor_atual, prazo, categoria) VALUES (?, ?, ?, ?, ?, ?)",
            (usuario_id, titulo, valor_alvo, valor_atual, prazo, categoria))
    db.commit()
    db.close()


def listar_metas(usuario_id=1, apenas_ativas=True):
    db = get_db()
    sql = "SELECT * FROM metas WHERE usuario_id = ?"
    params = [usuario_id]
    if apenas_ativas:
        sql += " AND concluida = 0"
    sql += " ORDER BY prazo ASC"
    rows = fetchall(db, sql, params)
    db.close()
    for row in rows:
        if isinstance(row.get('prazo'), date):
            row['prazo'] = row['prazo'].isoformat()
    return rows


def atualizar_meta(meta_id, valor_atual):
    db = get_db()
    meta = fetchone(db, "SELECT * FROM metas WHERE id = ?", (meta_id,))
    if meta:
        concluida = 1 if valor_atual >= meta['valor_alvo'] else 0
        execute(db, "UPDATE metas SET valor_atual = ?, concluida = ? WHERE id = ?",
                (valor_atual, concluida, meta_id))
        db.commit()
    db.close()


def deletar_meta(meta_id):
    db = get_db()
    execute(db, "DELETE FROM metas WHERE id = ?", (meta_id,))
    db.commit()
    db.close()


def concluir_meta(meta_id):
    db = get_db()
    execute(db, "UPDATE metas SET concluida = 1, valor_atual = valor_alvo WHERE id = ?", (meta_id,))
    db.commit()
    db.close()


# ─── ORCAMENTO MENSAL ─────────────────────────────────────────────────

def definir_orcamento(categoria, limite, mes, ano, usuario_id=1):
    db = get_db()
    existing = fetchone(db,
                        "SELECT id FROM orcamentos WHERE usuario_id = ? AND categoria = ? AND mes = ? AND ano = ?",
                        (usuario_id, categoria, mes, ano))
    if existing:
        execute(db, "UPDATE orcamentos SET limite = ? WHERE id = ?", (limite, existing['id']))
    else:
        execute(db, "INSERT INTO orcamentos (usuario_id, categoria, limite, mes, ano) VALUES (?, ?, ?, ?, ?)",
                (usuario_id, categoria, limite, mes, ano))
    db.commit()
    db.close()


def listar_orcamentos(usuario_id=1, mes=None, ano=None):
    db = get_db()
    hoje = date.today()
    m = int(mes) if mes else hoje.month
    a = int(ano) if ano else hoje.year
    rows = fetchall(db,
                    "SELECT * FROM orcamentos WHERE usuario_id = ? AND mes = ? AND ano = ? ORDER BY categoria ASC",
                    (usuario_id, m, a))
    db.close()
    return rows


def orcamento_com_gastos(usuario_id=1, mes=None, ano=None):
    hoje = date.today()
    m = int(mes) if mes else hoje.month
    a = int(ano) if ano else hoje.year

    orcamentos = listar_orcamentos(usuario_id, m, a)
    gastos_cat = gastos_por_categoria(usuario_id, m, a)
    gastos_map = {g['categoria']: g['total'] for g in gastos_cat}

    resultado = []
    for orc in orcamentos:
        gasto_real = gastos_map.get(orc['categoria'], 0)
        percentual = round((gasto_real / orc['limite']) * 100) if orc['limite'] > 0 else 0
        resultado.append({
            **orc,
            'gasto_real': gasto_real,
            'percentual': percentual,
            'restante': orc['limite'] - gasto_real,
            'estourou': gasto_real > orc['limite']
        })
    return resultado


def deletar_orcamento(orcamento_id):
    db = get_db()
    execute(db, "DELETE FROM orcamentos WHERE id = ?", (orcamento_id,))
    db.commit()
    db.close()


# ─── RESET ────────────────────────────────────────────────────────────

def resetar_tudo(usuario_id=1):
    db = get_db()
    tabelas = ['receitas', 'gastos', 'dividas', 'tarefas', 'historico',
               'regras_disciplina', 'metas', 'orcamentos']
    for tabela in tabelas:
        execute(db, f"DELETE FROM {tabela} WHERE usuario_id = ?", (usuario_id,))
    db.commit()
    db.close()

    # Reinsert default discipline rules
    db = get_db()
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
        execute(db, "INSERT INTO regras_disciplina (usuario_id, regra) VALUES (?, ?)",
                (usuario_id, regra))
    db.commit()
    db.close()


# ─── USUARIO ──────────────────────────────────────────────────────────

def buscar_usuario_por_email(email):
    db = get_db()
    row = fetchone(db, "SELECT * FROM usuarios WHERE email = ?", (email,))
    db.close()
    return row


def buscar_usuario_por_id(user_id):
    db = get_db()
    row = fetchone(db, "SELECT * FROM usuarios WHERE id = ?", (user_id,))
    db.close()
    return row


def criar_usuario(nome, email, senha_hash):
    db = get_db()
    try:
        execute(db, "INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?)",
                (nome, email, senha_hash))
        db.commit()
        db.close()
        return True
    except Exception:
        db.rollback()
        db.close()
        return False
