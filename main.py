import telebot
import sqlite3
import time
import requests.exceptions
from dotenv import load_dotenv
import os
import logging
from datetime import datetime

from search.default_sizes import get_default_sizes
from search.prefixes import check_code_prefix
from search.search_matches import search_matches

# Проверяем, существует ли папка, если нет — создаем её
if not os.path.exists('temp'):
    os.makedirs('temp')

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Логирование в консоль
        logging.FileHandler("temp/bot.log", encoding="utf-8")  # Логирование в файл
    ]
)

load_dotenv('resources/.env')
TOKEN = os.getenv('TOKEN')

bot = telebot.TeleBot(TOKEN)

# Подключение к базе данных SQLite
def create_connection():
    try:
        conn = sqlite3.connect('resources/sizes.db')
        return conn
    except sqlite3.Error as e:
        logging.error(f"Ошибка подключения к базе данных: {e}")
        return None

def execute_query(query, params=None, fetch_all=False):
    """Выполняет SQL-запрос и возвращает результаты, если необходимо."""
    with create_connection() as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        if fetch_all:
            return cursor.fetchall()
        conn.commit()


# Создаём таблицу, если она не существует
def create_table():
    query = '''
        CREATE TABLE IF NOT EXISTS sizes (
            code TEXT PRIMARY KEY, 
            size TEXT,
            description TEXT
        )
    '''
    execute_query(query)

# Функция для загрузки данных из текстового файла
def load_data_from_file():
    try:
        file_path = 'resources/sizes.txt'

        # Проверка существования файла
        if not os.path.exists(file_path):
            logging.error(f"Файл {file_path} не найден.")
            return

        # Открываем текстовый файл и загружаем данные
        with open(file_path, 'r', encoding='utf-8') as txtfile:
            for line in txtfile:
                # Разделяем строку на код, размер и описание
                parts = line.strip().split(maxsplit=2)

                # Проверка, чтобы избежать ошибок, если строка не соответствует формату
                if len(parts) == 3:
                    code, size, description = parts
                    try:
                        # Вставляем данные в базу
                        execute_query("INSERT OR REPLACE INTO sizes (code, size, description) VALUES (?, ?, ?)",
                                      (code, size, description))
                    except Exception as db_error:
                        logging.error(f"Ошибка при вставке данных в базу для строки: {line.strip()} - {db_error}")
                else:
                    logging.warning(f"Ошибка в формате строки: {line.strip()}")

        logging.info("Данные из текстового файла успешно загружены в базу.")
    except Exception as e:
        logging.error(f"Ошибка при загрузке данных из текстового файла: {e}")

# Обработчик для логирования всех входящих сообщений
@bot.message_handler(update_types=['message'])
def log_all_messages(message):
    user = f"{message.chat.first_name} {message.chat.last_name} (@{message.chat.username})"
    text = message.text or "[Нет текста]"
    logging.info(f"Получено сообщение от {user}: {text}")


# Команда /update_db для загрузки данных из файла
@bot.message_handler(commands=['update_db'])
def update_database(message):
    try:
        load_data_from_file()
        logging.info(f"Команда /update_db выполнена пользователем: {message.from_user.username}")
        bot.reply_to(message, "База данных успешно обновлена из файла sizes.txt.")
    except Exception as e:
        logging.error(f"Ошибка при обновлении базы данных: {e}")
        bot.reply_to(message, f"Произошла ошибка при обновлении базы данных: {e}")

# Команда /export_db для экспорта данных в txt файл
@bot.message_handler(commands=['export_db'])
def export_database(message):
    try:
        # Получение всех данных из таблицы
        rows = execute_query("SELECT code, size, description FROM sizes", fetch_all=True)

        # Проверка на пустую базу данных
        if not rows:
            bot.reply_to(message, "База данных пуста. Нечего экспортировать.")
            logging.info(f"Пользователь {message.from_user.username} запросил экспорт, но база данных пуста.")
            return

        # Создание имени файла с временной меткой
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f'temp/exported_sizes_{timestamp}.txt'

        # Запись данных в файл
        try:
            with open(file_name, 'w', encoding='utf-8') as file:
                for code, size, description in rows:
                    file.write(f"{code} {size} {description}\n")
        except Exception as file_error:
            logging.error(f"Ошибка при записи данных в файл {file_name}: {file_error}")
            bot.reply_to(message, "Произошла ошибка при записи файла.")
            return

        # Отправка файла пользователю
        try:
            with open(file_name, 'rb') as file:
                bot.send_document(message.chat.id, file)

            # Уведомление об успешной операции
            bot.reply_to(message, f"Данные экспортированы в файл с {len(rows)} записями.")
            logging.info(f"Файл {file_name} успешно экспортирован пользователем {message.from_user.username}.")
        finally:
            # Удаление файла после отправки
            os.remove(file_name)
            logging.info(f"Файл {file_name} успешно удалён после отправки.")
    except Exception as e:
        logging.error(f"Ошибка при экспорте базы данных: {e}")
        bot.reply_to(message, f"Произошла ошибка при экспорте: {e}")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я твой бот. Напиши код, чтобы получить размеры!")
    logging.info(f"Команда /start от {message.from_user.username}.")


# Обработчик команды /add для добавления новых кодов и размеров
@bot.message_handler(commands=['add'])
def add_size(message):
    try:
        # Получаем текст после команды /add
        data = message.text.split(maxsplit=3)

        # Проверяем корректность ввода
        if len(data) != 4:
            bot.reply_to(message, "Используйте формат: /add <код> <размер> <описание>.\n"
                                  "Пример: /add 223002G4GC 60*45*40 ГБЦ")
            return

        code = data[1].strip()
        size = data[2].strip()
        description = data[3].strip()

        # Проверяем, что код и описание не пустые
        if not code or not description:
            bot.reply_to(message, "Код и описание не могут быть пустыми.")
            return

        # Проверяем корректность размера
        if not all(c.isdigit() or c == '*' for c in size) or size.count('*') != 2:
            bot.reply_to(message, "Размер должен быть в формате 'число*число*число', например, 60*45*40.")
            return

        # Добавляем данные в базу
        try:
            execute_query("INSERT OR REPLACE INTO sizes (code, size, description) VALUES (?, ?, ?)",
                          (code, size, description))

            bot.reply_to(message, f"Запись добавлена: {code} имеет размеры {size} и описание: {description}")
            logging.info(f"Добавлено: {code} имеет размеры {size} и описание: {description}")
        except Exception as db_error:
            logging.error(f"Ошибка базы данных при добавлении: {db_error}")
            bot.reply_to(message, "Произошла ошибка при добавлении записи в базу данных.")
    except Exception as e:
        # Общая обработка ошибок
        logging.error(f"Ошибка при добавлении нового кода, размера и описания: {e}")
        bot.reply_to(message, f"Произошла ошибка: {e}")

# Обработчик команды /up для обновления размеров
@bot.message_handler(commands=['up'])
def update_size(message):
    try:
        # Получаем текст после команды /up
        data = message.text.split(maxsplit=3)

        # Проверяем, правильно ли введены данные
        if len(data) != 4:
            bot.reply_to(message, "Используйте формат: /up <код> <новый_размер> <описание>."
                                  " Пример: /up 223002G4GC 60*45*45 ГБЦ")
            return

        code = data[1].strip()
        new_size = data[2].strip()
        description = data[3].strip()

        # Проверяем, существует ли код в словаре
        result = execute_query("UPDATE sizes SET size = ?, description = ? WHERE code = ?", (new_size, description, code))

        if result is None:
            logging.info(f"Код {code} не найден в базе данных.")
            bot.reply_to(message, f"Код {code} не найден в базе данных.")
        else:
            logging.info(f"Обновлено: {code} теперь имеет размеры {new_size} с описанием {description}")
            bot.reply_to(message, f"Обновлено: {code} теперь имеет размеры {new_size} с описанием {description}")

    except Exception as e:
        logging.error(f"Ошибка при обновлении размера: {e}")
        bot.reply_to(message, f"Произошла ошибка: {e}")

# Обработчик команды /up_key для обновления ключа
@bot.message_handler(commands=['up_key'])
def update_key(message):
    try:
        # Разбираем запрос пользователя
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, "Используйте команду в формате: /up_key <старый_ключ> <новый_ключ>")
            return

        # Извлекаем старый и новый ключи
        old_key, new_key = parts[1].strip(), parts[2].strip()

        # Проверяем, существует ли новый ключ в базе (с учётом регистра)
        query_check_new_key = "SELECT COUNT(*) FROM sizes WHERE code = ?"
        if execute_query(query_check_new_key, (new_key,), fetch_all=True)[0][0] > 0:
            bot.reply_to(message, f"Ключ '{new_key}' уже существует в базе данных. Обновление невозможно.")
            return

        # Проверяем наличие старого ключа (без учета регистра)
        query_check_old_key = "SELECT * FROM sizes WHERE UPPER(code) = ?"
        row = execute_query(query_check_old_key, (old_key.upper(),), fetch_all=True)

        if row:
            # Выполняем обновление ключа
            query_update_key = "UPDATE sizes SET code = ? WHERE UPPER(code) = ?"
            execute_query(query_update_key, (new_key, old_key.upper()))
            bot.reply_to(message, f"Ключ '{old_key}' успешно обновлён на '{new_key}'.")
            logging.info(f"Ключ '{old_key}' обновлён на '{new_key}' пользователем {message.from_user.username}.")
        else:
            bot.reply_to(message, f"Ключ '{old_key}' не найден в базе данных.")
            logging.info(f"Ключ '{old_key}' не найден в базе данных (запрос от {message.from_user.username}).")

    except Exception as e:
        logging.error(f"Ошибка при обновлении ключа: {e}")
        bot.reply_to(message, f"Произошла ошибка при обновлении ключа: {e}")

# Обработчик команды /del для удаления кода и его размера по полному совпадению
@bot.message_handler(commands=['del'])
def delete_size(message):
    try:
        # Получаем текст после команды /del
        data = message.text.split(maxsplit=1)

        # Проверяем, правильно ли введены данные
        if len(data) != 2:
            bot.reply_to(message, "Используйте формат: /del <код>. Пример: /del 223002G4GC")
            return

        code = data[1].strip()  # Получаем код

        # Удаляем код из базы данных по полному совпадению, игнорируя регистр
        query = "DELETE FROM sizes WHERE UPPER(code) = UPPER(?)"
        execute_query(query, (code,))

        # Проверка, существует ли код после удаления
        remaining = execute_query("SELECT COUNT(*) FROM sizes WHERE UPPER(code) = UPPER(?)", (code,), fetch_all=True)

        if remaining[0][0] == 0:
            logging.info(f"Код {code} успешно удалён.")
            bot.reply_to(message, f"Код {code} успешно удалён.")
        else:
            logging.info(f"Не удалось удалить код {code}.")
            bot.reply_to(message, f"Не удалось удалить код {code}. Код все еще существует в базе.")

    except Exception as e:
        logging.error(f"Ошибка при удалении кода и размера: {e}")
        bot.reply_to(message, f"Произошла ошибка: {e}")

# Обработчик команды /show_db для отображения всей базы данных
@bot.message_handler(commands=['show_db'])
def show_database(message):
    try:
        # Получение данных из базы данных
        query = "SELECT code, size, description FROM sizes"
        rows = execute_query(query, fetch_all=True)

        if rows:
            # Формирование содержимого файла
            content = "\n".join(f"{code} {size} {description}" for code, size, description in rows)

            # Создание имени файла с временной меткой
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_name = f'temp/Show_db_{timestamp}.txt'

            # Запись в файл в оперативной памяти
            with open(file_name, 'w', encoding='utf-8') as file:
                file.write(content)

            # Отправка файла пользователю
            with open(file_name, 'rb') as file:
                bot.send_document(message.chat.id, file)

            logging.info(f"Файл {file_name} успешно экспортирован пользователем {message.from_user.username}.")

            # Удаление файла после отправки
            os.remove(file_name)
            logging.info(f"Файл {file_name} успешно удалён после отправки.")
        else:
            bot.reply_to(message, "База данных пуста.")
            logging.info("База данных пуста. Ответ отправлен.")
    except Exception as e:
        logging.error(f"Ошибка при отображении базы данных: {e}")
        bot.reply_to(message, f"Произошла ошибка при получении данных из базы: {e}")

# Обработчик текстовых сообщений для поиска по коду или по его последним символам
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    query = message.text.strip()

    try:
        # Получаем данные из базы
        rows = execute_query("SELECT code, size, description FROM sizes", fetch_all=True)

        query_upper = query.upper()
        query_lower = query.lower()

        # Проверяем префиксы
        is_prefix = check_code_prefix(query_upper)

        # Ищем совпадения в базе данных
        matches = search_matches(rows, query_lower, query_upper)

        # Если совпадений нет, добавляем стандартные размеры
        if not matches:
            matches.extend(get_default_sizes(query_upper, is_prefix))

        # Формируем ответ
        response = "\n".join(matches) if matches else f"К сожалению, я не знаю размеры для '{query}'."

        # Отправляем ответ пользователю
        bot.reply_to(message, response)
        logging.info(f"Ответ на запрос '{query}' от {message.from_user.username}: \n{response}")

    except Exception as e:
        # Логируем ошибку
        logging.error(f"Ошибка при обработке запроса '{query}': {e}")
        bot.reply_to(message, "Произошла ошибка при обработке запроса.")


if __name__ == '__main__':
    try:
        # Инициализация базы данных
        create_table()
        logging.info("Таблица в базе данных успешно создана (если её не было).")

        while True:
            try:
                logging.info("Бот успешно инициализирован.")
                bot.infinity_polling(timeout=10, long_polling_timeout=5)

            except requests.exceptions.ProxyError as e:
                logging.error(f"Ошибка подключения к прокси: {e}. Перезапуск через 10 секунд...")
                time.sleep(10)

            except requests.exceptions.ConnectionError as e:
                logging.error(f"Ошибка соединения: {e}. Перезапуск через 10 секунд...")
                time.sleep(10)

            except Exception as e:
                logging.error(f"Неизвестная ошибка: {e}. Перезапуск через 10 секунд...")
                time.sleep(10)

    except KeyboardInterrupt:
        logging.info("Работа бота завершена вручную.")
    except Exception as e:
        logging.critical(f"Критическая ошибка при инициализации: {e}")
    finally:
        logging.info("Программа завершена.")
