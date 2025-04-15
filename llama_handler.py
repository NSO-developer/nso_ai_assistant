from lib.gitbook_scraper import search
import logging
import time


from llama_code_generator import handler as code_gen_handler
from llama_changelog import handler as changelog_handler,changelog_init
from llama_gitbook import handler as gitbook_handler
from llama_code_generator import info_prep as code_gen_cache
from llama_api import *
import json
from webex_api import send
import urllib.parse
from lib.langchain_loader import *
from lib.loader import *


from langgraph.graph import START, MessagesState, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage
import traceback


handler = logging.FileHandler("logs/llama.log")        
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('llama')
logger.setLevel(logging.INFO)
logger.addHandler(handler)


config=load_config()

global cache
cache=None
print("Initializing.......")
logger.info("Initializing.......")
cache=code_gen_cache()


def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data



def query_callback(state: MessagesState):
    if config["com_int"] == "cli":
      loader = Loader("Seems like you want some answer on general question. Let me think..... This might takes around 45 sec to 1 min.").start()
      #print("AI> \nSeems like you want some answer on general question. Let me think..... This might takes around 45 sec to 1 min.")           
    response=gitbook_handler(state["messages"])
    if config["com_int"] == "cli":
      loader.stop()
    data=print_data(response, deploy=config['deploy_mode'],intf=config['com_int'])
    out=AIMessage(content=data)
    return {"messages":out}


def query_callback_code(state: MessagesState):
    if config["com_int"] == "cli":
      loader = Loader("AI> Seems like you want to generate some code. Let me think..... This might takes around 45 sec to 1 min.").start()
          #print("AI> \nSeems like you want to generate some code. Let me think.....")
    response=code_gen_handler(state["messages"],cache)
    if config["com_int"] == "cli":
      loader.stop()
    data=print_data(response, deploy=config['deploy_mode'],intf=config['com_int'])
    out=AIMessage(content=data)
    return {"messages":out}

def query_callback_changlog(state: MessagesState):
    if config["com_int"] == "cli":
      loader = Loader("AI> Seems like you want me to explore the changenote. Let me think..... This might takes around 1 min to 2 min.").start()
      #print("AI> \nSeems like you want me to explore the changenote. Let me think.....")
    response=changelog_handler(state["messages"])
    if config["com_int"] == "cli":
      loader.stop()
    data=print_data(response, deploy=config['deploy_mode'],intf=config['com_int'])
    out=AIMessage(content=data)
    return {"messages":out}

def check_changelog(msg):
  datas=[re.search('ENG-[0-9]*', msg,re.IGNORECASE),re.search('BEMS[0-9]*',  msg,re.IGNORECASE), re.search('CSC[a-z,A-Z,0-9]*', msg,re.IGNORECASE),re.search('PS-[0-9]*',  msg,re.IGNORECASE),re.search('RT-[0-9]*',  msg,re.IGNORECASE)]
  for item in datas:
     if item:
        return True
  return False

memory = MemorySaver()

workflow = StateGraph(state_schema=MessagesState)
workflow.add_node("model", query_callback)
workflow.add_edge(START, "model")
app = workflow.compile(checkpointer=memory)


workflow_code = StateGraph(state_schema=MessagesState)
workflow_code.add_node("model", query_callback_code)
workflow_code.add_edge(START, "model")
app_code = workflow_code.compile(checkpointer=memory)

workflow_changelog = StateGraph(state_schema=MessagesState)
workflow_changelog.add_node("model", query_callback_changlog)
workflow_changelog.add_edge(START, "model")
app_changelog = workflow_changelog.compile(checkpointer=memory)

def define_purpose(msg,deploy="remote"):
  if check_changelog(msg):
     data=3
  else:
    messages = [
      {
        "role": "user",
        "content": f'Define if this question is a general question , request a code generation or regarding to specific feature introduction or bug fix(release note)  - {msg}. Your answer should not provide any Explanation, provide only absolute integer answer by following the instruction below.  Answer 1  - if the question is a general question. Answer 2 - if the question is a request for code generation. Answer 3 - if the question is regarding to specific feature introduction or bug fix(release note)'
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

def main(msg,cec_in="",name=""):
    purpose=int(define_purpose(msg,config['deploy_mode']))
    if purpose ==3 and "how "  not in msg.lower() and "why "  not in msg.lower():
       bypass =True
    else:
       bypass = False

       
    if  "what "  in msg.lower() or ("when " in msg.lower() and "_when" not in msg.lower() ) or bypass:
      if purpose == 3:
        logger.info("define as changelog related")
        if config["com_int"] == "webex":
          send(f"Hi {name}. Let me try to go through the changenote.....This might takes around 1 to 2 min.", cec=cec_in)
        start = time.time()
        messages =  [HumanMessage(content=msg)]
        response=app_changelog.invoke(
            {"messages": messages},
            config={"configurable": {"thread_id": cec_in}},

        )
        end = time.time()
      else:
        if config["com_int"] == "webex":
            send(f"Hi {name}. Let me think.....This might takes around 45 sec to 1 min.",cec=cec_in)    
        logger.info("define as general question")
        start = time.time()
        messages =  [HumanMessage(content=msg)]
        response=app.invoke(
            {"messages": messages},
            config={"configurable": {"thread_id": cec_in}},

        )
        end = time.time()
    else:
      if purpose == 2:
        logger.info("define as code generation related")
        if config["com_int"] == "webex":
          send(f"Hi {name}. Let me try to craft your code.....This might takes around 45 sec to 1 min.", cec=cec_in)
        start = time.time()
        messages =  [HumanMessage(content=msg)]
        response=app_code.invoke(
            {"messages": messages},
            config={"configurable": {"thread_id": cec_in}},

        )
        end = time.time()
      else:
        if config["com_int"] == "webex":
            send(f"Hi {name}. I am having a hard time to define the purpose of your question. I assume this is something to that can be found in the Gitbook. Let me check and get back to you..... This might takes around 45 sec to 1 min.",cec=cec_in)    
        logger.error("Undefined Purpose - "+str(purpose))
        logger.info("LAST RESOLUTION!!! define as general question")
        start = time.time()
        messages =  [HumanMessage(content=msg)]
        response=app.invoke(
            {"messages": messages},
            config={"configurable": {"thread_id": cec_in}},

        )
        end = time.time()
        

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
    if config["get_content_type"] == "langchain_rag" or config["get_content_type"] == "hybrid":
      logger.info("Initializing Gitbook VDB")
      vdb_init(True)
      logger.info("Initializing Gitbook VDB......Done")
      logger.info("Initializing Changelog Explorer VDB")
      changelog_init()
      logger.info("Initializing Changelog Explorer VDB......Done")

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
          os._exit(os.EX_OK)
      else:
          try:
            main(msg,cache,cec_in)
          except Exception:
             print(traceback.format_exc())
             os._exit(os.EX_TEMPFAIL)

