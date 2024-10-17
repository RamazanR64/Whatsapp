import os
import requests
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
from datetime import datetime

# Загружаем переменные окружения из файла .env
load_dotenv()

# Настройки приложения
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DB_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация базы данных и миграций
db = SQLAlchemy(app)  # Инициализация SQLAlchemy
migrate = Migrate(app, db)  # Инициализация Flask-Migrate

# Модель для хранения информации о пользователях
class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    whatsapp_id = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    notifications = db.relationship('Notification', backref='client', lazy=True)

    def __repr__(self):
        return f'<Client {self.whatsapp_id}>'

# Модель для хранения истории сообщений
class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    message_text = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)

    def __repr__(self):
        return f'<Notification {self.message_text[:20]}>'

# Подключаем Green API
GREEN_API_URL = f"https://api.green-api.com/waInstance{os.getenv('INSTANCE_ID')}"
API_TOKEN = os.getenv('API_TOKEN')

# Функция для отправки сообщений
def send_message(chat_id, message_text):
    url = f'{GREEN_API_URL}/SendMessage/{API_TOKEN}'
    payload = {
        "chatId": chat_id,
        "message": message_text
    }
    response = requests.post(url, json=payload)
    return response.json()

# Эндпоинт для отправки сообщений
@app.route('/send_message', methods=['POST'])
def send_message_endpoint():
    data = request.json
    chat_id = data.get('chat_id')
    message_text = data.get('message_text')

    if not chat_id or not message_text:
        return jsonify({"error": "Параметры chat_id и message_text обязательны"}), 400

    client = Client.query.filter_by(whatsapp_id=chat_id).first()
    if not client:
        client = Client(whatsapp_id=chat_id)
        db.session.add(client)
        db.session.commit()

    response = send_message(chat_id, message_text)

    new_notification = Notification(
        message_text=message_text,
        client_id=client.id
    )
    db.session.add(new_notification)
    db.session.commit()

    return jsonify(response), 200

# Эндпоинт для обработки вебхуков
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    chat_id = data['senderData']['chatId']
    message = data['messageData'].get('textMessageData', {}).get('textMessage', "")

    client = Client.query.filter_by(whatsapp_id=chat_id).first()
    if not client:
        client = Client(whatsapp_id=chat_id)
        db.session.add(client)
        db.session.commit()

    new_notification = Notification(
        message_text=message,
        client_id=client.id
    )
    db.session.add(new_notification)
    db.session.commit()

    if message.lower() == "привет":
        send_message(chat_id, "Привет! Как я могу помочь?")
    else:
        send_message(chat_id, "Спасибо за ваше сообщение!")

    return jsonify({"status": "ok"}), 200

# Запуск приложения
if __name__ == '__main__':
    with app.app_context():  # Создаем контекст приложения
        db.create_all()  # Создание таблиц при запуске приложения
    app.run(debug=True)
