import re
import time
import requests
import json
import socket
from slackclient import SlackClient

FILE = open("/home/kyle/thatsthewrongword/secret.json", "r")
STRING_SECRETS = FILE.read()
SECRETS = json.loads(STRING_SECRETS)
FILE.close()

print("STARTUP")

LANGUAGE = 'en'

slack_client = SlackClient(SECRETS['slack_key'])

user_list = slack_client.api_call("users.list")

for user in user_list.get('members'):
    if user.get('name') == "dictionary_bot":
        slack_user_id = user.get('id')
        break

if slack_client.rtm_connect():
    print("Connected!")
    while True:
        for message in slack_client.rtm_read():

            if 'text' in message and re.findall(r"([Dd]efine: |[Ww]hat is |[Ww]hat\'s |[Ww]hats )([A-Za-z0-9][A-Za-z0-9 ]+)([\?\.\!]*)", message['text']):

                message_text = re.findall(r"([Dd]efine: |[Ww]hat is |[Ww]hat\'s |[Ww]hats )([A-Za-z0-9][_A-Za-z0-9 ]+)([\?\.\!]*)", message['text'])

                print("Message captured: ", message_text)

                word = message_text[0][len(message_text[0])-2]

                print("Word identified: ", word)
                
                error = 1

                while error:
                    random_word_url = "http://api.wordnik.com:80/v4/words.json/randomWord?hasDictionaryDef=true&includePartOfSpeech=noun&minCorpusCount=0&maxCorpusCount=0&minDictionaryCount=3&maxDictionaryCount=-1&minLength=5&maxLength=-1&api_key="+SECRETS['wordnik_key']
                    
                    response = requests.get(random_word_url)
                    random_word = response.json()['word']
                    print("random_word: ", random_word)

                    url = 'https://od-api.oxforddictionaries.com:443/api/v1/entries/' + LANGUAGE + '/' + random_word.lower()

                    response = requests.get(url, headers={'app_id': SECRETS['oxford_id'], 'app_key': SECRETS['oxford_key']})

                    try:
                        response = response.json()
                        definition = response['results'][0]['lexicalEntries'][0]['entries'][0]['senses'][0]['definitions'][0]
                        error = 0
                        formatted_response = "The definition of `{0}` is: {1}".format(word, definition)
                        print("Formatted response: ", formatted_response)
                    except:
                        print("need to get a new word")
                        error = 1


                slack_client.api_call(
                    "chat.postMessage",
                    channel=message['channel'],
                    text=formatted_response,
                    as_user=True)

        time.sleep(1)