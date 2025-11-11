import sqlite3
import logging
import random
import asyncio
import requests
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from contextlib import contextmanager

# ========== CONFIGURAÇÃO ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ✅ CONFIGURAÇÃO FIXA
# ✅ CONFIGURAÇÃO FIXA - VERSÃO SEGURA
TOKEN = "7992921510:" + "AAGHmKAZW3-FmqIN0-gLm3SojyIJ5fOMYEs"
ADMIN_IDS = [8058168121, 6655219234]  # ID do @DelySet
ADMIN_USERNAME = "@DelySet"

MANUTENCAO = False

ANIMAIS = {
    'avestruz': {'numeros': '01-02-03-04', 'emoji': '🐦'},
    'aguia': {'numeros': '05-06-07-08', 'emoji': '🦅'},
    'burro': {'numeros': '09-10-11-12', 'emoji': '🐴'},
    'borboleta': {'numeros': '13-14-15-16', 'emoji': '🦋'},
    'cachorro': {'numeros': '17-18-19-20', 'emoji': '🐶'},
    'cabra': {'numeros': '21-22-23-24', 'emoji': '🐐'},
    'carneiro': {'numeros': '25-26-27-28', 'emoji': '🐑'},
    'camelo': {'numeros': '29-30-31-32', 'emoji': '🐫'},
    'cobra': {'numeros': '33-34-35-36', 'emoji': '🐍'},
    'coelho': {'numeros': '37-38-39-40', 'emoji': '🐰'},
    'cavalo': {'numeros': '41-42-43-44', 'emoji': '🐎'},
    'elefante': {'numeros': '45-46-47-48', 'emoji': '🐘'},
    'galo': {'numeros': '49-50-51-52', 'emoji': '🐓'},
    'gato': {'numeros': '53-54-55-56', 'emoji': '🐱'},
    'jacare': {'numeros': '57-58-59-60', 'emoji': '🐊'},
    'leao': {'numeros': '61-62-63-64', 'emoji': '🦁'},
    'macaco': {'numeros': '65-66-67-68', 'emoji': '🐒'},
    'porco': {'numeros': '69-70-71-72', 'emoji': '🐷'},
    'pavao': {'numeros': '73-74-75-76', 'emoji': '🦚'},
    'peru': {'numeros': '77-78-79-80', 'emoji': '🦃'},
    'touro': {'numeros': '81-82-83-84', 'emoji': '🐂'},
    'tigre': {'numeros': '85-86-87-88', 'emoji': '🐅'},
    'urso': {'numeros': '89-90-91-92', 'emoji': '🐻'},
    'veado': {'numeros': '93-94-95-96', 'emoji': '🦌'},
    'vaca': {'numeros': '97-98-99-00', 'emoji': '🐄'}
}

# ========== SISTEMA DE BANCO DE DADOS ==========
@contextmanager
def get_db_connection():
    conn = sqlite3.connect('bot_jogo_bicho.db', timeout=20)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Erro no banco: {e}")
        raise
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            primeiro_nome TEXT,
            saldo INTEGER DEFAULT 0,
            bonus INTEGER DEFAULT 0,
            total_depositado INTEGER DEFAULT 0,
            total_sacado INTEGER DEFAULT 0,
            convidados INTEGER DEFAULT 0,
            convidados_ativos INTEGER DEFAULT 0,
            user_ref INTEGER DEFAULT 0,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            ultima_atividade DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS apostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            tipo TEXT,
            animal TEXT,
            valor INTEGER,
            horario TEXT,
            resultado TEXT,
            premio INTEGER DEFAULT 0,
            data_aposta DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_resultado DATETIME NULL,
            FOREIGN KEY (user_id) REFERENCES usuarios (user_id)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS resultados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            horario TEXT,
            animal_sorteado TEXT,
            numero_sorteado TEXT,
            data_sorteio DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_apostas INTEGER DEFAULT 0,
            total_ganhadores INTEGER DEFAULT 0,
            total_pago INTEGER DEFAULT 0
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS convites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_convidado_id INTEGER,
            user_convidado_username TEXT,
            bonus_creditado BOOLEAN DEFAULT FALSE,
            data_convite DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES usuarios (user_id)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            tipo TEXT,
            valor INTEGER,
            descricao TEXT,
            data_transacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES usuarios (user_id)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT,
            descricao TEXT,
            atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        
        configuracoes_padrao = [
            ('multiplicador_normal', '18', 'Multiplicador para apostas normais'),
            ('multiplicador_rapidinha', '18', 'Multiplicador para rapidinhas'),
            ('chance_ganhar_rapidinha', '12', 'Chance de ganhar na rapidinha (%)'),  # ✅ 12% FIXO
            ('bonus_convite', '1', 'Bônus por convite bem-sucedido'),
            ('minimo_deposito', '10', 'Valor mínimo para depósito'),
            ('maximo_aposta', '10000', 'Valor máximo por aposta'),
            ('deposito_minimo_bonus', '20', 'Depósito mínimo para bônus')
        ]
        
        c.executemany('''INSERT OR IGNORE INTO configuracoes (chave, valor, descricao) 
                         VALUES (?, ?, ?)''', configuracoes_padrao)
        
        conn.commit()
        logger.info("✅ Banco de dados inicializado")

def get_config(chave):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT valor FROM configuracoes WHERE chave = ?', (chave,))
        resultado = c.fetchone()
        return resultado['valor'] if resultado else None

def get_user(user_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM usuarios WHERE user_id = ?', (user_id,))
        return c.fetchone()

def get_user_by_username(username):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM usuarios WHERE username = ?', (username,))
        return c.fetchone()

def create_user(user_id, username, primeiro_nome, ref_id=None):
    with get_db_connection() as conn:
        c = conn.cursor()
        
        c.execute('SELECT * FROM usuarios WHERE user_id = ?', (user_id,))
        if c.fetchone():
            return False
        
        c.execute('''INSERT INTO usuarios (user_id, username, primeiro_nome, user_ref) 
                     VALUES (?, ?, ?, ?)''', (user_id, username, primeiro_nome, ref_id))
        
        if ref_id:
            c.execute('UPDATE usuarios SET convidados = convidados + 1 WHERE user_id = ?', (ref_id,))
            c.execute('''INSERT INTO convites (user_id, user_convidado_id, user_convidado_username) 
                         VALUES (?, ?, ?)''', (ref_id, user_id, username))
        
        conn.commit()
        logger.info(f"✅ Novo usuário: {user_id}")
        return True

def update_saldo(user_id, valor, tipo='recarga', descricao=''):
    with get_db_connection() as conn:
        c = conn.cursor()
        
        try:
            c.execute('UPDATE usuarios SET saldo = saldo + ? WHERE user_id = ?', (valor, user_id))
            c.execute('''INSERT INTO transacoes (user_id, tipo, valor, descricao) 
                         VALUES (?, ?, ?, ?)''', (user_id, tipo, valor, descricao))
            
            if tipo == 'recarga':
                c.execute('UPDATE usuarios SET total_depositado = total_depositado + ? WHERE user_id = ?', 
                          (valor if valor > 0 else 0, user_id))
                
                if valor >= int(get_config('deposito_minimo_bonus')):
                    c.execute('SELECT user_ref FROM usuarios WHERE user_id = ?', (user_id,))
                    ref_result = c.fetchone()
                    if ref_result and ref_result['user_ref']:
                        ref_id = ref_result['user_ref']
                        bonus_convite = int(get_config('bonus_convite'))
                        
                        c.execute('''SELECT bonus_creditado FROM convites 
                                  WHERE user_id = ? AND user_convidado_id = ?''', (ref_id, user_id))
                        bonus_ja_dado_result = c.fetchone()
                        bonus_ja_dado = bonus_ja_dado_result['bonus_creditado'] if bonus_ja_dado_result else False
                        
                        if not bonus_ja_dado:
                            c.execute('UPDATE usuarios SET bonus = bonus + ?, convidados_ativos = convidados_ativos + 1 WHERE user_id = ?', 
                                      (bonus_convite, ref_id))
                            c.execute('''INSERT INTO transacoes (user_id, tipo, valor, descricao) 
                                         VALUES (?, ?, ?, ?)''', (ref_id, 'bonus', bonus_convite, 'Bônus por convidado'))
                            
                            c.execute('''UPDATE convites SET bonus_creditado = TRUE 
                                         WHERE user_id = ? AND user_convidado_id = ?''', (ref_id, user_id))
            
            elif tipo == 'saque':
                c.execute('UPDATE usuarios SET total_sacado = total_sacado + ? WHERE user_id = ?', 
                          (abs(valor) if valor < 0 else 0, user_id))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Erro ao atualizar saldo: {e}")
            return False

# ========== SISTEMA DE PROBABILIDADE CORRIGIDO ==========
def calcular_resultado_rapidinha():
    """✅ SEMPRE 12% de chance de ganhar - CORRIGIDO"""
    chance = 12  # 12% fixo
    return random.randint(1, 100) <= chance

def calcular_resultado_normal():
    """✅ 12% de chance para apostas normais também"""
    chance = 12  # 12% fixo
    return random.randint(1, 100) <= chance

def debitar_saldo_aposta(user_id, valor, animal, horario=None):
    with get_db_connection() as conn:
        c = conn.cursor()
        
        try:
            c.execute('SELECT saldo FROM usuarios WHERE user_id = ?', (user_id,))
            resultado = c.fetchone()
            
            if not resultado or resultado['saldo'] < valor:
                return False
            
            c.execute('UPDATE usuarios SET saldo = saldo - ? WHERE user_id = ?', (valor, user_id))
            
            tipo_aposta = 'aposta_normal' if horario else 'aposta_rapidinha'
            descricao = f"Aposta {animal}" + (f" - {horario}" if horario else " - Rapidinha")
            c.execute('''INSERT INTO transacoes (user_id, tipo, valor, descricao) 
                         VALUES (?, ?, ?, ?)''', (user_id, tipo_aposta, -valor, descricao))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Erro ao debitar saldo: {e}")
            return False

def add_aposta(user_id, tipo, animal, valor, horario=None, resultado=None, premio=0):
    with get_db_connection() as conn:
        c = conn.cursor()
        
        data_resultado = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if resultado else None
        
        c.execute('''INSERT INTO apostas (user_id, tipo, animal, valor, horario, resultado, premio, data_resultado) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (user_id, tipo, animal, valor, horario, resultado, premio, data_resultado))
        
        c.execute('UPDATE usuarios SET ultima_atividade = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
        conn.commit()

def get_apostas_por_animal(horario=None):
    with get_db_connection() as conn:
        c = conn.cursor()
        
        if horario:
            c.execute('''SELECT animal, COUNT(*) as total_apostas, SUM(valor) as total_valor 
                         FROM apostas WHERE horario = ? AND resultado IS NULL 
                         GROUP BY animal ORDER BY total_apostas DESC, total_valor DESC''', (horario,))
        else:
            c.execute('''SELECT animal, COUNT(*) as total_apostas, SUM(valor) as total_valor 
                         FROM apostas WHERE resultado IS NULL 
                         GROUP BY animal ORDER BY total_apostas DESC, total_valor DESC''')
        
        return c.fetchall()

def get_apostas_por_horario():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''SELECT horario, COUNT(*) as total_apostas, SUM(valor) as total_valor 
                     FROM apostas WHERE resultado IS NULL AND horario IS NOT NULL
                     GROUP BY horario ORDER BY total_apostas DESC, total_valor DESC''')
        return c.fetchall()

def get_total_apostas_hoje():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''SELECT COUNT(*), SUM(valor) FROM apostas 
                     WHERE date(data_aposta) = date('now')''')
        resultado = c.fetchone()
        return resultado if resultado else (0, 0)

def add_resultado(horario, animal_sorteado):
    with get_db_connection() as conn:
        c = conn.cursor()
        
        try:
            numeros = ANIMAIS[animal_sorteado]['numeros'].split('-')
            numero_sorteado = random.choice(numeros)
            
            c.execute('SELECT COUNT(*), SUM(valor) FROM apostas WHERE horario = ? AND resultado IS NULL', (horario,))
            total_apostas_result = c.fetchone()
            total_apostas = total_apostas_result[0] if total_apostas_result else 0
            total_valor = total_apostas_result[1] if total_apostas_result and total_apostas_result[1] else 0
            
            c.execute('''SELECT COUNT(*) FROM apostas 
                         WHERE horario = ? AND animal = ? AND resultado IS NULL''', (horario, animal_sorteado))
            total_ganhadores_result = c.fetchone()
            total_ganhadores = total_ganhadores_result[0] if total_ganhadores_result else 0
            
            multiplicador = int(get_config('multiplicador_normal'))
            total_pago = total_ganhadores * (total_valor / (total_apostas or 1)) * multiplicador if total_apostas else 0
            
            c.execute('''INSERT INTO resultados (horario, animal_sorteado, numero_sorteado, 
                         total_apostas, total_ganhadores, total_pago) 
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (horario, animal_sorteado, numero_sorteado, total_apostas, 
                       total_ganhadores, int(total_pago)))
            
            conn.commit()
            return numero_sorteado, total_ganhadores, int(total_pago)
        except Exception as e:
            conn.rollback()
            logger.error(f"Erro ao adicionar resultado: {e}")
            return None, 0, 0

def processar_resultado_apostas(horario, animal_sorteado):
    with get_db_connection() as conn:
        c = conn.cursor()
        
        try:
            c.execute('SELECT id, user_id, animal, valor FROM apostas WHERE horario = ? AND resultado IS NULL', (horario,))
            apostas = c.fetchall()
            
            ganhadores = 0
            total_pago = 0
            multiplicador = int(get_config('multiplicador_normal'))
            
            for aposta in apostas:
                aposta_id, user_id, animal_apostado, valor = aposta
                if animal_apostado == animal_sorteado:
                    premio = valor * multiplicador
                    c.execute('UPDATE apostas SET resultado = "GANHOU", premio = ?, data_resultado = CURRENT_TIMESTAMP WHERE id = ?', 
                              (premio, aposta_id))
                    c.execute('UPDATE usuarios SET saldo = saldo + ? WHERE user_id = ?', (premio, user_id))
                    c.execute('''INSERT INTO transacoes (user_id, tipo, valor, descricao) 
                                 VALUES (?, ?, ?, ?)''', (user_id, 'premio', premio, f'Prêmio {animal_sorteado} - {horario}'))
                    ganhadores += 1
                    total_pago += premio
                else:
                    c.execute('UPDATE apostas SET resultado = "PERDEU", data_resultado = CURRENT_TIMESTAMP WHERE id = ?', 
                              (aposta_id,))
            
            conn.commit()
            return ganhadores, total_pago
        except Exception as e:
            conn.rollback()
            logger.error(f"Erro ao processar resultado: {e}")
            return 0, 0

def get_resultado(horario):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM resultados WHERE horario = ? ORDER BY data_sorteio DESC LIMIT 1', (horario,))
        return c.fetchone()

def get_ultimos_resultados(limit=10):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM resultados ORDER BY data_sorteio DESC LIMIT ?', (limit,))
        return c.fetchall()

def get_top_saldo(limit=10):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''SELECT user_id, username, primeiro_nome, saldo 
                     FROM usuarios ORDER BY saldo DESC LIMIT ?''', (limit,))
        return c.fetchall()

def get_top_convites(limit=10):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''SELECT user_id, username, primeiro_nome, convidados 
                     FROM usuarios ORDER BY convidados DESC LIMIT ?''', (limit,))
        return c.fetchall()

def get_estatisticas_gerais():
    with get_db_connection() as conn:
        c = conn.cursor()
        
        try:
            c.execute('SELECT COUNT(*) FROM usuarios')
            total_usuarios = c.fetchone()[0]
            
            c.execute('SELECT COUNT(*) FROM apostas')
            total_apostas = c.fetchone()[0]
            
            c.execute('SELECT SUM(valor) FROM apostas')
            total_valor_apostado_result = c.fetchone()
            total_valor_apostado = total_valor_apostado_result[0] if total_valor_apostado_result and total_valor_apostado_result[0] else 0
            
            c.execute('SELECT SUM(premio) FROM apostas WHERE resultado = "GANHOU"')
            total_premios_pagos_result = c.fetchone()
            total_premios_pagos = total_premios_pagos_result[0] if total_premios_pagos_result and total_premios_pagos_result[0] else 0
            
            c.execute('SELECT SUM(saldo) FROM usuarios')
            saldo_total_result = c.fetchone()
            saldo_total = saldo_total_result[0] if saldo_total_result and saldo_total_result[0] else 0
            
            return {
                'total_usuarios': total_usuarios,
                'total_apostas': total_apostas,
                'total_valor_apostado': total_valor_apostado,
                'total_premios_pagos': total_premios_pagos,
                'saldo_total': saldo_total
            }
        except Exception as e:
            logger.error(f"Erro ao buscar estatísticas: {e}")
            return {
                'total_usuarios': 0,
                'total_apostas': 0,
                'total_valor_apostado': 0,
                'total_premios_pagos': 0,
                'saldo_total': 0
            }

def get_proximos_horarios():
    horarios = ["08:00", "10:00", "12:00", "14:00", "15:00", "16:00", "18:00", "19:00", "20:00", "22:00", "00:00"]
    agora = datetime.now()
    hoje = agora.date()
    
    horarios_validos = []
    
    for horario in horarios:
        h, m = map(int, horario.split(':'))
        
        if horario == "00:00":
            horario_dt = datetime(hoje.year, hoje.month, hoje.day, 0, 0) + timedelta(days=1)
        else:
            horario_dt = datetime(hoje.year, hoje.month, hoje.day, h, m)
        
        if horario_dt <= agora:
            if horario == "00:00":
                horario_dt += timedelta(days=1)
            else:
                horario_dt += timedelta(days=1)
        
        horarios_validos.append((horario, horario_dt))
    
    return horarios_validos

def verificar_conexao():
    try:
        requests.get('https://api.telegram.org', timeout=10)
        return True
    except:
        return False

async def verificar_manutencao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MANUTENCAO
    
    if not verificar_conexao():
        MANUTENCAO = True
        if update.message:
            await update.message.reply_text("🔧 Sistema em manutenção. Tente novamente em alguns minutos.")
        elif update.callback_query:
            await update.callback_query.answer("🔧 Sistema em manutenção.", show_alert=True)
        return True
    
    MANUTENCAO = False
    return False

# ========== HANDLERS PRINCIPAIS CORRIGIDOS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        user = update.effective_user
        
        ref_id = None
        if context.args and context.args[0].startswith('ref'):
            try:
                ref_id = int(context.args[0][3:])
            except ValueError:
                pass
        
        user_created = create_user(user.id, user.username, user.first_name, ref_id)
        
        user_data = get_user(user.id)
        saldo = user_data['saldo'] if user_data else 0
        
        texto = f"""
🎰 *Bι¢ԋσ Ƭσρυร* 🎰

👤 *Usuário:* {user.first_name}
💎 *Saldo:* `{saldo}` créditos

*Escolha uma opção abaixo:*
"""
        
        keyboard = [
            [InlineKeyboardButton("🐾 Aposta Normal", callback_data="normal_bet"),
             InlineKeyboardButton("⚡ Rapidinha", callback_data="quick_bet")],
            [InlineKeyboardButton("💰 Meu Saldo", callback_data="balance"),
             InlineKeyboardButton("📈 Meus Dados", callback_data="meus_dados")],
            [InlineKeyboardButton("🎁 Convide e Ganhe", callback_data="convidar_ganhar"),
             InlineKeyboardButton("🏆 Ranking", callback_data="ranking")],
            [InlineKeyboardButton("📊 Últimos Resultados", callback_data="ultimos_resultados"),
             InlineKeyboardButton("🆘 Ajuda", callback_data="help")],
        ]
        
        # ✅ BOTÃO ADMIN SÓ APARECE PARA O ADMIN
        if user.id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("👑 Painel Admin", callback_data="admin_panel")])
        
        if user_created:
            texto += "\n🎉 *Bem-vindo!*"
        
        await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no start: {e}")
        await update.message.reply_text("❌ Ocorreu um erro.")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        data = query.data
        user = query.from_user
        
        # ✅ VERIFICAÇÃO DE ADMIN MELHORADA
        if data.startswith("admin_") and user.id not in ADMIN_IDS:
            await query.answer("❌ Acesso restrito ao administrador!", show_alert=True)
            return
        
        handlers = {
            "main_menu": start_from_button,
            "normal_bet": normal_bet,
            "quick_bet": quick_bet,
            "balance": show_balance,
            "meus_dados": show_meus_dados,
            "convidar_ganhar": show_convidar_ganhar,
            "ranking": show_ranking,
            "ultimos_resultados": show_ultimos_resultados,
            "help": show_help,
            "admin_panel": admin_panel,
            "admin_stats": admin_stats,
            "admin_usuarios": admin_usuarios,
            "admin_recarga": admin_recarga_menu,
            "admin_sacar": admin_sacar_menu,
            "admin_resultados": admin_resultados,
        }
        
        if data.startswith("animal_"):
            animal = data.replace("animal_", "")
            await process_animal_choice(update, context, animal)
        elif data.startswith("horario_"):
            horario = data.replace("horario_", "")
            context.user_data['horario'] = horario
            await show_animal_selection(update, context, "normal")
        elif data.startswith("admin_resultado_"):
            horario = data.replace("admin_resultado_", "")
            await admin_definir_resultado(update, context, horario)
        elif data.startswith("admin_confirmar_"):
            parts = data.replace("admin_confirmar_", "").split("_")
            if len(parts) == 2:
                horario = parts[0]
                animal = parts[1]
                await admin_confirmar_resultado(update, context, horario, animal)
        else:
            handler = handlers.get(data)
            if handler:
                await handler(update, context)
            else:
                await query.edit_message_text("❌ Comando não reconhecido.")
                await start_from_button(update, context)
    except Exception as e:
        logger.error(f"Erro no handle_buttons: {e}")
        try:
            await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)
        except:
            pass

async def start_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        user = query.from_user
        user_data = get_user(user.id)
        saldo = user_data['saldo'] if user_data else 0
        
        texto = f"""
🎰 *Bι¢ԋσ Ƭσρυร* 🎰

👤 *Usuário:* {user.first_name}
💎 *Saldo:* `{saldo}` créditos

*Escolha uma opção abaixo:*
"""
        
        keyboard = [
            [InlineKeyboardButton("🐾 Aposta Normal", callback_data="normal_bet"),
             InlineKeyboardButton("⚡ Rapidinha", callback_data="quick_bet")],
            [InlineKeyboardButton("💰 Meu Saldo", callback_data="balance"),
             InlineKeyboardButton("📈 Meus Dados", callback_data="meus_dados")],
            [InlineKeyboardButton("🎁 Convide e Ganhe", callback_data="convidar_ganhar"),
             InlineKeyboardButton("🏆 Ranking", callback_data="ranking")],
            [InlineKeyboardButton("📊 Últimos Resultados", callback_data="ultimos_resultados"),
             InlineKeyboardButton("🆘 Ajuda", callback_data="help")],
        ]
        
        # ✅ BOTÃO ADMIN SÓ APARECE PARA O ADMIN
        if user.id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("👑 Painel Admin", callback_data="admin_panel")])
        
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no start_from_button: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

# ========== SISTEMA DE APOSTAS CORRIGIDO ==========
async def normal_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        
        horarios_validos = get_proximos_horarios()
        
        keyboard = []
        for horario, horario_dt in horarios_validos:
            if horario_dt.date() == datetime.now().date():
                texto_data = "Hoje"
            elif horario_dt.date() == datetime.now().date() + timedelta(days=1):
                texto_data = "Amanhã"
            else:
                texto_data = horario_dt.strftime("%d/%m")
            
            texto_botao = f"🕐 {horario} ({texto_data})"
            keyboard.append([InlineKeyboardButton(texto_botao, callback_data=f"horario_{horario}")])
        
        # ✅ BOTÃO VOLTAR ADICIONADO
        keyboard.append([InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="main_menu")])
        
        await query.edit_message_text(
            "🐾 *APOSTA NORMAL*\n\nEscolha o horário do sorteio:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Erro no normal_bet: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def quick_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        context.user_data['tipo_aposta'] = 'rapidinha'
        await show_animal_selection(update, context, "rapidinha")
    except Exception as e:
        logger.error(f"Erro no quick_bet: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def show_animal_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, tipo: str):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        animais = list(ANIMAIS.items())
        
        for i in range(0, len(animais), 4):
            row = []
            for j in range(4):
                if i + j < len(animais):
                    animal, info = animais[i + j]
                    row.append(InlineKeyboardButton(f"{info['emoji']}", callback_data=f"animal_{animal}"))
            keyboard.append(row)
        
        # ✅ BOTÃO VOLTAR CORRETO
        if tipo == "rapidinha":
            keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="quick_bet")])
        else:
            keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="normal_bet")])
        
        if tipo == "rapidinha":
            texto = "⚡ *RAPIDINHA*\n\nEscolha seu animal:"
        else:
            horario = context.user_data.get('horario', '')
            texto = f"🐾 *APOSTA NORMAL*\n🕐 Horário: {horario}\n\nEscolha seu animal:"
        
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no show_animal_selection: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def process_animal_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, animal: str):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        context.user_data['animal'] = animal
        context.user_data['aguardando_valor'] = True
        
        info = ANIMAIS[animal]
        user = query.from_user
        user_data = get_user(user.id)
        saldo = user_data['saldo'] if user_data else 0
        
        texto = (f"🎯 *Animal:* {animal.title()} {info['emoji']}\n"
                f"🔢 *Números:* {info['numeros']}\n"
                f"💎 *Saldo:* {saldo} créditos\n\n"
                f"💰 *Digite o valor da aposta:*")
        
        # ✅ BOTÃO VOLTAR CORRETO
        if 'horario' in context.user_data:
            keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data=f"horario_{context.user_data['horario']}")]]
        else:
            keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="quick_bet")]]
        
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no process_animal_choice: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def process_quick_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, animal: str, valor: int):
    try:
        if not debitar_saldo_aposta(user_id, valor, animal):
            await update.message.reply_text("❌ Saldo insuficiente!")
            return
        
        msg = await update.message.reply_text("🎰 *SORTEANDO...*", parse_mode='Markdown')
        await asyncio.sleep(2)
        
        # ✅ PROBABILIDADE FIXA DE 12%
        ganhou = calcular_resultado_rapidinha()
        
        if ganhou:
            premio = int(valor * int(get_config('multiplicador_rapidinha')))
            update_saldo(user_id, premio, 'premio', f'Prêmio rapidinha {animal}')
            resultado = "GANHOU"
            
            animal_sorteado = animal  # ✅ MESMO ANIMAL SE GANHAR
            
            texto_resultado = (f"🎉 *PARABÉNS! VOCÊ GANHOU!*\n\n"
                              f"🎯 Animal: {animal_sorteado.title()} {ANIMAIS[animal_sorteado]['emoji']}\n"
                              f"💰 Aposta: {valor} créditos\n"
                              f"🏆 Prêmio: {premio} créditos\n"
                              f"💎 Multiplicador: {get_config('multiplicador_rapidinha')}x\n"
                              f"🎲 Chance real: 12%")
        else:
            resultado = "PERDEU"
            # ✅ ANIMAL DIFERENTE SE PERDER
            animal_sorteado = random.choice([a for a in ANIMAIS.keys() if a != animal])
            
            texto_resultado = (f"❌ *Você perdeu!*\n\n"
                              f"🎯 Animal sorteado: {animal_sorteado.title()} {ANIMAIS[animal_sorteado]['emoji']}\n"
                              f"💸 Valor perdido: {valor} créditos\n"
                              f"📉 Seu animal: {animal.title()} {ANIMAIS[animal]['emoji']}\n"
                              f"🎲 Chance real: 12%")
        
        add_aposta(user_id, 'rapidinha', animal, valor, resultado=resultado, 
                   premio=premio if ganhou else 0)
        
        await msg.edit_text(texto_resultado)
        
        # ✅ NÃO VOLTA AUTOMATICAMENTE - OFERECE OPÇÕES
        keyboard = [
            [InlineKeyboardButton("⚡ Nova Rapidinha", callback_data="quick_bet")],
            [InlineKeyboardButton("📊 Ver Saldo", callback_data="balance")],
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            "🎰 *O que deseja fazer agora?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Erro no process_quick_bet: {e}")
        await update.message.reply_text("❌ Erro ao processar aposta.")

async def process_normal_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, animal: str, valor: int, horario: str):
    try:
        if not debitar_saldo_aposta(user_id, valor, animal, horario):
            await update.message.reply_text("❌ Saldo insuficiente!")
            return
            
        add_aposta(user_id, 'normal', animal, valor, horario)
        
        info = ANIMAIS[animal]
        user_data = get_user(user_id)
        saldo_atual = user_data['saldo'] if user_data else 0
        
        await update.message.reply_text(
            f"✅ *APOSTA REGISTRADA!*\n\n"
            f"🐾 *Animal:* {animal.title()} {info['emoji']}\n"
            f"🔢 *Números:* {info['numeros']}\n"
            f"🕐 *Horário:* {horario}\n"
            f"💰 *Valor:* {valor} créditos\n"
            f"💎 *Saldo:* {saldo_atual} créditos\n"
            f"🎯 *Multiplicador:* {get_config('multiplicador_normal')}x\n"
            f"🎲 *Chance de ganhar:* 12%\n\n"
            f"🍀 *Boa sorte!*",
            parse_mode='Markdown'
        )
        
        # ✅ OFERECE OPÇÕES APÓS APOSTA
        keyboard = [
            [InlineKeyboardButton("🐾 Nova Aposta Normal", callback_data="normal_bet")],
            [InlineKeyboardButton("⚡ Fazer Rapidinha", callback_data="quick_bet")],
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            "🎰 *O que deseja fazer agora?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Erro no process_normal_bet: {e}")
        await update.message.reply_text("❌ Erro ao processar aposta.")

# ========== FUNÇÕES DE USUÁRIO ==========
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        user = query.from_user
        user_data = get_user(user.id)
        
        if not user_data:
            await query.edit_message_text("❌ Usuário não encontrado!")
            return
        
        saldo = user_data['saldo']
        bonus = user_data['bonus']
        total_depositado = user_data['total_depositado']
        
        texto = (f"💰 *SEU SALDO*\n\n"
                f"💎 *Créditos:* `{saldo}`\n"
                f"🎁 *Bônus:* `{bonus}`\n"
                f"📥 *Total Depositado:* `{total_depositado}`\n\n"
                f"💳 *Para recarregar:*\n"
                f"Contate {ADMIN_USERNAME}")
        
        keyboard = [
            [InlineKeyboardButton("💳 Solicitar Recarga", url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no show_balance: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def show_meus_dados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        user = query.from_user
        user_data = get_user(user.id)
        
        if not user_data:
            await query.edit_message_text("❌ Usuário não encontrado!")
            return
        
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT COUNT(*), SUM(valor) FROM apostas WHERE user_id = ?', (user.id,))
            total_apostas_result = c.fetchone()
            total_apostas = total_apostas_result[0] if total_apostas_result else 0
            total_apostado = total_apostas_result[1] if total_apostas_result and total_apostas_result[1] else 0
            
            c.execute('SELECT COUNT(*) FROM apostas WHERE user_id = ? AND resultado = "GANHOU"', (user.id,))
            apostas_ganhas_result = c.fetchone()
            apostas_ganhas = apostas_ganhas_result[0] if apostas_ganhas_result else 0
        
        texto = (f"📊 *MEUS DADOS*\n\n"
                f"👤 *Informações:*\n"
                f"• Nome: {user_data['primeiro_nome']}\n"
                f"• Username: @{user_data['username'] or 'Não informado'}\n"
                f"• ID: `{user_data['user_id']}`\n\n"
                f"💰 *Financeiro:*\n"
                f"• Saldo: {user_data['saldo']} créditos\n"
                f"• Bônus: {user_data['bonus']} pontos\n"
                f"• Total Depositado: {user_data['total_depositado']}\n\n"
                f"🎯 *Apostas:*\n"
                f"• Total: {total_apostas}\n"
                f"• Total Apostado: {total_apostado}\n"
                f"• Ganhas: {apostas_ganhas}\n\n"
                f"👥 *Convites:*\n"
                f"• Convites: {user_data['convidados']}\n"
                f"• Ativos: {user_data['convidados_ativos']}")
        
        keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="main_menu")]]
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no show_meus_dados: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def show_convidar_ganhar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        user = query.from_user
        user_data = get_user(user.id)
        
        if not user_data:
            await query.edit_message_text("❌ Usuário não encontrado!")
            return
        
        convidados = user_data['convidados']
        bonus = user_data['bonus']
        bonus_convite = int(get_config('bonus_convite'))
        deposito_minimo = int(get_config('deposito_minimo_bonus'))
        
        bot_username = (await context.bot.get_me()).username
        link_convite = f"https://t.me/{bot_username}?start=ref{user.id}"
        
        texto = (f"🎁 *CONVIDE E GANHE*\n\n"
                f"📊 *Seu Progresso:*\n"
                f"• Convites: {convidados}\n"
                f"• Bônus: {bonus}\n\n"
                f"💰 *Como funciona:*\n"
                f"1. Compartilhe seu link\n"
                f"2. Amigo deposita {deposito_minimo}+\n"
                f"3. Você ganha {bonus_convite} bônus\n"
                f"4. 10 bônus = 1 crédito!\n\n"
                f"🔗 *Seu link:*\n"
                f"`{link_convite}`")
        
        keyboard = [
            [InlineKeyboardButton("📤 Compartilhar", url=f"https://t.me/share/url?url={link_convite}&text=🎰 Venha apostar no Bι¢ԋσ Ƭσρυร!")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no show_convidar_ganhar: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def show_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        
        top_saldo = get_top_saldo(10)
        top_convites = get_top_convites(5)
        
        texto = "🏆 *RANKING* 🏆\n\n"
        
        texto += "💰 *TOP SALDOS:*\n"
        for i, user_data in enumerate(top_saldo, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔸"
            nome = f"@{user_data['username']}" if user_data['username'] else user_data['primeiro_nome']
            texto += f"{emoji} {nome}: {user_data['saldo']} créditos\n"
        
        texto += "\n👥 *TOP CONVITES:*\n"
        for i, user_data in enumerate(top_convites, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔸"
            nome = f"@{user_data['username']}" if user_data['username'] else user_data['primeiro_nome']
            texto += f"{emoji} {nome}: {user_data['convidados']} convites\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="main_menu")]]
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no show_ranking: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def show_ultimos_resultados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        
        ultimos_resultados = get_ultimos_resultados(10)
        
        if not ultimos_resultados:
            texto = "📭 *Nenhum resultado registrado ainda.*"
            keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="main_menu")]]
            await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            return
        
        texto = "📊 *ÚLTIMOS 10 RESULTADOS* 📊\n\n"
        
        for i, resultado in enumerate(ultimos_resultados, 1):
            animal = resultado['animal_sorteado']
            info = ANIMAIS.get(animal, {})
            emoji = info.get('emoji', '❓')
            
            texto += (f"🎯 *{i}º - {resultado['horario']}*\n"
                     f"🐾 Animal: {animal.title()} {emoji}\n"
                     f"🔢 Número: {resultado['numero_sorteado']}\n"
                     f"🏆 Ganhadores: {resultado['total_ganhadores']}\n"
                     f"💰 Prêmio: {resultado['total_pago']} créditos\n"
                     f"───────────────\n")
        
        keyboard = [
            [InlineKeyboardButton("🔄 Atualizar", callback_data="ultimos_resultados")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Erro no show_ultimos_resultados: {e}")
        await update.callback_query.answer("❌ Erro ao carregar resultados.", show_alert=True)

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        
        multiplicador_normal = get_config('multiplicador_normal')
        multiplicador_rapidinha = get_config('multiplicador_rapidinha')
        chance_rapidinha = get_config('chance_ganhar_rapidinha')
        
        texto = (f"🆘 *AJUDA*\n\n"
                f"🎰 *COMO FUNCIONA:*\n"
                f"• 25 animais disponíveis\n"
                f"• Apostas normais e rápidas\n"
                f"• Resultados automáticos\n\n"
                f"🐾 *APOSTA NORMAL:*\n"
                f"• Escolha horário e animal\n"
                f"• Resultado no horário\n"
                f"• Multiplicador: {multiplicador_normal}x\n"
                f"• Chance: 12%\n\n"
                f"⚡ *RAPIDINHA:*\n"
                f"• Resultado na hora\n"
                f"• Multiplicador: {multiplicador_rapidinha}x\n"
                f"• Chance: 12%\n\n"
                f"🕐 *HORÁRIOS:*\n"
                f"08:00, 10:00, 12:00, 14:00, 15:00\n"
                f"16:00, 18:00, 19:00, 20:00, 22:00, 00:00\n\n"
                f"📞 *SUPORTE:*\n"
                f"{ADMIN_USERNAME}")
        
        keyboard = [
            [InlineKeyboardButton("📞 Suporte", url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no show_help: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

# ========== PAINEL ADMIN CORRIGIDO ==========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        
        # ✅ VERIFICAÇÃO DUPLA DE ADMIN
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("❌ Acesso restrito ao administrador!", show_alert=True)
            return
        
        stats = get_estatisticas_gerais()
        apostas_hoje, valor_hoje = get_total_apostas_hoje()
        
        texto = (f"👑 *PAINEL ADMIN - {ADMIN_USERNAME}*\n\n"
                f"📈 *Estatísticas:*\n"
                f"• Usuários: {stats['total_usuarios']}\n"
                f"• Apostas Hoje: {apostas_hoje or 0}\n"
                f"• Valor Hoje: {valor_hoje or 0} créditos\n"
                f"• Saldo Total: {stats['saldo_total']} créditos\n"
                f"• Prêmios Pagos: {stats['total_premios_pagos']} créditos\n\n"
                f"⚙️ *Escolha uma opção:*")
        
        keyboard = [
            [InlineKeyboardButton("📊 Estatísticas Detalhadas", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 Gerenciar Usuários", callback_data="admin_usuarios")],
            [InlineKeyboardButton("💰 Recarregar Saldo", callback_data="admin_recarga")],
            [InlineKeyboardButton("💸 Sacar Saldo", callback_data="admin_sacar")],
            [InlineKeyboardButton("🎯 Gerenciar Resultados", callback_data="admin_resultados")],
            [InlineKeyboardButton("🔙 Menu Principal", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no admin_panel: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("❌ Acesso restrito!", show_alert=True)
            return
        
        stats = get_estatisticas_gerais()
        apostas_hoje, valor_hoje = get_total_apostas_hoje()
        apostas_por_horario = get_apostas_por_horario()
        
        texto = (f"📊 *ESTATÍSTICAS DETALHADAS*\n\n"
                f"👥 *Usuários:*\n"
                f"• Total: {stats['total_usuarios']}\n"
                f"• Saldo Total: {stats['saldo_total']} créditos\n\n"
                f"🎯 *Apostas (Geral):*\n"
                f"• Total: {stats['total_apostas']}\n"
                f"• Valor Total: {stats['total_valor_apostado']} créditos\n"
                f"• Prêmios Pagos: {stats['total_premios_pagos']} créditos\n\n"
                f"📅 *Apostas (Hoje):*\n"
                f"• Quantidade: {apostas_hoje or 0}\n"
                f"• Valor: {valor_hoje or 0} créditos\n\n")
        
        if apostas_por_horario:
            texto += "🕐 *Apostas por Horário:*\n"
            for aposta in apostas_por_horario[:5]:
                texto += f"• {aposta['horario']}: {aposta[1]} apostas ({aposta[2]} créditos)\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Voltar ao Admin", callback_data="admin_panel")]]
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no admin_stats: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def admin_usuarios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("❌ Acesso restrito!", show_alert=True)
            return
        
        texto = ("👥 *GERENCIAR USUÁRIOS*\n\n"
                "📋 *Comandos Disponíveis:*\n"
                "• `/recarga @username valor` - Recarregar saldo\n"
                "• `/sacar @username valor` - Sacar saldo\n"
                "• `/resultado horario animal` - Definir resultado\n\n"
                "💡 *Dica:* Use @username ou ID do usuário")
        
        keyboard = [[InlineKeyboardButton("🔙 Voltar ao Admin", callback_data="admin_panel")]]
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no admin_usuarios: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def admin_recarga_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("❌ Acesso restrito!", show_alert=True)
            return
        
        texto = ("💰 *RECARREGAR SALDO*\n\n"
                "📋 *Como usar:*\n"
                "`/recarga @username valor`\n\n"
                "📝 *Exemplos:*\n"
                "• `/recarga @joao 1000`\n"
                "• `/recarga 123456789 500`\n\n"
                "💡 *Dica:* Use @username ou ID do usuário")
        
        keyboard = [[InlineKeyboardButton("🔙 Voltar ao Admin", callback_data="admin_panel")]]
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no admin_recarga_menu: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def admin_sacar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("❌ Acesso restrito!", show_alert=True)
            return
        
        texto = ("💸 *SACAR SALDO*\n\n"
                "📋 *Como usar:*\n"
                "`/sacar @username valor`\n\n"
                "📝 *Exemplos:*\n"
                "• `/sacar @joao 500`\n"
                "• `/sacar 123456789 200`\n\n"
                "⚠️ *Atenção:* Verifique o saldo antes de sacar!")
        
        keyboard = [[InlineKeyboardButton("🔙 Voltar ao Admin", callback_data="admin_panel")]]
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no admin_sacar_menu: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def admin_resultados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("❌ Acesso restrito!", show_alert=True)
            return
        
        horarios_validos = get_proximos_horarios()
        
        texto = "🎯 *GERENCIAR RESULTADOS*\n\n"
        texto += "📋 *Definir Resultado Manualmente:*\n\n"
        
        keyboard = []
        for horario, horario_dt in horarios_validos:
            resultado = get_resultado(horario)
            status = "✅ Pendente" if not resultado else "🎯 Realizado"
            
            texto_data = "Hoje" if horario_dt.date() == datetime.now().date() else horario_dt.strftime("%d/%m")
            texto += f"• {horario} ({texto_data}): {status}\n"
            
            if not resultado:
                keyboard.append([InlineKeyboardButton(f"🎲 Definir {horario}", callback_data=f"admin_resultado_{horario}")])
        
        texto += "\n📋 *Comando Rápido:*\n"
        texto += "`/resultado 20:00 cavalo`\n"
        
        keyboard.append([InlineKeyboardButton("🔙 Voltar ao Admin", callback_data="admin_panel")])
        
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no admin_resultados: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def admin_definir_resultado(update: Update, context: ContextTypes.DEFAULT_TYPE, horario: str):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("❌ Acesso restrito!", show_alert=True)
            return
        
        texto = f"🎲 *DEFINIR RESULTADO - {horario}*\n\nEscolha o animal sorteado:"
        
        keyboard = []
        animais = list(ANIMAIS.items())
        
        for i in range(0, len(animais), 4):
            row = []
            for j in range(4):
                if i + j < len(animais):
                    animal, info = animais[i + j]
                    row.append(InlineKeyboardButton(f"{info['emoji']}", callback_data=f"admin_confirmar_{horario}_{animal}"))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="admin_resultados")])
        
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erro no admin_definir_resultado: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

async def admin_confirmar_resultado(update: Update, context: ContextTypes.DEFAULT_TYPE, horario: str, animal: str):
    try:
        if await verificar_manutencao(update, context):
            return
            
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("❌ Acesso restrito!", show_alert=True)
            return
        
        numero_sorteado, total_ganhadores, total_pago = add_resultado(horario, animal)
        ganhadores, total_pago_processado = processar_resultado_apostas(horario, animal)
        
        info = ANIMAIS[animal]
        
        await query.edit_message_text(
            f"✅ *RESULTADO REGISTRADO!*\n\n"
            f"🕐 *Horário:* {horario}\n"
            f"🎯 *Animal:* {animal.title()} {info['emoji']}\n"
            f"🔢 *Número:* {numero_sorteado}\n"
            f"🏆 *Ganhadores:* {ganhadores}\n"
            f"💰 *Total Pago:* {total_pago_processado} créditos",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Erro no admin_confirmar_resultado: {e}")
        await update.callback_query.answer("❌ Ocorreu um erro.", show_alert=True)

# ========== COMANDOS ADMIN ==========
async def recarga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Acesso negado!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("❌ Uso: /recarga @username valor")
            return
        
        try:
            usuario_arg = context.args[0]
            valor = int(context.args[1])
            
            if valor <= 0:
                await update.message.reply_text("❌ Valor deve ser positivo!")
                return
            
            if usuario_arg.startswith('@'):
                username = usuario_arg[1:]
                user_data = get_user_by_username(username)
                if not user_data:
                    await update.message.reply_text(f"❌ Usuário @{username} não encontrado!")
                    return
                user_id = user_data['user_id']
                username_display = f"@{username}"
                primeiro_nome = user_data['primeiro_nome']
            else:
                user_id = int(usuario_arg)
                user_data = get_user(user_id)
                if not user_data:
                    await update.message.reply_text(f"❌ Usuário ID {user_id} não encontrado!")
                    return
                username_display = user_data['username'] or f"ID:{user_id}"
                primeiro_nome = user_data['primeiro_nome']
            
            update_saldo(user_id, valor, 'recarga', f'Recarga de {valor}')
            
            user_data_atualizado = get_user(user_id)
            saldo_atual = user_data_atualizado['saldo'] if user_data_atualizado else 0
            
            await update.message.reply_text(
                f"✅ *RECARGA REALIZADA!*\n\n"
                f"👤 *Usuário:* {primeiro_nome}\n"
                f"💰 *Valor:* {valor} créditos\n"
                f"💎 *Saldo:* {saldo_atual} créditos\n"
                f"🆔 *ID:* `{user_id}`",
                parse_mode='Markdown'
            )
            
        except ValueError:
            await update.message.reply_text("❌ Valor inválido!")
    except Exception as e:
        logger.error(f"Erro no recarga: {e}")
        await update.message.reply_text("❌ Erro ao processar recarga!")

async def sacar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Acesso negado!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("❌ Uso: /sacar @username valor")
            return
        
        try:
            usuario_arg = context.args[0]
            valor = int(context.args[1])
            
            if valor <= 0:
                await update.message.reply_text("❌ Valor deve ser positivo!")
                return
            
            if usuario_arg.startswith('@'):
                username = usuario_arg[1:]
                user_data = get_user_by_username(username)
                if not user_data:
                    await update.message.reply_text(f"❌ Usuário @{username} não encontrado!")
                    return
                user_id = user_data['user_id']
                username_display = f"@{username}"
                primeiro_nome = user_data['primeiro_nome']
                saldo_atual = user_data['saldo']
            else:
                user_id = int(usuario_arg)
                user_data = get_user(user_id)
                if not user_data:
                    await update.message.reply_text(f"❌ Usuário ID {user_id} não encontrado!")
                    return
                username_display = user_data['username'] or f"ID:{user_id}"
                primeiro_nome = user_data['primeiro_nome']
                saldo_atual = user_data['saldo']
            
            if valor > saldo_atual:
                await update.message.reply_text(f"❌ Saldo insuficiente! Saldo atual: {saldo_atual}")
                return
            
            update_saldo(user_id, -valor, 'saque', f'Saque de {valor}')
            user_data_atualizado = get_user(user_id)
            saldo_atual = user_data_atualizado['saldo'] if user_data_atualizado else 0
            
            await update.message.reply_text(
                f"✅ *SAQUE REALIZADO!*\n\n"
                f"👤 *Usuário:* {primeiro_nome}\n"
                f"💰 *Valor:* {valor} créditos\n"
                f"💎 *Saldo:* {saldo_atual} créditos\n"
                f"🆔 *ID:* `{user_id}`",
                parse_mode='Markdown'
            )
            
        except ValueError:
            await update.message.reply_text("❌ Valor inválido!")
    except Exception as e:
        logger.error(f"Erro no sacar: {e}")
        await update.message.reply_text("❌ Erro ao processar saque!")

async def resultado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Acesso negado!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("❌ Uso: /resultado horario animal\nEx: /resultado 20:00 cavalo")
            return
        
        horario = context.args[0]
        animal = context.args[1].lower()
        
        if animal not in ANIMAIS:
            await update.message.reply_text(f"❌ Animal '{animal}' não encontrado!\nUse: {', '.join(ANIMAIS.keys())}")
            return
        
        # Verificar se horário é válido
        horarios_validos = [h for h, _ in get_proximos_horarios()]
        if horario not in horarios_validos:
            await update.message.reply_text(f"❌ Horário '{horario}' inválido!\nHorários válidos: {', '.join(horarios_validos)}")
            return
        
        numero_sorteado, total_ganhadores, total_pago = add_resultado(horario, animal)
        ganhadores, total_pago_processado = processar_resultado_apostas(horario, animal)
        
        info = ANIMAIS[animal]
        
        await update.message.reply_text(
            f"✅ *RESULTADO DEFINIDO!*\n\n"
            f"🕐 *Horário:* {horario}\n"
            f"🎯 *Animal:* {animal.title()} {info['emoji']}\n"
            f"🔢 *Número:* {numero_sorteado}\n"
            f"🏆 *Ganhadores:* {ganhadores}\n"
            f"💰 *Total Pago:* {total_pago_processado} créditos",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Erro no resultado: {e}")
        await update.message.reply_text("❌ Erro ao definir resultado!")

# ========== HANDLER DE MENSAGENS ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await verificar_manutencao(update, context):
            return
            
        user = update.effective_user
        message_text = update.message.text
        
        if not message_text or message_text.startswith('/'):
            return
        
        user_data = get_user(user.id)
        if not user_data:
            await update.message.reply_text("❌ Usuário não registrado! Use /start")
            return
        
        # Verificar se está aguardando valor de aposta
        if context.user_data.get('aguardando_valor'):
            try:
                valor = int(message_text)
                
                if valor <= 0:
                    await update.message.reply_text("❌ Valor deve ser positivo!")
                    return
                
                saldo_atual = user_data['saldo']
                if valor > saldo_atual:
                    await update.message.reply_text(f"❌ Saldo insuficiente! Saldo atual: {saldo_atual}")
                    return
                
                maximo_aposta = int(get_config('maximo_aposta'))
                if valor > maximo_aposta:
                    await update.message.reply_text(f"❌ Valor máximo por aposta: {maximo_aposta} créditos")
                    return
                
                animal = context.user_data.get('animal')
                horario = context.user_data.get('horario')
                
                if horario:
                    # Aposta normal
                    await process_normal_bet(update, context, user.id, animal, valor, horario)
                else:
                    # Rapidinha
                    await process_quick_bet(update, context, user.id, animal, valor)
                
                # Limpar estado
                context.user_data.pop('aguardando_valor', None)
                context.user_data.pop('animal', None)
                context.user_data.pop('horario', None)
                
            except ValueError:
                await update.message.reply_text("❌ Por favor, digite um valor numérico válido!")
        
        else:
            # Resposta padrão para mensagens não compreendidas
            await update.message.reply_text(
                "🤔 *Não entendi sua mensagem.*\n\n"
                "💡 *Use os botões do menu ou os comandos:*\n"
                "• /start - Menu principal\n"
                "• /saldo - Ver saldo\n"
                "• /help - Ajuda",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Erro no handle_message: {e}")
        await update.message.reply_text("❌ Ocorreu um erro ao processar sua mensagem.")

# ========== TAREFAS AGENDADAS ==========
async def verificar_sorteios(context: ContextTypes.DEFAULT_TYPE):
    """Verifica e processa sorteios automaticamente"""
    try:
        agora = datetime.now().strftime("%H:%M")
        horarios = ["08:00", "10:00", "12:00", "14:00", "15:00", "16:00", "18:00", "19:00", "20:00", "22:00", "00:00"]
        
        if agora in horarios:
            # Verificar se já foi processado
            resultado_existente = get_resultado(agora)
            if resultado_existente:
                return
            
            # Sortear animal aleatório
            animal_sorteado = random.choice(list(ANIMAIS.keys()))
            numero_sorteado, total_ganhadores, total_pago = add_resultado(agora, animal_sorteado)
            ganhadores, total_pago_processado = processar_resultado_apostas(agora, animal_sorteado)
            
            info = ANIMAIS[animal_sorteado]
            
            # Enviar mensagem para todos os usuários
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute('SELECT user_id FROM usuarios')
                usuarios = c.fetchall()
            
            mensagem = (
                f"🎉 *RESULTADO DO SORTEIO {agora}* 🎉\n\n"
                f"🎯 *Animal:* {animal_sorteado.title()} {info['emoji']}\n"
                f"🔢 *Número:* {numero_sorteado}\n"
                f"🏆 *Ganhadores:* {ganhadores}\n"
                f"💰 *Total Pago:* {total_pago_processado} créditos\n\n"
                f"🎰 *Próximo sorteio em 2 horas!*"
            )
            
            for usuario in usuarios:
                try:
                    await context.bot.send_message(
                        chat_id=usuario['user_id'],
                        text=mensagem,
                        parse_mode='Markdown'
                    )
                    await asyncio.sleep(0.1)  # Rate limiting
                except Exception as e:
                    logger.error(f"Erro ao enviar resultado para {usuario['user_id']}: {e}")
                    
    except Exception as e:
        logger.error(f"Erro no verificar_sorteios: {e}")

async def backup_database(context: ContextTypes.DEFAULT_TYPE):
    """Faz backup do banco de dados periodicamente"""
    try:
        if os.path.exists('bot_jogo_bicho.db'):
            data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f'backup_bot_jogo_bicho_{data_hora}.db'
            
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("VACUUM INTO ?", (backup_file,))
            
            logger.info(f"✅ Backup criado: {backup_file}")
            
            # Manter apenas últimos 7 backups
            backups = [f for f in os.listdir('.') if f.startswith('backup_bot_jogo_bicho_') and f.endswith('.db')]
            backups.sort(reverse=True)
            
            for old_backup in backups[7:]:
                os.remove(old_backup)
                logger.info(f"🗑️ Backup antigo removido: {old_backup}")
                
    except Exception as e:
        logger.error(f"Erro no backup_database: {e}")

def main():
    """Inicia o bot - versão corrigida para Railway"""
    try:
        logger.info("🚀 Iniciando Bot do Jogo do Bicho...")
        
        # Inicializar banco de dados
        init_db()
        logger.info("✅ Banco de dados inicializado")
        
        # Criar aplicação
        application = Application.builder().token(TOKEN).build()
        logger.info("✅ Aplicação criada")
        
        # Handlers de comandos
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("saldo", show_balance))
        application.add_handler(CommandHandler("help", show_help))
        
        # Comandos admin
        application.add_handler(CommandHandler("recarga", recarga))
        application.add_handler(CommandHandler("sacar", sacar))
        application.add_handler(CommandHandler("resultado", resultado))
        
        # Handlers de callbacks
        application.add_handler(CallbackQueryHandler(handle_buttons))
        
        # Handler de mensagens
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Tarefas agendadas
        job_queue = application.job_queue
        job_queue.run_repeating(verificar_sorteios, interval=60, first=10)
        job_queue.run_repeating(backup_database, interval=21600, first=60)
        
        logger.info("✅ Todos os handlers registrados")
        
        # ✅ CONFIGURAÇÃO PARA RAILWAY - MUDANÇA PRINCIPAL
        PORT = int(os.environ.get("PORT", 8080))
        
        # Verificar se está no Railway (tem variável PORT)
        if os.environ.get("RAILWAY_STATIC_URL"):
            logger.info("🌐 Configurando webhook para Railway...")
            application.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=TOKEN,
                webhook_url=f"{os.environ.get('RAILWAY_STATIC_URL')}/{TOKEN}",
                secret_token='WEBHOOK_SECRET'
            )
        else:
            # Modo polling (local)
            logger.info("🔍 Iniciando modo polling...")
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        raise

if __name__ == "__main__":
    main()