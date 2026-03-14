from flask import Flask
import mysql.connector
import redis
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Подключение к БД
mysql_config = {
    'host': os.getenv('MYSQL_HOST', 'mysql'),
    'user': os.getenv('MYSQL_USER', 'flask_user'),
    'password': os.getenv('MYSQL_PASSWORD', 'flaskpass'),
    'database': os.getenv('MYSQL_DB', 'flask_app')
}

# Подключение к Redis
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    decode_responses=True
)

@app.route('/')
def hello():
    return "Flask + MySQL + Redis работает!"

@app.route('/test-db')
def test_db():
    try:
        conn = mysql.connector.connect(**mysql_config)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return "MySQL подключение OK"
    except Exception as e:
        return f"MySQL ошибка: {str(e)}"

@app.route('/test-redis')
def test_redis():
    try:
        redis_client.set('test', 'Hello Redis!')
        value = redis_client.get('test')
        return f"Redis OK: {value}"
    except Exception as e:
        return f"Redis ошибка: {str(e)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
