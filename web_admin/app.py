"""Веб-админка для управления ботом Олег."""

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
import os
from datetime import datetime, timedelta
import asyncio
import json

# Импорты для работы с базой данных бота
from app.database.session import get_session
from app.database.models import User, GameStat, MessageLog
from sqlalchemy import select, func

# Используем вспомогательные функции для асинхронной работы
from .utils import run_async


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('ADMIN_SECRET_KEY', 'oleg_bot_secret_key_change_me')
    app.config['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', 'admin')
    app.config['ADMIN_PASSWORD_HASH'] = generate_password_hash(
        os.environ.get('ADMIN_PASSWORD', 'oleg123')
    )

    return app


app = create_app()


def login_required(f):
    """Декоратор для защиты маршрутов."""
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Проверяем учетные данные
        if (username == app.config['ADMIN_USERNAME'] and 
            check_password_hash(app.config['ADMIN_PASSWORD_HASH'], password)):
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash('Неправильное имя пользователя или пароль', 'error')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    """Главная страница админки."""
    def get_dashboard_data():
        async def _get_data():
            async_session = get_session()

            # Получаем основную статистику
            async with async_session() as session:
                # Количество пользователей
                user_count_res = await session.execute(select(func.count(User.id)))
                user_count = user_count_res.scalar()

                # Количество активных пользователей за последние 24 часа
                yesterday = datetime.utcnow() - timedelta(hours=24)
                active_users_res = await session.execute(
                    select(func.count(User.id)).where(User.created_at >= yesterday)
                )
                active_users_count = active_users_res.scalar()

                # Количество сообщений за последние 24 часа
                message_count_res = await session.execute(
                    select(func.count(MessageLog.id)).where(MessageLog.created_at >= yesterday)
                )
                message_count = message_count_res.scalar()

                # Топ-10 пользователей по размеру "пиписи"
                top_users_res = await session.execute(
                    select(GameStat).order_by(GameStat.size_cm.desc()).limit(10)
                )
                top_users = top_users_res.scalars().all()

                return {
                    'user_count': user_count,
                    'active_users_count': active_users_count,
                    'message_count': message_count,
                    'top_users': top_users
                }

        return run_async(_get_data())

    data = get_dashboard_data()

    return render_template(
        'dashboard.html',
        user_count=data['user_count'],
        active_users_count=data['active_users_count'],
        message_count=data['message_count'],
        top_users=data['top_users']
    )


@app.route('/users')
@login_required
def users():
    """Страница управления пользователями."""
    def get_users_data():
        async def _get_data():
            async_session = get_session()

            async with async_session() as session:
                # Получаем всех пользователей с их игровой статистикой
                users_res = await session.execute(
                    select(User, GameStat)
                    .outerjoin(GameStat, User.id == GameStat.user_id)
                    .order_by(User.created_at.desc())
                )
                users_data = users_res.all()

                return users_data

        return run_async(_get_data())

    users_data = get_users_data()

    return render_template('users.html', users_data=users_data)


@app.route('/logs')
@login_required
def logs():
    """Страница просмотра логов."""
    # В реальной реализации здесь будет показ лог-файлов
    # или логов из базы данных
    logs = []

    # Читаем последние логи из файла
    log_file = "logs/oleg.log"
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Берем последние 50 строк
                logs = lines[-50:]
        except:
            logs = ["Не удалось прочитать лог-файл"]

    return render_template('logs.html', logs=logs)


@app.route('/moderation', methods=['GET', 'POST'])
@login_required
def moderation():
    """Страница модерации."""
    current_mode = "normal"  # значение по умолчанию

    # В реальной реализации здесь будет получение текущего режима из базы данных
    # или кэша

    # Если это POST запрос - изменение режима
    if request.method == 'POST':
        mode = request.form.get('mode')
        if mode in ['light', 'normal', 'dictatorship']:
            # Здесь должна быть логика изменения режима модерации в базе данных
            flash(f'Режим модерации изменен на: {mode}', 'success')

            # В реальной реализации вызываем функцию установки режима
            # await set_moderation_mode(chat_id, mode)

    return render_template('moderation.html', current_mode=current_mode)


@app.route('/moderation/set_mode/<mode>')
@login_required
def set_mode(mode):
    """Установка режима модерации."""
    if mode in ['light', 'normal', 'dictatorship']:
        # В реальной реализации вызываем функцию установки режима
        # await set_moderation_mode(chat_id, mode)
        flash(f'Режим модерации изменен на: {mode}', 'success')

    return redirect(url_for('moderation'))


@app.route('/settings')
@login_required
def settings():
    """Страница настроек."""
    return render_template('settings.html')


# Добавим простую страницу статистики
@app.route('/stats')
@login_required
def stats():
    """Страница статистики чата."""
    def get_stats_data():
        async def _get_data():
            async_session = get_session()

            async with async_session() as session:
                # Общая статистика
                user_count_res = await session.execute(select(func.count(User.id)))
                user_count = user_count_res.scalar()

                # Статистика за последние 24 часа
                yesterday = datetime.utcnow() - timedelta(hours=24)

                message_count_res = await session.execute(
                    select(func.count(MessageLog.id)).where(MessageLog.created_at >= yesterday)
                )
                message_count = message_count_res.scalar()

                # Топ-10 активных пользователей
                active_users_res = await session.execute(
                    select(
                        User.username,
                        func.count(MessageLog.id).label('message_count')
                    )
                    .join(MessageLog, User.tg_user_id == MessageLog.user_id)
                    .where(MessageLog.created_at >= yesterday)
                    .group_by(User.username)
                    .order_by(func.count(MessageLog.id).desc())
                    .limit(10)
                )
                active_users = active_users_res.all()

                return {
                    'user_count': user_count,
                    'message_count': message_count,
                    'active_users': active_users
                }

        return run_async(_get_data())

    data = get_stats_data()

    return render_template(
        'stats.html',
        user_count=data['user_count'],
        message_count=data['message_count'],
        active_users=data['active_users']
    )


if __name__ == '__main__':
    # Запуск dev-сервера
    app.run(debug=True, host='0.0.0.0', port=5000)