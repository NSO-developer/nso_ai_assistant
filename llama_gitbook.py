from lib.gitbook_scraper import search
import logging


from llama_api import *
import json
from webex_api import send
from lib.langchain_loader import *
#from lib.summarizer import summarize_get

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
import traceback


handler = logging.FileHandler("logs/llama_gitbook.log")        
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('llama_gitbook')
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
        "content": f'Can you rephrase and expend the question - "{msg}"? Your answer should only include the rephrased question in a string'
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


def generate_sum_context(context,final_result,sum_url=[]):
    url_re=re.search(r"url: http.*, ", context,re.IGNORECASE)
    if not url_re:
      #logger.info("Mismatch context - url: http.*, : "+ str(context))
      url_re=re.search(r"url: http.*\n", context,re.IGNORECASE)
    if not url_re:
      #logger.info("Mismatch context - url: http.*\n"+ str(context))
      url_re=re.search(r"source: http.*\n", context,re.IGNORECASE)
      if url_re:
        url=url_re.group().split("source:")[1].strip()
      else:
         url=None
    else:
      url=url_re.group().split("url:")[1].strip()
    if url:
      if "," in url:
        url=url.replace(",","")
      if url not in sum_url:
        logger.info("URL obtain from Context for Summary: "+url)
        final_result.append(generate_summarize(url))
        sum_url.append(url)
      else:
        logger.info("Summarize has already been provided for URL: "+url)
    return final_result



def process_val_result(search_result,val_results):
  q_set=[]
  split_context=search_result.split("\n\nsource:")
  final_result=[]
  false_switch=False
  i=0
  for result in val_results:
      if (result["relevant_DEF"] == 'False' or result["relevant_DEF"] == False) and "section5#ncs.conf" not in result["irrelvant_context_url"] :
        for context in  split_context:
          #logger.info(f'checking {result["irrelvant_context_url"]} in {context}')
          if result["irrelvant_context_url"] in context:
            logger.info(f'{result["irrelvant_context_url"]} is invalid. Query again with max_marginal_relevance inside RAG')
            for query in result["other_context"]:
               if query.strip().lower() not in q_set:
                  logger.info(f"Trying to get extra query - {query}")
                  q_set.append(query.strip().lower())
                  final_result.append(query_vdb(query,mode="max_marginal_relevance",top_result=1))
                  false_switch=True
        #final_result.append(summarize_get(result["irrelvant_context_url"]))
      else:
          if "source:" not in split_context[i]:
             final_result.append("source: "+split_context[i])
          else:   
            final_result.append(split_context[i])
      i+=1
      
  if config["get_content_type"] =="langchain_rag" and config["summarizer"]["enable"]:
     false_switch=True

  triggered=False
  i=0
  if false_switch and config["summarizer"]["enable"]:
    sum_url=[]
    for result in val_results:
      if "source: " not in split_context[i]:
          data="source: "+split_context[i]
      else:
          data=split_context[i]
      if config["get_content_type"] =="langchain_rag":
        logger.info("langchain_rag enhanced mode - summary support")
        final_result=generate_sum_context(data,final_result,sum_url)
        triggered=True
      elif (result["relevant_DEF"] == 'True' or result["relevant_DEF"] == True):
          logger.info(split_context)
          logger.info("max_marginal_relevance trigger substitution. Creating Summary from corrected source as support context")
          final_result=generate_sum_context(data,final_result,sum_url)
          triggered=True
      i+=1

    if not triggered:
        i=0
        for data in final_result:
            logger.info("All False Result. Creating Summary from max_marginal_relevance substitution as support context")
            if "source: " not in split_context[i]:
               con="source: "+split_context[i]
            else:
              con=split_context[i]
            final_result=generate_sum_context(con,final_result,sum_url)
        i+=1

  #final_result.append(tavily(query,["https://datatracker.ietf.org/"]))
  out=""
  for data in final_result:
     logger.info(data)
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





def handler(msgs):
  messages=[]
  #[HumanMessage(content='What is CDB', additional_kwargs={}, response_metadata={}, id='430b76f7-8a0e-4dfa-9670-8c8dc39b1a1e')]
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


  logger.info("Getting keyword")
  (data_gitbook,data_langchain)=keyword_scrapper(msg,config['get_content_type'],config['deploy_mode'])
  messages[-1]["content"]=data_langchain
  logger.info("Keyword: "+str((data_gitbook,data_langchain)))

  logger.info("Searching Gitbook")
  search_result_orig = search((data_gitbook,data_langchain))
  logger.info("Searching Gitbook Done")
  logger.info("Gitbook Content: "+search_result_orig)

  general='''
      You are a Cisco NSO Expert that answer Cisco NSO related question with the help of the context provided. 
      If you find the provided context is irrelevant, please disregard the irrelevant context and use the other context that you find that are more relevant. 
      If there are code or command example in the context that can help you answering the question, please include them into your answer. At the same time, consider all scenrio in the context.
      In the end of your answer, mention whatever source that you used to construct your answer. 
      Construct your answer in Markdown format.
      '''
  messages_backup=messages.copy()

  try:
    logger.info("Validating context extracted")
    val_result=context_validation(search_result_orig,msg)
    logger.info(f"Validating context extracted Done - {val_result}")

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
    messages.insert(0,{
                      "role": "system",
                      "content": systemPrompt,
                  })
    #print(messages)
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

    logger.info(f"AI creating answer based on context - {messages}")
    stream=llama32(messages,config['deploy_mode'])
    logger.info("AI creating answer based on context Done")
  except:
    logger.error(traceback.format_exc())
    logger.error("Error detected when trying to fetch answer from AI")
    if config["get_content_type"] == "hybrid":
      logger.info("Retry with Langchain 2 top result")
      search_result_orig = query_vdb(data_langchain,top_result=2)
    else:
      logger.info("Retry with only 1 top result")
      search_result_orig = search((data_gitbook,data_langchain),top_result=1)

    logger.info(f"Validating context extracted - {search_result_orig}")
    val_result=context_validation(search_result_orig,msg)
    logger.info(f"Validating context extracted Done - {val_result}")

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
  
  #print("response2:" + str(response))
  #print("out:" + out)

  return response

def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data