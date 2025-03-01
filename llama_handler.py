from lib.gitbook_scraper import search
import logging
import time
from llama_code_generator import handler as code_gen_handler
from llama_code_generator import info_prep as code_gen_cache
from llama_api import *
import json
from webex_api import send
import urllib.parse
from lib.langchain_loader import *
from lib.langchain_memory import mem_retrive,mem_add

import traceback


handler = logging.FileHandler("logs/llama.log")        
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('llama')
logger.setLevel(logging.INFO)
logger.addHandler(handler)


config=load_config()


def rephrase(msg,deploy="remote"):
  messages =[
    {
      "role": "system",
      "content": f'''
      NSO in the question is in term of Cisco Network Services Ochestrator. Only use NSO to answer your question. Do not use full name of NSO. 
      Doc,doc and documentation is in term of NSO Gitbook Documentation.
      '''
    }
  ]

  messages=messages+[{
        "role": "user",
        "content": f'Can you rephrase and expend the question - "{msg}"? Your answre should only include the rephrased question in a string'
      }]
    
  stream=llama32(messages,deploy)
  response=get_data(stream,deploy)

  data=""
  for str in response:
        data=data+str
  data=data.replace("\"","")
  return data



def keyword_scrapper(msg,mode,deploy="remote"):
  data_gitbook=None
  data_langchain=None

  rephrased_msg=rephrase(msg,deploy=deploy)
  logger.info(f"Rephrased qestion - {rephrased_msg}")

  messages =[
    {
      "role": "system",
      "content": f'''
      NSO in the question is in term of Cisco Network Services Ochestrator. Only use NSO to answer your question. Do not use full name of NSO. 
      Doc,doc and documentation is in term of NSO Gitbook Documentation.
      '''
    }
  ]

  if mode == "gitbook_search":
    messages=messages+[{
        "role": "user",
        "content": f'What keyword would you use to search on the searching engine in NSO Gitbook Guide to answer the following question accuratly - "{rephrased_msg}"? Only provide your best choice.'
      }]
    stream=llama32(messages,deploy)
    response=get_data(stream,deploy)

    data_gitbook=""
    for str in response:
      data_gitbook=data_gitbook+str      

  elif mode == "langchain_rag":
    data_langchain=rephrased_msg
  elif mode == "hybrid":
    messages1=messages+[{
        "role": "user",
        "content": f'What keyword would you use to search on the searching engine in NSO Gitbook Guide to answer the following question accuratly - "{rephrased_msg}"? Only provide your best choice.'
      }]
       
    stream=llama32(messages1,deploy)
    response=get_data(stream,deploy)

    data_gitbook=""
    for str in response:
      data_gitbook=data_gitbook+str
    data_langchain=rephrased_msg
  if data_gitbook:
    data_gitbook=data_gitbook.replace("\"","")
  return (data_gitbook,data_langchain)


def define_purpose(msg,deploy="remote"):
  messages = [
    {
      "role": "user",
      "content": f'Define if this question is a general question or request a code generation  - {msg}. Your answer should not provide any Explanation, provide only absolute integer answer by following the instruction below.  Answer 1  - if the question is a general question. Answer 2 - if the question is a request for code generation'
    }
  ]
  
  stream=llama32(messages,deploy)
  response=get_data(stream,deploy)
  data=""
  for str in response:
     if str.isnumeric():
      data=data+str
  #print(data)
  return data


def process_val_result(search_result,val_results):
  split_context=search_result.split("\n\n")
  for result in val_results:
      if result["relevant_DEF"] == 'False' or result["relevant_DEF"] == False :
        i=0
        for context in  split_context:
          #logger.info(f'checking {result["irrelvant_context_url"]} in {context}')
          if result["irrelvant_context_url"] in context:
            logger.info(f'{result["irrelvant_context_url"]} is invalid. Query again with Tavily')
            for query in result["other_context"]:
               logger.info(f"Trying to get extra query - {query}")
               split_context[i]=tavily(query,["https://datatracker.ietf.org/"])
          i+=1
  out=""
  for data in split_context:
     out=out + data + "\n\n"
  return out
             
        
         



def context_validation(search_result,query):
  general='''
    You are a Cisco NSO Expert that define if the context provided below is good enough to answer the Cisco NSO related question. If not, you will mention what other context is required.
    Answer the question with the following variables per context.    
    relevant_DEF - "True" if it is relevant, "False" if not
    irrelvant_context_url - url as a string that is irrelevant. If the relevant = True, this field is None.
    other_context - list of extra context that needed to answer the current question. If the relevant = True, this field is None.

    You will construct your answer as JSON format. Inside the JSON is a list per conext. 
    Do not answer anything else than the JSON String. 
    '''
  systemPrompt = f'''
    {general}

    Here are the set of contexts:

    <contexts>
    {search_result}
    </contexts>
  `;
  '''

  messages = [
    {
      "role": "user",
      "content": f'''
      Define if the context provided is relavant to answer of the question - "{query}"? 
      '''
    }
  ]
  messages.append({
                    "role": "system",
                    "content": systemPrompt,
                })

  stream=llama32(messages,config['deploy_mode'])
  response=get_data(stream,config['deploy_mode'])
  out=""
  for chunk in response:
      if "```" not in chunk and "json" not in chunk:
        out=out+chunk
  out=out.replace("```","")
  return  json.loads(out)





def handler(history,msg,config):
  history.append(
    {
      "role": "user",
      "content": msg
    }
  )
  messages = history
  #print(messages)
  
  logger.info("Getting keyword")
  (data_gitbook,data_langchain)=keyword_scrapper(msg,config['get_content_type'],config['deploy_mode'])
  logger.info("Keyword: "+str((data_gitbook,data_langchain)))

  logger.info("Searching Gitbook")
  search_result_orig = search((data_gitbook,data_langchain),q=msg)
  logger.info("Searching Gitbook Done")
  logger.info("Gitbook Content: "+search_result_orig)


  logger.info("Validating context extracted")
  val_result=context_validation(search_result_orig,msg)
  logger.info(f"Validating context extracted Done - {val_result}")

  logger.info("Act on Validating context result")
  search_result=process_val_result(search_result_orig,val_result)
  logger.info(f"Act on Validating context result Done - {search_result}")

  general='''
    You are a Cisco NSO Expert that answer Cisco NSO related question with the help of the context provided. 
    If you find the provided context is irrelevant, please disregard the provided context and use the other context that you find that are more relevant. 
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
  messages.insert(0,{
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
    messages.insert(1,{
                      "role": "tool",
                      "content": toolPrompt,
                  })
  try:
    stream=llama32(messages,config['deploy_mode'])
    logger.info(f"AI creating answer based on context - {messages}")
    stream=llama32(messages,config['deploy_mode'])
    logger.info("AI creating answer based on context Done")
  except:
    logger.error(traceback.format_exc())
    logger.error("Error detected when trying to fetch answer from AI")
    if config["get_content_type"] == "hybrid":
      logger.info("Retry with Langchain 2 top result")
      search_result_orig = query_vdb(msg,top_result=2)
    else:
      logger.info("Retry with only 1 top result")
      search_result_orig = search((data_gitbook,data_langchain),top_result=1)

    logger.info("Act on Validating context result")
    search_result=process_val_result(search_result_orig,val_result)
    logger.info(f"Act on Validating context result Done - {search_result}")

    systemPrompt = f'''
    {general}

    Here are the set of contexts:

    <contexts>
    {search_result}
    </contexts>
    `;
    '''
    messages_backup.insert(0,{
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
      hist=mem_retrive(cec_in,msg,count=2)
      logger.info(f"memory retrived - {hist}")
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
      hist=mem_retrive(cec_in,msg,count=2)
      logger.info(f"memory retrived - {hist}")
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
    #print(response)
    url_response=urllib.parse.quote_plus(response)

    finish_text=f'''
      \nAverage execution time: {end - start}
      \nI did not do well? Leave me a [Feedback](https://github.com/NSO-developer/nso_ai_assistant/issues/new?title=Inaccurate%20Answer%20from%20AI&body=**Question**%0A{url_msg}%0A%0A**Answer%20from%20AI**%0A{url_response}%0A%0A**Expected%20Answer(Optional)**%0A{comment}&labels[]=bug) on Github 
      '''
    print(finish_text)
    return response + f'\n\nAverage execution time: {end - start}'

if __name__=="__main__":
    global cache
    print("Initializing.......")
    cache=code_gen_cache()
    if config["get_content_type"] == "langchain_rag" or config["get_content_type"] == "hybrid":
      vdb_init(True)
    #api_init(config)
    logger.info("Deploy mode: "+ config['deploy_mode'])
    schedule_update()
    print("Initializing.......Done")

    cec_in=""
    while len(cec_in) == 0:
      cec_in = input('AI>\nBefore we start, please let me know who you are. What is your Username?\nUser>\n')
    print(f"Hi {cec_in}. What can I help you about Cisco NSO today?")

    while True:
      msg = input(f'\n{cec_in}>\n')
      if len(msg)==0:
         continue
      elif msg.lower() == "exit":
          exit()
      else:
          main(msg,cache,cec_in)