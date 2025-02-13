import os

from lib.gitbook_scraper import search
import os
import requests
from webex_api import send,webhook_reg


url=os.environ['OLLAMA_URL']
ollama_url=f'{url}/api/chat'



def ollama32(msg, model_name):
  payload={
  "model": model_name,
  "messages": msg,
  "stream": False,
  "options": {
    "num_ctx": 50000
  }
  }
  #print(ollama_url)
  r=requests.post(ollama_url,json = payload)
  #print(r.text)
  r_json=r.json()
  if r.status_code <200 and r.status_code >300:
        raise requests.exceptions.HTTPError
  elif 'error' in r_json:
     print(r_json['error'])
     raise Exception("Internal Error")
  return r_json


def print_data(response):
  print("\nAI> "+str(response), flush=True)

  


def get_data(stream):
  if len(stream['message']['content'])>0:
    return stream['message']['content']
  else:
    return "Error: AI provide empty reply"
