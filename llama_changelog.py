from together import Together
from tavily import TavilyClient

from lib.langchain_loader_changelog import query_vdb,vdb_init 


from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from llama_api import *

import json
import os
import logging
import time
import re


try: 
    from BeautifulSoup import BeautifulSoup
except ImportError:
    from bs4 import BeautifulSoup


TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]


handler = logging.FileHandler("logs/llama_changelog.log")        
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('llama_changelog')
logger.setLevel(logging.INFO)
logger.addHandler(handler)




client = Together()
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

def rephrase(msg,deploy="remote"):
  messages =[
    {
      "role": "system",
      "content": f'''
      NSO in the question is in term of Cisco Network Services Ochestrator. Only use NSO to answer your question. Do not use full name of NSO. 
      Your answer will be used to search inside NSO Change Log.
      '''
    }
  ]

  messages=messages+[{
        "role": "user",
        "content": f'Can you rephrase and expend the question - "{msg}"? Your answer should only include the rephrased question in a string'
      }]
    
  stream=llama32(messages,deploy)
  response=get_data(stream,deploy)

  data=""
  for str in response:
        data=data+str
  data=data.replace("\"","")
  return data

def eng_detect(msg):
  eng_nr = re.search('/ENG-[1-9]*/', msg.upper())
  bsp_nr = re.search('/BSP-[1-9]*/', msg.upper())
  print(msg)
  print(eng_nr)
  return eng_nr



def handler(msgs):
  messages=[]
  for human_msg in msgs:
    if isinstance(human_msg, HumanMessage):
      messages.append({
        "role": "user",
        "content": human_msg.content
      })
    elif isinstance(human_msg, SystemMessage):
      messages.append({
        "role": "system",
        "content": human_msg.content
      })
    elif isinstance(human_msg, AIMessage):
      messages.append({
        "role": "assistant",
        "content": human_msg.content
      })
  msg=msgs[-1].content

  
  logger.info("Rephrasing")
  rephrased_msg=rephrase(msg,deploy=config['deploy_mode'])
  logger.info(f"Rephrased qestion Done - {rephrased_msg}")
  logger.info("Detecting ENG")
  eng_nr=eng_detect(msg)
  logger.info(f"Detecting ENG Done - {eng_nr}")


  general=""" 
      You are a Cisco NSO Expert that answer Cisco NSO related question based on NSO Change Note. The relevent Change Note will be provided as the contexts. 
      You must strictly follow the context and answer the question. 
      In the end of your answer, mention whatever source that you used to construct your answer. 
      Construct your answer in Markdown format.
  """
  logger.info("Extract from changelog vdb")
  search_result=query_vdb(rephrased_msg,eng_nr,top_result=2)
  logger.info(f"Extract from changelog vdb Done - {search_result}")

  systemPrompt = f'''
      {general}

      Here are the set of contexts:

      <contexts>
      {search_result}
      </contexts>
    `;
    '''

  logger.info(f'System Prompt: {systemPrompt}')
  messages.append({
                    "role": "system",
                    "content": systemPrompt,
                })
  
  logger.info(f"AI creating answer based on context - {messages}")
  stream=llama32(messages,config['deploy_mode'])
  logger.info("AI creating answer based on context Done")

  response=get_data(stream,config['deploy_mode'])
  out=print_data(response, deploy=config['deploy_mode'],intf=config['com_int'])
  return out

def changelog_init():
   logger.info("Initializing changelog vdb")
   vdb_init(True)
   logger.info("Initializing changelog vdb......Done")

def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data


if __name__=="__main__":
    vdb_init(True)
    while True:
       msg = input('\nUser>\n')
       if msg.lower() == "exit":
          exit()
       elif len(msg.lower()) ==0:
          "noop"
       else:
        start = time.time()
        messages =  [HumanMessage(content=msg)]
        handler(messages)
        end = time.time()
        print(f"\nAverage execution time: {end - start}")
