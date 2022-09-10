import requests
import json
import time
import pathlib
import os
import argparse
from dotenv import load_dotenv

load_dotenv()

def get_PIN_code(userid):
    url = f"https://api.simkl.com/oauth/pin?client_id={userid}"

    headers = {
        'Content-Type': 'application/json'
    }

    request_data = json.loads(requests.get(url, headers=headers).text)

    if request_data['result'] == 'OK':
        return request_data
    return None

def retrieveToken(user_code, expires_in, interval, userid):
    url = f"https://api.simkl.com/oauth/pin/{user_code}?client_id={userid}"

    headers = {
        'Content-Type': 'application/json'
    }
    # start polling
    access_token = ''

    t_end = time.time() + expires_in
    while time.time() < t_end:
        request_data = json.loads(requests.get(url, headers=headers).text)
        if 'access_token' in request_data:
            return request_data['access_token']
            break
        time.sleep(interval)
    print("Code expired.")
    return None

def main(simkluser):
    filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'simkl_api_id.txt')

    simkl_client_id = os.getenv('SIMKL_CLIENTID')

    headers = {
        'Content-Type': 'application/json'
    }

    data = get_PIN_code(simkl_client_id)
    if data:
        print ("Enter this code at https://simkl.com/pin/: %s" % data['user_code'])
        token = retrieveToken(data['user_code'], data['expires_in'], data['interval'], simkl_client_id)
    
    # save token at the appropriate folder
    filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'simkl_tokens')
    pathlib.Path(filepath).mkdir(parents=True, exist_ok=True) 

    if token:
        with open(os.path.join(filepath, f'{simkluser}.txt'), "w") as text_file:
            print(f"{token}", file=text_file)
        print("Success.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--simkl', required=True)
    opts = parser.parse_args()
    main(opts.simkl)