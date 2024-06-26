import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telegram import Bot
from telegram.ext import Updater

from exceptions import NoAPIAnswer

load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}

updater = Updater(token=TELEGRAM_TOKEN)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - Строка %(lineno)d - %(message)s",
    level=logging.ERROR,
)

handler = logging.StreamHandler(stream=sys.stdout)
logger = logging.getLogger(__name__)
logger.addHandler(handler)


def check_tokens():
    """Проверка наличия переменных окружений."""
    environment_variables = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    for varname, varvalue in environment_variables.items():
        if not varvalue:
            logging.critical(f"Отсутствует переменная окружения {varname}!")
            sys.exit()


def send_message(bot, message):
    """Отправка различных сообщений в Telegram-чат.

    Функция отправляет сообщение в Telegram-чат об изменении
    статуса домашней работы, а также об ошибках в работе бота.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug("Сообщение успешно отправлено в чат!")
    except Exception as error:
        logging.error(f"{error} - сообщение не отправлено в чат!")


def get_api_answer(timestamp):
    """Функция делает запрос к API и приводит ответ к типу данных Python."""
    try:
        payload = {"from_date": timestamp}
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload,
            timeout=10,
        )

    except Exception as error:
        message = "Ошибка! url-адрес недоступен!"
        logging.error(message)
        raise Exception(message, error)

    if homework_statuses.status_code != HTTPStatus.OK:
        message = "Ошибка! Неверный ответ сервера!"
        raise NoAPIAnswer(message)
    return homework_statuses.json()


def check_response(response):
    """Проверка правильного типа данных ответа API."""
    if not isinstance(response, dict):
        message = "Ответ API пришёл не в форме словаря!"
        logging.error(message)
        raise TypeError(message)
    elif "homeworks" not in response:
        message = "В ответе отсутствует ключ homeworks!"
        logging.error(message)
        raise KeyError(message)
    elif not isinstance(response.get("homeworks"), list):
        message = "Ответ API  под ключом homeworks не в форме списка!"
        logging.error(message)
        raise TypeError(message)


def parse_status(homework):
    """Функция выделяет из ответа API необходимые аргументы."""
    homework_keys = ['homework_name', 'status']
    for key in homework_keys:
        if key not in homework:
            message = f'В домашке отсутствует ключ {key}'
            logging.error(message)
            raise KeyError(message)

    if homework['status'] not in HOMEWORK_VERDICTS:
        message = "Неожиданное значение под ключём status"
        logging.error(message)
        raise KeyError(message)

    verdict = homework["status"]
    homework_name = homework["homework_name"]
    return (f'Изменился статус проверки работы "{homework_name}".'
            f'{HOMEWORK_VERDICTS[verdict]}')


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    send_message(bot, message="Начали парсинг!")
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks_list = response["homeworks"]
            if homeworks_list:
                actual_homework, *_ = homeworks_list
                message = parse_status(actual_homework)
                send_message(bot, message)
        except Exception as error:
            logging.error(f"Сбой в работе программы: {error}")
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
