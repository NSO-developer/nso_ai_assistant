from lib.gitbook_scraper import search
import os
import requests
import time
import logging
import uuid



handler = logging.FileHandler("logs/ollama.log")        
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('ollama')
logger.setLevel(logging.INFO)
logger.addHandler(handler)



workspace=os.environ['WORKSPACE']
ip=os.environ['ANYTHINGLLM_IP']
port=os.environ['ANYTHINGLLM_PORT']
token=os.environ['ANYTHINGLLM_API_TOKEN']


anythingllm_url=f'http://{ip}:{port}/api/v1/workspace/{workspace}/chat'



def handler(msg,cec_in=""):
  sessionId=uuid.uuid4().hex
  logger.info("AI creating answer based on context")
  stream=ollama32(msg,sessionId)
  logger.info("AI creating answer based on context Done")
  response=get_data(stream)
  out=print_data(response,cec_in)
  return out

def ollama32(msg,sessionId):
  header={
    'accept': 'application/json',
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
  }

  payload={
  "message": msg,
  "mode": "chat",
  "sessionId": sessionId
  }
  r=requests.post(anythingllm_url, headers=header,json = payload)

  if r.status_code <200 and r.status_code >300:
        raise requests.exceptions.HTTPError
  return r.json()


def print_data(response,cec_in=""):
  print("\nAI> ")
  out=None
  if len(response)==0:
     out="ERROR: "+"Empty Reply from Ollama."
  else:
    out=response
  if len(cec_in) == 0:
    print(out)
  return out


def get_data(stream):
  r=stream['textResponse']
  if stream['error'] != None:
     logger.error("ERROR: "+stream['error'])
     print("ERROR: "+stream['error'])
  if len(r)==0:
     logger.error("ERROR: "+"Empty Reply from Ollama.")
     print("ERROR: "+"Empty Reply from Ollama.")
  out=r + "\nSource: \n"
  for source in stream['sources']:
     out=out+source['chunkSource']+"\n"
  return out

def main(msg,cec_in=""):
      start = time.time()
      response=handler(msg,cec_in)
      end = time.time()
      if len(cec_in) == 0:
        print(f"\nAverage execution time: {end - start}")
      return response + f"\nAverage execution time: {end - start}"
   

if __name__=="__main__":
    while True:
      msg = input('\nUser>\n')
      if msg.lower() == "exit":
          exit()
      else:
        main(msg,cec_in="")
