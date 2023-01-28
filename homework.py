import logging
import os
import time
from http import HTTPStatus
from json.decoder import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = os.getenv('ENDPOINT')
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Функция проверяет доступность переменных окружения."""
    if not all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        logging.critical('Отсутствуют токены!')
        raise exceptions.InvalidTokens('Отсутствуют токены!')


def send_message(bot, message):
    """Функция отправки сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Отправлено сообщение: "{message}"')
    except Exception as error:
        logging.error(f'Сбой отправки сообщения. Ошибка: "{error}"')


def get_api_answer(timestamp):
    """Функция делает запрос к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        logging.info('Отправление запроса к API Яндекс.Практикум')
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
    except requests.RequestException as error:
        raise exceptions.ApiException(
            f'Эндпоинт {ENDPOINT} недоступен. {error}')
    if response.status_code != HTTPStatus.OK:
        raise exceptions.ApiException(
            f'Эндпоинт {ENDPOINT} недоступен')
    try:
        return response.json()
    except JSONDecodeError as error:
        raise exceptions.ApiException(
            f'Ответ сервера не удалось преобразовать в JSON. {error}')


def check_response(response):
    """Функция проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Response должен быть словарем!')
    if 'current_date' not in response:
        raise exceptions.EmptyValue(
            'Отсутствует информация о времени ответа сервера!')
    if 'homeworks' not in response:
        raise exceptions.EmptyValue('Отсутствует информация о домашке!')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Homeworks должен быть списком!')
    return response.get('homeworks')


def parse_status(homeworks):
    """Функция извлекает статус домашки."""
    if 'homework_name' in homeworks:
        homework_name = homeworks['homework_name']
    else:
        raise KeyError('Отсутствует ключ "homework_name"!')
    if 'status' in homeworks:
        status = homeworks['status']
        if status in HOMEWORK_VERDICTS:
            verdict = HOMEWORK_VERDICTS[status]
            return (f'Изменился статус проверки работы'
                    f' "{homework_name}". {verdict}')
        else:
            raise exceptions.InvalidStatus('Отсутствует валидный статус')
    else:
        raise KeyError('Отсутствует ключ статуса домашки!')


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    month = 2592000
    timestamp = int(time.time()) - month
    send_message(bot, 'Бот включен.')
    last_message = ''
    while True:
        check_tokens()
        try:
            response = get_api_answer(timestamp)
            timestamp = response['current_date']
            homeworks = check_response(response)
            if len(homeworks) > 0:
                send_message(bot, parse_status(homeworks[0]))
        except Exception as error:
            exc_message = f'Сбой в работе программы: {error}'
            logging.error(exc_message)
            if exc_message != last_message:
                last_message = exc_message
                send_message(bot, exc_message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename='global.log',
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
    )
    main()
