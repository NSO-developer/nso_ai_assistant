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
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
import uuid
import traceback


handler = logging.FileHandler("logs/llama.log")        
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('llama')
logger.setLevel(logging.INFO)
logger.addHandler(handler)


config=load_config()

cache=None


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
  q_set=[]
  split_context=search_result.split("\n\n")
  final_result=[]
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
      else:
          final_result.append(split_context[i])
      i+=1
  #final_result.append(tavily(query,["https://datatracker.ietf.org/"]))
  out=""
  for data in final_result:
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
  out=print_data(response, deploy=config['deploy_mode'],intf=config['com_int'])
  #print("response2:" + str(response))
  #print("out:" + out)

  return out

def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data



def query_callback(state: MessagesState):
    response=handler(state["messages"])
    out=AIMessage(content=response)
    return {"messages":out}


def query_callback_code(state: MessagesState):
    response=code_gen_handler(state["messages"],cache)
    out=AIMessage(content=response)
    return {"messages":out}

memory = MemorySaver()

workflow = StateGraph(state_schema=MessagesState)
workflow.add_node("model", query_callback)
workflow.add_edge(START, "model")
app = workflow.compile(checkpointer=memory)


workflow_code = StateGraph(state_schema=MessagesState)
workflow_code.add_node("model", query_callback_code)
workflow_code.add_edge(START, "model")
app_code = workflow_code.compile(checkpointer=memory)

def main(msg,cache_in,cec_in="",name=""):
    cache=cache_in
    purpose=int(define_purpose(msg,config['deploy_mode']))
    if purpose == 1 or "how"  in msg.lower() or "what"  in msg.lower() or "when"  in msg.lower() or "why"  in msg.lower():
      if config["com_int"] == "cli":
         print("AI> \nSeems like you want some answer on general question. Let me think..... This might takes around 45 sec to 1 min.")           
      elif config["com_int"] == "webex":
        send(f"Hi {name}. Let me think.....This might takes around 45 sec to 1 min.",cec=cec_in)
      start = time.time()

      messages =  [HumanMessage(content=msg)]
      response=app.invoke(
          {"messages": messages},
          config={"configurable": {"thread_id": cec_in}},

      )

      #print("response1:" + response)
      end = time.time()
    elif purpose == 2 and "how" not in msg.lower() and "what" not in msg.lower() and "when" not in msg.lower() and "why" not in msg.lower():
      if config["com_int"] == "cli":
         print("AI> \nSeems like you want to generate some code. Let me think.....")
      elif config["com_int"] == "webex":
         send(f"Hi {name}. Let me try to craft your code.....This might takes around 45 sec to 1 min.", cec=cec_in)

      start = time.time()

      messages =  [HumanMessage(content=msg)]
      response=app_code.invoke(
          {"messages": messages},
          config={"configurable": {"thread_id": cec_in}},

      )
      end = time.time()
    else:
      response=""
      send("ERROR: Undefined Purpose", cec=cec_in)
      logger.error("Undefined Purpose")

    comment="What%20do%20you%20want%20to%20see%20and%20how%20should%20it%20be%20improved."
    #print("msg:" + msg)
    #print("response:" + str(response))
    url_msg=urllib.parse.quote_plus(msg)
    result=response['messages'][-1].content

    url_response=urllib.parse.quote_plus(str(result))


    finish_text=f'''
      \nAverage execution time: {end - start}
      \nI did not do well? Leave me a [Feedback](https://github.com/NSO-developer/nso_ai_assistant/issues/new?title=Inaccurate%20Answer%20from%20AI&body=**Question**%0A{url_msg}%0A%0A**Answer%20from%20AI**%0A{url_response}%0A%0A**Expected%20Answer(Optional)**%0A{comment}&labels[]=bug) on Github 
      '''
    print(finish_text)
    return result + f'\n\nAverage execution time: {end - start}'

if __name__=="__main__":
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