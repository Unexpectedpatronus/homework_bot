import logging
import os
import time
from http import HTTPStatus

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
logging.basicConfig(
    level=logging.DEBUG,
    filename='global.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)


def check_tokens():
    """Функция проверяет доступность переменных окружения."""
    if not all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        logging.critical('Отсутствуют токены!')
        raise exceptions.InvalidTokens('Отсутствуют токены!')
    return True


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
        if response.status_code != HTTPStatus.OK:
            logging.error('ENDPOINT недоступен!')
            raise exceptions.StatusNotOk('ENDPOINT недоступен!')
        return response.json()
    except requests.exceptions.RequestException as error:
        logging.error(f'Ошибка при запросе к основному API: {error}')
    except ConnectionError:
        logging.error('Проблема с соединением!')
        raise ConnectionError('Проблема с соединением!')


def check_response(response):
    """Функция проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Response должен быть словарем!')
    if 'current_date' not in response:
        raise exceptions.EmptyValue('Отсутствует информация о дате домашки!')
    if 'homeworks' not in response:
        raise exceptions.EmptyValue('Отсутствует информация о домашке!')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Homeworks должен быть списком!')
    if len(response.get('homeworks')) > 0:
        if not isinstance(response.get('homeworks')[0], dict):
            raise TypeError('Элемент списка Homeworks должен быть словарем!')
        if 'status' not in response.get('homeworks')[0]:
            raise exceptions.EmptyValue('Отстутствует статус домашки!')
        if response.get('homeworks')[0]['status'] not in HOMEWORK_VERDICTS:
            raise exceptions.InvalidStatus(
                'Отсутствует валидный статус домашки!')
        return response.get('homeworks')[0]
    raise exceptions.EmptyValue('Отсутствует информация о домашней работе!')


def parse_status(homework):
    """Функция извлекает статус домашки."""
    if 'homework_name' not in homework:
        raise exceptions.EmptyValue('Отсутствует инфо о названии домашки!')
    if ('status' not in homework
            or homework.get('status') not in HOMEWORK_VERDICTS):
        raise exceptions.InvalidStatus('Отсутствует валидный статус!')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD
    send_message(bot, 'Бот включен.')
    last_error = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if len(homeworks) > 0:
                send_message(bot, parse_status(homeworks))
                timestamp = response['current_date']
        except Exception as error:
            exc_message = f'Сбой в работе программы: {error}'
            logging.error(exc_message)
            if exc_message != last_error:
                last_error = exc_message
                send_message(bot, exc_message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
