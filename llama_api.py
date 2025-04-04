import json
from webex_api import send,webhook_reg
from tavily import TavilyClient
import os

tavily_client = TavilyClient(api_key=os.environ['TAVILY_API_KEY'])



config=None




def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data

def api_init():
    global config
    config=load_config()
    return config

api_init()
if config['deploy_mode'] == "remote":
  global together_mode
  if config['together_mode'] == "legacy":
    import requests 
    import os
    token=os.environ['TOGETHER_API_KEY']
  else:
    from together import Together
    client_local = Together()
    global client
    client=client_local
  together_mode=config['together_mode']

else:
  from ollama_api import ollama32
  from ollama_api import print_data as ollama_print_data
  from ollama_api import get_data as ollama_get_data
model_name=config['model_name']


def tavily(msg,extra_domain=[]): 
  response = tavily_client.search(
        query=msg,
        include_domains=["https://cisco-tailf.gitbook.io/nso-docs","https://www.cisco.com/"]+extra_domain,
        include_answer="basic",
        max_results=2
    )
  if len(response["results"]) > 0:
    for results in response["results"]:
      text="source: "+results["url"]+"\nresult: "+results["content"]
    answer=response["answer"]
    text=text+"\n"+answer
  else:
    text=None
  return text

def requests_llama32(msg):
  url = "https://api.together.xyz/v1/chat/completions"

  payload = {
    "model": f'{model_name}',
    "messages": f'{msg}'
   }
  headers = {
      "accept": "application/json",
      "content-type": "application/json",
      "authorization": f'Bearer {token}'
  }

  response = requests.post(url, json=payload, headers=headers,verify=False)
  return response.text

def llama32(msg, deploy="remote"):
  #print(msg)
  if deploy == "remote":
    if together_mode == "api":
      stream = client.chat.completions.create(
        model=f'{model_name}',
        #llama-3.3-70B-Instruct-Turbo-Free
        messages=msg,
        stream=True,
        temperature=0.6
      )
    else:
      stream=requests_llama32(msg)
  else:
    stream=ollama32(msg,model_name)
  return stream


def print_data(response, deploy="remote",intf="cli"):
  if intf=="cli":
    if deploy == "remote":
      print("\nAI> ")
      out=""
      for chunk in response:
            out=out+chunk
            print(chunk or "", end="", flush=True)
    else:
      out=ollama_print_data(response)
  elif intf=="webex":
    out=""
    if deploy == "remote":
      for chunk in response:
              out=out+chunk
    else:
      out=response
  else:
    print("Wrong Communication Interface")
  return out



def get_data(stream, deploy="remote"):
  if deploy == "remote":
    output=[]
    for chunk in stream:
      if len(chunk.choices[0].delta.content) !=0:
        output.append(chunk.choices[0].delta.content)
  else:
    output=ollama_get_data(stream)
  return output
