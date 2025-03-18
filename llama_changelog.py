from together import Together
from tavily import TavilyClient

from lib.langchain_loader_changelog import query_vdb,vdb_init 


from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from llama_gitbook import handler as gitbook_handler

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

def rephrase(msg,search_result,deploy="remote"):
  messages =[
    {
      "role": "system",
      "content": f'''
      NSO in the question is in term of Cisco Network Services Ochestrator. Only use NSO to answer your question. Do not use full name of NSO. 
      Your answer will be used to search inside NSO Release Note.
      You will rephrase your question based on the following context

      <contexts>
      {search_result}
      </contexts>
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

def nr_detect(msg):
  eng_nr = re.search('ENG-[0-9]*', msg,re.IGNORECASE)
  bsp_nr = re.search('BEMS[0-9]*',  msg,re.IGNORECASE)
  cdets_nr = re.search('CSC-[a-z,A-Z,0-9]*', msg,re.IGNORECASE)
  ps_nr = re.search('PS-[0-9]*',  msg,re.IGNORECASE)
  rt_nr = re.search('RT-[0-9]*',  msg,re.IGNORECASE)
  #    metadata={"source": url,'Header 1': "NSO Version: "+str(ver),'Header 2':"ENG Number: "+str(eng_nr),'Header 3':"Component: "+str(type),'Header 4':"Relevent Case Number: "+str(case_nrs)}
  metas={}
  out={"ENG Number":eng_nr,"BEMs Number":bsp_nr,"CDETs Number":cdets_nr,"PS Number":ps_nr,"RT Number":rt_nr}
  check=False
  for key,value in out.items():
     if value:
        check=True
        if key == "ENG Number":
          metas['Header 2']="ENG Number: "+value.group()
        else:
          metas[key]=value.group()
  return (metas,check)

def keyword_scrapper(msg,deploy="remote"):
  messages =[
    {
      "role": "system",
      "content": f'''
      NSO in the question is in term of Cisco Network Services Ochestrator. Only use NSO to answer your question. Do not use full name of NSO. 
      List your answer in Json format
      Do not add description to your answer. 
      If there are version number mentioned in the question, include it in your answer. Otherwise ignore.
      '''
    }
  ]

  messages1=messages+[{
        "role": "user",
        "content": f'What feature in NSO is the following question asking about - "{msg}"? '
      }]
       
  stream=llama32(messages1,deploy)
  response=get_data(stream,deploy)
  data=""
  for str in response:
      data=data+str
  data_json=json.loads(data)
  output_json={"feature":data_json["feature"]}
  if "version" in data_json.keys():
     output_json["version"]=data_json["version"]
  return output_json


def context_extract(context,deploy="remote"):
  messages =[
    {
      "role": "system",
      "content": f'''
      NSO in the question is in term of Cisco Network Services Ochestrator. Only use NSO to answer your question. Do not use full name of NSO. 
      '''
    }
  ]

  messages1=messages+[{
        "role": "user",
        "content": f'Extract the key takeaway of the following context - "{context}"? '
      }]
       
  stream=llama32(messages1,deploy)
  response=get_data(stream,deploy)
  data=""
  for str in response:
      data=data+str
  return data

def obtain_info(msg):
  messages =  [HumanMessage(content="What is "+msg+" ?")]
  tech_detail=gitbook_handler(messages)
  data=""
  for str in tech_detail:
      data=data+str
  return data


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

  
  logger.info("Keyword Extraction")
  keyword=keyword_scrapper(msg,deploy="remote")
  logger.info(f"Keyword Extraction Done - {keyword}")

  logger.info("Technical Detail Extraction")
  tech_detail=obtain_info(keyword["feature"])
  logger.info(f"Technical Detail Extraction Done - {tech_detail}")

  logger.info("Extract Key Takeaway")
  takeaway=context_extract(tech_detail,deploy="remote")
  logger.info(f"Extract Key Takeaway - {takeaway}")

  logger.info("Rephrasing")
  rephrased_msg=rephrase(msg,takeaway,deploy=config['deploy_mode'])
  logger.info(f"Rephrased qestion Done - {rephrased_msg}")
  logger.info("Detecting ENG")
  nr=nr_detect(msg)
  logger.info(f"Detecting ENG Done - {nr}")



  general=""" 
      You are a Cisco NSO Expert that answer Cisco NSO related question based on NSO Change Note. The relevent Change Note will be provided as the contexts. 
      You must strictly follow the context and answer the question. 
      In the end of your answer, mention whatever source that you used to construct your answer. 
      Construct your answer in Markdown format.
  """
  logger.info("Extract from changelog vdb")
  search_result=query_vdb(rephrased_msg,nr,top_result=2)
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
  return response

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
