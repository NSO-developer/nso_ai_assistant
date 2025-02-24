from lib.gitbook_scraper import search
import logging
import time
from llama_code_generator import handler as code_gen_handler
from llama_code_generator import info_prep as code_gen_cache
from llama_api import *
import json
from webex_api import send,webhook_reg
import urllib.parse
from lib.langchain_loader import *
from lib.langchain_memory import *

import traceback


handler = logging.FileHandler("logs/llama.log")        
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('llama')
logger.setLevel(logging.INFO)
logger.addHandler(handler)


config=load_config()





def keyword_scrapper(msg,deploy="remote"):
  # messages = [
  #   {
  #     "role": "user",
  #     "content": f'what is the keyword of the question without verb - "{msg}"? list the keyword only in a string'
  #   }
  # ]

  # messages = [
  #   {
  #     "role": "user",
  #     "content": f'What knowledge do you need to answer this question correctly and accuratly - "{msg}"?list the knowledge only in a string'
  #   }
  # ]

  messages = [
    {
      "role": "system",
      "content": f'NSO in the question is in term of Cisco Network Services Ochestrator. Only use NSO to answer your question. Do not use full name of NSO.'
    },
    {
      "role": "user",
      "content": f'What keyword would you use to search on the searching engine in NSO Gitbook Guide to answer the following question accuratly - "{msg}"? Only provide your best choice.'
    }
  ]
  
  stream=llama32(messages,deploy)
  response=get_data(stream,deploy)

  data=""
  for str in response:
     data=data+str
  #print(data)
  return data


def define_purpose(msg,deploy="remote"):
  messages = [
    {
      "role": "user",
      "content": f'Define if this question is a general question or request a code generation  - {msg}. Do not analyze and explain, provide only absolute integer answer by following the instruction below.  Answer 1  - if the question is a general question. Answer 2 - if the question is a request for code generation'
    }
  ]
  
  stream=llama32(messages,deploy)
  response=get_data(stream,deploy)
  data=""
  for str in response:
     data=data+str
  #print(data)
  return data

def handler(history,msg,config):
  messages = history+[
    {
      "role": "user",
      "content": msg
    }
  ]
  #print(messages)
  
  logger.info("Getting keyword")
  keyword=keyword_scrapper(msg,config['deploy_mode'])
  logger.info("Keyword: "+keyword)

  logger.info("Searching Gitbook")
  search_result = search(keyword)
  logger.info("Searching Gitbook Done")
  logger.info("Gitbook Content: "+search_result)



  general='''
    You are a Cisco NSO Expert that answer Cisco NSO related question with the help of the context provided. 
    If you find the provided context is irrelevant, pleade ignore the provided context and use the other context that you find that are more relevant. 
    If there are code or command example in the context that can help you answering the question, please include them into your answer. At the same time, consider all scenrio in the context.
    In the end of your answer, mention whatever source that you used to construct your answer. 
    '''
  systemPrompt = f'''
    {general}

    Here are the set of contexts:

    <contexts>
    {search_result}
    </contexts>
  `;
  '''
  messages_backup=messages.copy()
  messages.append({
                    "role": "system",
                    "content": systemPrompt,
                })
  if config['get_content_type'] !="hybrid":
    logger.info("Getting support information from Tavily for tool")
    toolPrompt=tavily(msg)  
    logger.info("Getting support information from Tavily for tool Done")
  else:
     toolPrompt=None

  if toolPrompt:
    logger.info("Tavily return useful result. Support enabled. - "+ toolPrompt)
    messages.append({
                      "role": "tool",
                      "content": toolPrompt,
                  })
  try:
    logger.info("AI creating answer based on context")
    stream=llama32(messages,config['deploy_mode'])
    logger.info("AI creating answer based on context Done")
  except:
    logger.error(traceback.format_exc())
    logger.error("Error detected when trying to fetch answer from AI")
    if config["get_content_type"] == "hybrid":
      logger.info("Retry with Langchain 2 top result")
      query_vdb(query,top_result=2)
    else:
      logger.info("Retry with only 1 top result")
      search_result = search(keyword,top_result=1)
    systemPrompt = f'''
    {general}

    Here are the set of contexts:

    <contexts>
    {search_result}
    </contexts>
    `;
    '''
    messages_backup.append({
                    "role": "system",
                    "content": systemPrompt,
                })
    logger.info("AI creating answer based on context with one result")
    stream=llama32(messages_backup,config['deploy_mode'])
    logger.info("AI creating answer based on context with one result Done")

  response=get_data(stream,config['deploy_mode'])
  out=print_data(response, deploy=config['deploy_mode'],intf=config['com_int'])
  #print("response2:" + str(response))
  #print("out:" + out)

  return out

def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data


def main(msg,cache,cec_in=""):
    purpose=int(define_purpose(msg,config['deploy_mode']))
    if purpose == 1 or "how"  in msg.lower() or "what"  in msg.lower() or "when"  in msg.lower() or "why"  in msg.lower():
      if config["com_int"] == "cli":
         print("AI> \nSeems like you want some answer on general question. Let me think.....")           
      elif config["com_int"] == "webex":
        send(f"Hi {cec_in}. Let me think.....",cec=cec_in)
      start = time.time()
      hist=mem_retrive(cec_in,msg,count=4)
      response=handler(hist,msg,config)
      mem_add(cec_in,msg,response)
      #print("response1:" + response)
      end = time.time()
    elif purpose == 2 and "how" not in msg.lower() and "what" not in msg.lower() and "when" not in msg.lower() and "why" not in msg.lower():
      start = time.time()
      if config["com_int"] == "cli":
         print("AI> \nSeems like you want to generate some code. Let me think.....")
      elif config["com_int"] == "webex":
         send(f"Hi {cec_in}. Let me try to craft your code.....", cec=cec_in)
      logger.info("Preparing Cache")
      hist=mem_retrive(cec_in,msg,count=4)
      response=code_gen_handler(hist,msg,cache,config)
      mem_add(cec_in,msg,response)
      end = time.time()
    else:
      response=""
      send("ERROR: Undefined Purpose", cec=cec_in)
      logger.error("Undefined Purpose")

    comment="What%20do%20you%20want%20to%20see%20and%20how%20should%20it%20be%20improved."
    #print("msg:" + msg)
    #print("response:" + str(response))
    url_msg=urllib.parse.quote_plus(msg)
    url_response=urllib.parse.quote_plus(response)

    finish_text=f'''
      \nAverage execution time: {end - start}
      \nI did not do well? Leave me a [Feedback](https://github.com/NSO-developer/nso_ai_assistant/issues/new?title=Inaccurate%20Answer%20from%20AI&body=**Question**%0A{url_msg}%0A%0A**Answer%20from%20AI**%0A{url_response}%0A%0A**Expected%20Answer(Optional)**%0A{comment}&labels[]=bug) on Github 
      '''
    if len(cec_in) == 0:
      print(finish_text)
    else:
      return response + f'\n\nAverage execution time: {end - start}'

if __name__=="__main__":
    global cache
    print("Initializing.......")
    cache=code_gen_cache()
    if config["get_content_type"] == "langchain_rag":
      vdb_init(True)
    #api_init(config)
    logger.info("Deploy mode: "+ config['deploy_mode'])
    schedule_update()
    print("Initializing.......Done")
    cec_in = input('AI>\n Before we start, please let me know who you are. What is your Username?\nUser>\n')
    print(f"Hi {cec_in}. What can I help you about Cisco NSO today?")
    while True:
      msg = input('\nUser>\n')
      if len(msg)==0:
         continue
      elif msg.lower() == "exit":
          exit()
      else:
          main(msg,cache,cec_in)