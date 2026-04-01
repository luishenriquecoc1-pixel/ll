from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import date, datetime
import csv
import io
import os

from database import init_db
import models

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chave-secreta-mudar-em-producao-2024')


# ─── AUTH ─────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faca login para acessar o sistema.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '')
        user = models.buscar_usuario_por_email(email)
        if user and check_password_hash(user['senha_hash'], senha):
            session['user_id'] = user['id']
            session['user_nome'] = user['nome']
            flash(f'Bem-vindo, {user["nome"]}! Hora de executar.', 'success')
            return redirect(url_for('dashboard'))
        flash('Email ou senha incorretos.', 'danger')
    return render_template('login.html')


@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '')
        senha2 = request.form.get('senha2', '')

        if not nome or not email or not senha:
            flash('Preencha todos os campos.', 'danger')
        elif senha != senha2:
            flash('As senhas nao coincidem.', 'danger')
        elif len(senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
        else:
            ok = models.criar_usuario(nome, email, generate_password_hash(senha))
            if ok:
                flash('Conta criada com sucesso! Faca login.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Email ja cadastrado.', 'danger')
    return render_template('registro.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Voce saiu do sistema.', 'info')
    return redirect(url_for('login'))


# ─── DASHBOARD ────────────────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    uid = session['user_id']
    hoje = date.today()

    receitas = models.total_receitas_mes(uid)
    gastos = models.total_gastos_mes(uid)
    saldo = receitas - gastos
    dividas = models.total_dividas(uid)
    prog = models.progresso_tarefas(hoje.isoformat(), uid)
    tarefas_hoje = models.listar_tarefas(hoje.isoformat(), uid)
    gastos_cat = models.gastos_por_categoria(uid)
    orcamentos_alerta = models.orcamento_com_gastos(uid)
    metas = models.listar_metas(uid, apenas_ativas=True)

    # Register daily snapshot
    models.registrar_historico(uid)

    # Evolution data for chart (last 30 days)
    historico = models.listar_historico(uid, 30)

    return render_template('dashboard.html',
                           saldo=saldo,
                           receitas=receitas,
                           gastos_total=gastos,
                           dividas=dividas,
                           progresso=prog,
                           tarefas_hoje=tarefas_hoje,
                           gastos_cat=gastos_cat,
                           historico=historico,
                           orcamentos_alerta=orcamentos_alerta,
                           metas=metas,
                           hoje=hoje)


# ─── DIVIDAS ──────────────────────────────────────────────────────────

@app.route('/dividas')
@login_required
def dividas():
    uid = session['user_id']
    todas = models.listar_dividas(uid)
    bola_neve = models.estrategia_bola_neve(uid)
    avalanche = models.estrategia_avalanche(uid)
    total = models.total_dividas(uid)
    return render_template('dividas.html',
                           dividas=todas,
                           bola_neve=bola_neve,
                           avalanche=avalanche,
                           total_dividas=total)


@app.route('/dividas/adicionar', methods=['POST'])
@login_required
def adicionar_divida():
    uid = session['user_id']
    nome = request.form.get('nome', '').strip()
    valor = float(request.form.get('valor_total', 0))
    parcelas = int(request.form.get('parcelas_total', 1))
    juros = float(request.form.get('juros_mensal', 0))
    data_inicio = request.form.get('data_inicio', date.today().isoformat())

    if nome and valor > 0:
        models.adicionar_divida(nome, valor, parcelas, juros, data_inicio, uid)
        flash(f'Divida "{nome}" adicionada. Foco em eliminar!', 'success')
    else:
        flash('Preencha nome e valor corretamente.', 'danger')
    return redirect(url_for('dividas'))


@app.route('/dividas/pagar/<int:divida_id>')
@login_required
def pagar_parcela(divida_id):
    models.pagar_parcela(divida_id)
    flash('Parcela paga! Continue assim!', 'success')
    return redirect(url_for('dividas'))


@app.route('/dividas/quitar/<int:divida_id>')
@login_required
def quitar_divida(divida_id):
    models.marcar_divida_paga(divida_id)
    flash('Divida QUITADA! Uma a menos!', 'success')
    return redirect(url_for('dividas'))


@app.route('/dividas/deletar/<int:divida_id>')
@login_required
def deletar_divida(divida_id):
    models.deletar_divida(divida_id)
    flash('Divida removida.', 'info')
    return redirect(url_for('dividas'))


# ─── FINANCEIRO ───────────────────────────────────────────────────────

@app.route('/financeiro')
@login_required
def financeiro():
    uid = session['user_id']
    hoje = date.today()
    mes = request.args.get('mes', hoje.month)
    ano = request.args.get('ano', hoje.year)

    receitas = models.listar_receitas(uid, mes, ano)
    gastos = models.listar_gastos(uid, mes, ano)
    total_rec = models.total_receitas_mes(uid, mes, ano)
    total_gas = models.total_gastos_mes(uid, mes, ano)
    sobra = total_rec - total_gas
    gastos_cat = models.gastos_por_categoria(uid, mes, ano)
    orcamentos = models.orcamento_com_gastos(uid, mes, ano)

    return render_template('financeiro.html',
                           receitas=receitas,
                           gastos=gastos,
                           total_receitas=total_rec,
                           total_gastos=total_gas,
                           sobra=sobra,
                           gastos_cat=gastos_cat,
                           orcamentos=orcamentos,
                           mes=int(mes),
                           ano=int(ano),
                           hoje=hoje)


@app.route('/financeiro/receita', methods=['POST'])
@login_required
def adicionar_receita():
    uid = session['user_id']
    descricao = request.form.get('descricao', '').strip()
    valor = float(request.form.get('valor', 0))
    categoria = request.form.get('categoria', 'Outros')
    data = request.form.get('data', date.today().isoformat())

    if descricao and valor > 0:
        models.adicionar_receita(descricao, valor, categoria, data, uid)
        flash('Receita adicionada!', 'success')
    else:
        flash('Preencha corretamente.', 'danger')
    return redirect(url_for('financeiro'))


@app.route('/financeiro/gasto', methods=['POST'])
@login_required
def adicionar_gasto():
    uid = session['user_id']
    descricao = request.form.get('descricao', '').strip()
    valor = float(request.form.get('valor', 0))
    categoria = request.form.get('categoria', 'Outros')
    tipo = request.form.get('tipo', 'variavel')
    data = request.form.get('data', date.today().isoformat())

    if descricao and valor > 0:
        models.adicionar_gasto(descricao, valor, categoria, tipo, data, uid)
        flash('Gasto registrado. Lembre-se: cada real conta!', 'warning')
    else:
        flash('Preencha corretamente.', 'danger')
    return redirect(url_for('financeiro'))


@app.route('/financeiro/receita/deletar/<int:id>')
@login_required
def deletar_receita(id):
    models.deletar_receita(id)
    flash('Receita removida.', 'info')
    return redirect(url_for('financeiro'))


@app.route('/financeiro/gasto/deletar/<int:id>')
@login_required
def deletar_gasto(id):
    models.deletar_gasto(id)
    flash('Gasto removido.', 'info')
    return redirect(url_for('financeiro'))


# ─── ORCAMENTO ────────────────────────────────────────────────────────

@app.route('/financeiro/orcamento', methods=['POST'])
@login_required
def definir_orcamento():
    uid = session['user_id']
    categoria = request.form.get('categoria', '').strip()
    limite = float(request.form.get('limite', 0))
    mes = int(request.form.get('mes', date.today().month))
    ano = int(request.form.get('ano', date.today().year))

    if categoria and limite > 0:
        models.definir_orcamento(categoria, limite, mes, ano, uid)
        flash(f'Orcamento de R$ {limite:.2f} definido para {categoria}!', 'success')
    else:
        flash('Preencha categoria e limite.', 'danger')
    return redirect(url_for('financeiro', mes=mes, ano=ano))


@app.route('/financeiro/orcamento/deletar/<int:orcamento_id>')
@login_required
def deletar_orcamento(orcamento_id):
    models.deletar_orcamento(orcamento_id)
    flash('Orcamento removido.', 'info')
    return redirect(url_for('financeiro'))


# ─── TAREFAS ──────────────────────────────────────────────────────────

@app.route('/tarefas')
@login_required
def tarefas():
    uid = session['user_id']
    hoje = date.today()
    data_filtro = request.args.get('data', hoje.isoformat())
    tarefas_lista = models.listar_tarefas(data_filtro, uid)
    prog = models.progresso_tarefas(data_filtro, uid)
    historico = models.historico_tarefas(uid, 30)
    return render_template('tarefas.html',
                           tarefas=tarefas_lista,
                           progresso=prog,
                           historico=historico,
                           data_filtro=data_filtro,
                           hoje=hoje)


@app.route('/tarefas/adicionar', methods=['POST'])
@login_required
def adicionar_tarefa():
    uid = session['user_id']
    titulo = request.form.get('titulo', '').strip()
    descricao = request.form.get('descricao', '').strip()
    data = request.form.get('data', date.today().isoformat())

    if titulo:
        models.adicionar_tarefa(titulo, descricao, data, uid)
        flash('Tarefa criada! Agora EXECUTE.', 'success')
    else:
        flash('Titulo obrigatorio.', 'danger')
    return redirect(url_for('tarefas', data=data))


@app.route('/tarefas/concluir/<int:tarefa_id>')
@login_required
def concluir_tarefa(tarefa_id):
    models.concluir_tarefa(tarefa_id)
    flash('Tarefa concluida! Proximo!', 'success')
    data = request.args.get('data', date.today().isoformat())
    return redirect(url_for('tarefas', data=data))


@app.route('/tarefas/reabrir/<int:tarefa_id>')
@login_required
def reabrir_tarefa(tarefa_id):
    models.reabrir_tarefa(tarefa_id)
    data = request.args.get('data', date.today().isoformat())
    return redirect(url_for('tarefas', data=data))


@app.route('/tarefas/deletar/<int:tarefa_id>')
@login_required
def deletar_tarefa(tarefa_id):
    models.deletar_tarefa(tarefa_id)
    flash('Tarefa removida.', 'info')
    data = request.args.get('data', date.today().isoformat())
    return redirect(url_for('tarefas', data=data))


# ─── METAS FINANCEIRAS ───────────────────────────────────────────────

@app.route('/metas')
@login_required
def metas():
    uid = session['user_id']
    ativas = models.listar_metas(uid, apenas_ativas=True)
    concluidas = models.listar_metas(uid, apenas_ativas=False)
    concluidas = [m for m in concluidas if m['concluida']]
    return render_template('metas.html', metas_ativas=ativas, metas_concluidas=concluidas, hoje=date.today())


@app.route('/metas/adicionar', methods=['POST'])
@login_required
def adicionar_meta():
    uid = session['user_id']
    titulo = request.form.get('titulo', '').strip()
    valor_alvo = float(request.form.get('valor_alvo', 0))
    valor_atual = float(request.form.get('valor_atual', 0))
    prazo = request.form.get('prazo', '')
    categoria = request.form.get('categoria', 'Geral')

    if titulo and valor_alvo > 0 and prazo:
        models.adicionar_meta(titulo, valor_alvo, valor_atual, prazo, categoria, uid)
        flash(f'Meta "{titulo}" criada! Foco no objetivo!', 'success')
    else:
        flash('Preencha todos os campos obrigatorios.', 'danger')
    return redirect(url_for('metas'))


@app.route('/metas/atualizar/<int:meta_id>', methods=['POST'])
@login_required
def atualizar_meta(meta_id):
    valor_atual = float(request.form.get('valor_atual', 0))
    models.atualizar_meta(meta_id, valor_atual)
    flash('Meta atualizada!', 'success')
    return redirect(url_for('metas'))


@app.route('/metas/concluir/<int:meta_id>')
@login_required
def concluir_meta_route(meta_id):
    models.concluir_meta(meta_id)
    flash('Meta CONCLUIDA! Parabens!', 'success')
    return redirect(url_for('metas'))


@app.route('/metas/deletar/<int:meta_id>')
@login_required
def deletar_meta(meta_id):
    models.deletar_meta(meta_id)
    flash('Meta removida.', 'info')
    return redirect(url_for('metas'))


# ─── EVOLUCAO ─────────────────────────────────────────────────────────

@app.route('/evolucao')
@login_required
def evolucao():
    uid = session['user_id']
    dias = int(request.args.get('dias', 90))
    historico = models.listar_historico(uid, dias)
    return render_template('evolucao.html', historico=historico, dias=dias)


# ─── DISCIPLINA ───────────────────────────────────────────────────────

@app.route('/disciplina')
@login_required
def disciplina():
    uid = session['user_id']
    regras = models.listar_regras(uid)
    hoje = date.today().isoformat()
    prog = models.progresso_tarefas(hoje, uid)

    alerta = None
    if prog['total'] > 0 and prog['percentual'] < 100:
        pendentes = prog['total'] - prog['concluidas']
        alerta = f'ATENCAO: Voce tem {pendentes} tarefa(s) pendente(s) hoje! Nao va dormir sem completar.'
    elif prog['total'] == 0:
        alerta = 'Voce nao criou nenhuma tarefa para hoje. Disciplina comeca com planejamento!'

    return render_template('disciplina.html', regras=regras, progresso=prog, alerta=alerta)


@app.route('/disciplina/adicionar', methods=['POST'])
@login_required
def adicionar_regra():
    uid = session['user_id']
    regra = request.form.get('regra', '').strip()
    if regra:
        models.adicionar_regra(regra, uid)
        flash('Nova regra adicionada!', 'success')
    return redirect(url_for('disciplina'))


@app.route('/disciplina/deletar/<int:regra_id>')
@login_required
def deletar_regra(regra_id):
    models.deletar_regra(regra_id)
    flash('Regra removida.', 'info')
    return redirect(url_for('disciplina'))


# ─── EXPORT (CSV/PDF) ────────────────────────────────────────────────

@app.route('/export/financeiro/csv')
@login_required
def export_financeiro_csv():
    uid = session['user_id']
    hoje = date.today()
    mes = request.args.get('mes', hoje.month)
    ano = request.args.get('ano', hoje.year)

    receitas = models.listar_receitas(uid, mes, ano)
    gastos = models.listar_gastos(uid, mes, ano)

    output = io.StringIO()
    output.write('\ufeff')  # BOM for Excel UTF-8
    writer = csv.writer(output, delimiter=';')

    writer.writerow(['RELATORIO FINANCEIRO'])
    nomes_meses = ['Janeiro','Fevereiro','Marco','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
    writer.writerow([f'{nomes_meses[int(mes)-1]} / {ano}'])
    writer.writerow([])

    writer.writerow(['=== RECEITAS ==='])
    writer.writerow(['Data', 'Descricao', 'Categoria', 'Valor (R$)'])
    total_rec = 0
    for r in receitas:
        writer.writerow([r['data'], r['descricao'], r['categoria'], f"{r['valor']:.2f}"])
        total_rec += r['valor']
    writer.writerow(['', '', 'TOTAL RECEITAS', f"{total_rec:.2f}"])
    writer.writerow([])

    writer.writerow(['=== GASTOS ==='])
    writer.writerow(['Data', 'Descricao', 'Categoria', 'Tipo', 'Valor (R$)'])
    total_gas = 0
    for g in gastos:
        writer.writerow([g['data'], g['descricao'], g['categoria'], g['tipo'], f"{g['valor']:.2f}"])
        total_gas += g['valor']
    writer.writerow(['', '', '', 'TOTAL GASTOS', f"{total_gas:.2f}"])
    writer.writerow([])

    writer.writerow(['SALDO DO MES', '', '', '', f"{total_rec - total_gas:.2f}"])

    filename = f"financeiro_{ano}_{int(mes):02d}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@app.route('/export/dividas/csv')
@login_required
def export_dividas_csv():
    uid = session['user_id']
    dividas_lista = models.listar_dividas(uid)

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')

    writer.writerow(['RELATORIO DE DIVIDAS'])
    writer.writerow([f'Gerado em {date.today().isoformat()}'])
    writer.writerow([])
    writer.writerow(['Nome', 'Valor Total', 'Valor Pago', 'Restante', 'Parcelas (pagas/total)', 'Juros Mensal (%)', 'Valor Parcela', 'Status'])

    total_restante = 0
    for d in dividas_lista:
        restante = d['valor_total'] - d['valor_pago']
        status = 'QUITADA' if d['paga'] else 'Ativa'
        writer.writerow([
            d['nome'], f"{d['valor_total']:.2f}", f"{d['valor_pago']:.2f}", f"{restante:.2f}",
            f"{d['parcelas_pagas']}/{d['parcelas_total']}", f"{d['juros_mensal']:.1f}",
            f"{d['valor_parcela']:.2f}", status
        ])
        if not d['paga']:
            total_restante += restante

    writer.writerow([])
    writer.writerow(['TOTAL RESTANTE', '', '', f"{total_restante:.2f}"])

    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename=dividas_{date.today().isoformat()}.csv'}
    )


@app.route('/export/evolucao/csv')
@login_required
def export_evolucao_csv():
    uid = session['user_id']
    dias = int(request.args.get('dias', 90))
    historico = models.listar_historico(uid, dias)

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')

    writer.writerow(['RELATORIO DE EVOLUCAO'])
    writer.writerow([f'Ultimos {dias} dias'])
    writer.writerow([])
    writer.writerow(['Data', 'Saldo', 'Dividas', 'Receitas', 'Gastos', 'Tarefas Concluidas', 'Tarefas Total'])

    for h in historico:
        writer.writerow([
            h['data'], f"{h['saldo']:.2f}", f"{h['total_dividas']:.2f}",
            f"{h['total_receitas']:.2f}", f"{h['total_gastos']:.2f}",
            h['tarefas_concluidas'], h['tarefas_total']
        ])

    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename=evolucao_{date.today().isoformat()}.csv'}
    )


@app.route('/export/completo/csv')
@login_required
def export_completo_csv():
    """Exporta relatorio completo com tudo."""
    uid = session['user_id']
    hoje = date.today()

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')

    writer.writerow(['RELATORIO COMPLETO - RESOLVENDO MINHA VIDA'])
    writer.writerow([f'Gerado em {hoje.isoformat()}'])
    writer.writerow([])

    # Resumo
    receitas = models.total_receitas_mes(uid)
    gastos = models.total_gastos_mes(uid)
    dividas = models.total_dividas(uid)
    writer.writerow(['=== RESUMO DO MES ==='])
    writer.writerow(['Receitas', f"{receitas:.2f}"])
    writer.writerow(['Gastos', f"{gastos:.2f}"])
    writer.writerow(['Saldo', f"{receitas - gastos:.2f}"])
    writer.writerow(['Dividas Restantes', f"{dividas:.2f}"])
    writer.writerow([])

    # Dividas
    dividas_lista = models.listar_dividas(uid)
    writer.writerow(['=== DIVIDAS ==='])
    writer.writerow(['Nome', 'Total', 'Pago', 'Restante', 'Juros', 'Status'])
    for d in dividas_lista:
        writer.writerow([
            d['nome'], f"{d['valor_total']:.2f}", f"{d['valor_pago']:.2f}",
            f"{d['valor_total'] - d['valor_pago']:.2f}", f"{d['juros_mensal']:.1f}%",
            'QUITADA' if d['paga'] else 'Ativa'
        ])
    writer.writerow([])

    # Metas
    metas_lista = models.listar_metas(uid, apenas_ativas=False)
    writer.writerow(['=== METAS ==='])
    writer.writerow(['Titulo', 'Valor Alvo', 'Valor Atual', 'Prazo', 'Status'])
    for m in metas_lista:
        pct = round((m['valor_atual'] / m['valor_alvo']) * 100) if m['valor_alvo'] > 0 else 0
        writer.writerow([
            m['titulo'], f"{m['valor_alvo']:.2f}", f"{m['valor_atual']:.2f}",
            m['prazo'], f"{'Concluida' if m['concluida'] else f'{pct}%'}"
        ])

    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename=relatorio_completo_{hoje.isoformat()}.csv'}
    )


# ─── RESET ────────────────────────────────────────────────────────────

@app.route('/resetar', methods=['POST'])
@login_required
def resetar_dados():
    uid = session['user_id']
    confirmacao = request.form.get('confirmacao', '')
    if confirmacao == 'RESETAR':
        models.resetar_tudo(uid)
        flash('Todos os dados foram apagados. Comece do zero!', 'warning')
    else:
        flash('Digite RESETAR para confirmar.', 'danger')
    return redirect(url_for('dashboard'))


# ─── API (para graficos dinamicos) ───────────────────────────────────

@app.route('/api/historico')
@login_required
def api_historico():
    uid = session['user_id']
    dias = int(request.args.get('dias', 90))
    historico = models.listar_historico(uid, dias)
    return jsonify(historico)


# ─── INIT ─────────────────────────────────────────────────────────────

# Sempre inicializa o banco (necessario para gunicorn no Render)
init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
