import json
import linecache
import logging
import os
import random
import re
import socket
import time

import requests
import slack

logging.basicConfig(
    format='%(asctime)s [MrDictionary] %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p'
)

logger = logging.getLogger()

FILE = open('./config.json', 'r')
CONFIG = json.loads(FILE.read())
FILE.close()

DICTIONARY_FILE = '/tmp/dictionary.txt'

REQUIRED_CONFIGS = set(
    ['slack_verification', 'slack_token', 'dictionary_key', 'thesaurus_key']
)
loaded_configs = set(CONFIG.keys())

try:
    assert loaded_configs.issubset(REQUIRED_CONFIGS)
    logger.info('Loaded config')
except Exception as e:
    logger.error(
        f'Required keys [{REQUIRED_CONFIGS.difference(loaded_configs)}] not found in config.')
    pass

LANGUAGE = 'en'


def download_file(url):
    if os.path.exists(DICTIONARY_FILE):
        return

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(DICTIONARY_FILE, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    return DICTIONARY_FILE


def get_random_word():
    random.seed()
    rand_word_index = random.randint(0, 81882)
    rand_word = linecache.getline(DICTIONARY_FILE, rand_word_index)
    if '%' in rand_word:
        rand_word = get_random_word()
    return rand_word.strip()


def define_word(word):
    url = f'https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key={CONFIG["dictionary_key"]}'
    response = requests.get(url)
    defs = [x.capitalize() for x in response.json()[0]['shortdef']]
    return defs


def formatted_response(random_word, definitions):
    if len(definitions) == 1:
        return f'{random_word.capitalize()} might mean the following!\n{definitions[0]}'

    return f"{random_word.capitalize()} might mean one of the following!\n{' | '.join(definitions)}"


def lambda_handler(event, context):

    logger.info(f"CONFIG: {CONFIG}")
    body = json.loads(event['body'])

    if 'challenge' in body:
        logger.info("Returning challenge response")
        return {
            'statusCode': 200,
            'body': body['challenge']
        }

    if body['token'] != CONFIG['slack_verification']:
        logger.warning("Returning for invalid signing")
        logger.info(f"body['token']: {body['token']}")
        logger.info(
            f"CONFIG['slack_verification']: {CONFIG['slack_verification']}"
        )
        return {
            'statusCode': 401,
            'body': 'Invalid signing'
        }

    client = slack.WebClient(token=CONFIG['slack_token'])

    user_list = client.users_list()

    mr_dictionary = list(filter(
        lambda user: user['is_bot'] and not user['deleted'] and 'dict' in user['name'],
        user_list['members']
    ))

    mr_dictionary = mr_dictionary[0]  # because list :/

    if body['event']['user'] == mr_dictionary['id']:
        logger.info("Returning for self response")
        logger.info(f"body['event']['user']: {body['event']['user']}")
        logger.info(f"mr_dictionary['id']: {mr_dictionary['id']}")
        return {
            'statusCode': 200,
            'body': 'no-op'
        }

    if 'text' in body['event'] and re.findall(r'([Dd]efine: |[Ww]hat is |[Ww]hat\'s |[Ww]hats )([^?^.^!].+?)([.?!]+|$)', body['event']['text']):
        message_text = re.findall(
            r'([Dd]efine: |[Ww]hat is |[Ww]hat\'s |[Ww]hats )([^?^.^!].+?)([.?!]+|$)', body['event']['text'])

        logger.info(f'Message captured: {message_text}')

        word = message_text[0][len(message_text[0])-2]

        logger.info(f'Word identified: {word}')

        dictionary_tries = 3

        while dictionary_tries:
            try:
                download_file(
                    'https://gist.githubusercontent.com/Kyle-Helmick/11ca009418c600c946a9a0de7a0987ba/raw/ff2cac9bce8a621c29c146b00d96b2db21b78be6/2of12inf.txt'
                )
                break
            except:
                dictionary_tries -= 1
                if dictionary_tries == 0:
                    logger.error(
                        "Returning for failing to download dictionary"
                    )
                    return {
                        'statusCode': 500,
                        'body': f'{DICTIONARY_FILE} failed to download'
                    }

        get_word_tries = 3

        while get_word_tries:
            random_word = get_random_word()
            logger.info(f'Random_word: {random_word}')

            try:
                definitions = define_word(random_word)
                if len(definitions) == 0:
                    raise Exception(
                        f'{random_word} did not have any definitions'
                    )
                break
            except:
                logger.error('Failed to pick word with definitions')
                get_word_tries -= 1
                if get_word_tries == 0:
                    logger.error(
                        "Returning for failing to pick word with definition"
                    )
                    return {
                        'statusCode': 500,
                        'body': 'Continuously failed to pick word with definitions'
                    }

        response_body = formatted_response(word, definitions)

        channel = body['event']['channel']

        client.chat_postMessage(
            channel=channel,
            text=response_body
        )

        logger.info("Returning for successful chat response")
        logger.info(f"channel: {channel}")
        logger.info(f"response_body: {response_body}")
        return {
            'statusCode': 200,
            'body': "Successful chat response"
        }
