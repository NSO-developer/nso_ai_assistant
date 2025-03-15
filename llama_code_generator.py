from together import Together
from tavily import TavilyClient
from readability import Document

from lib.gitbook_scraper import search,gitbook_query
from lib.api_scraper import retrive_database
import requests 
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from llama_api import *

import json
import os
import logging
import time

try: 
    from BeautifulSoup import BeautifulSoup
except ImportError:
    from bs4 import BeautifulSoup


TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]


handler = logging.FileHandler("logs/llama_code_gen.log")        
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('llama_code_gen')
logger.setLevel(logging.INFO)
logger.addHandler(handler)




client = Together()
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)


def create_system(code_language,nso_service_doc_yang,config_doc,network_keyword,vendor,nso_service_api_doc):
  java_example_service="""
    @ServiceCallback(servicePoint="test-servicepoint",
        callType=ServiceCBType.CREATE)
    public Properties create(ServiceContext context,
                             NavuNode service,
                             NavuNode ncsRoot,
                             Properties opaque)
                             throws ConfException {

        Template myTemplate = new Template(context, "test-template");
        TemplateVariables myVars = new TemplateVariables();

        try {
            // set a variable to some value
            myVars.putQuoted("DUMMY", "10.0.0.1");
            // apply the template with the variable
            myTemplate.apply(service, myVars);

        } catch (Exception e) {
            throw new DpCallbackException(e.getMessage(), e);
        }
        return opaque;
    }

"""
  if code_language.lower() =="python":
    systemPrompt = f'''
    You are a coding assistant with expertise in creating the NSO {code_language} Service with NSO {code_language} API. A NSO service include the config-template in XML, {code_language} service code and the Yang Service Model.The code you created is a callback. Therefore main class is not needed. Inside {code_language} service code, there are two classes. One class named after {network_keyword} that include the code that benifit from the config-template. Another class called "Service(Application)" that is used to register the previous class that named after {network_keyword}(Service Registeration). Service Registeration is happend in the only function exist in the "Service(Application)" class - "setup(self)". Service Registeration will use two parameter - "servicename" to connect to the Yang Service Model via " ncs:servicepoint" in Yang Service Model and the class that named after {network_keyword}. 
    
    The Yang Service Model model need to include the following chapter to trigger the  {code_language} service code. 
    uses ncs:service-data;
    ncs:servicepoint "servicename";

    Implementated the code by strictly follow the documentation provided below:
      Here is how to write the Yang Service Model:
      -------
      {nso_service_doc_yang}
      ------- 
      Here is how to write the {code_language} service code:
      -------
      {nso_service_api_doc}
      ------- 
      Here is how to configure {network_keyword} on {vendor}:
      -------
      {config_doc}
      ------- 

    Your answer can benifit from the example from https://github.com/NSO-developer/nso-examples  

    The code implementated should satisfy the following requirment:
       Consider the configuration for {network_keyword} of the device model - {vendor}.
       In config-template, it need to include the configuration of {network_keyword}  for {vendor} under a devices device configuration. 
       Do not use maapi/maagic API to configure the same configuration as config-template. However, it can be used for other things.
       Your answer must include config-template in XML, NSO {code_language} service code and the Yang Service Model. 
       Device name, Interface Name and all other parameters is input from the Yang service model. 
       All leaf in the Yang service model need to be used in the config-template and NSO {code_language} service code

           
    The answer provided by you need to satisfy the following requirment:
      All required imports and variables defined. 
      Structure your answer with a description of the code solution.
      Then list the imports. And finally list the functioning code block.
      List the source you use for your answer.
  `;
  '''
  elif code_language.lower() == "java":
     systemPrompt = f'''
    You are a coding assistant with expertise in creating the NSO {code_language} Service with NSO {code_language} API. A NSO service include the config-template in XML, {code_language} service code and the Yang Service Model.The code you created is a callback. Therefore main class is not needed.
    Service Registeration will use two parameter -  "servicename" to connect to the Yang Service Model via " ncs:servicepoint" in Yang Service Model and callType which equal to ServiceCBType.CREATE. For example @ServiceCallback(servicePoint="servicename",callType=ServiceCBType.CREATE)
    
    The Yang Service Model model need to include the following chapter to trigger the  {code_language} service code. 
    uses ncs:service-data;
    ncs:servicepoint "servicename";

    Implementated the code by strictly follow the documentation provided below:
      Here is how to write the Yang Service Model:
      -------
      {nso_service_doc_yang}
      ------- 
      Here is how to write the {code_language} service code:
      -------
      {nso_service_api_doc}
      ------- 
      Here is how to configure {network_keyword} on {vendor}:
      -------
      {config_doc}
      ------- 

    Your answer can benifit from the example from https://github.com/NSO-developer/nso-examples/tree/6.4/service-management/mpls-vpn-java  

    The code implementated should satisfy the following requirment:
       Consider the configuration for {network_keyword} of the device model - {vendor}.
       In config-template, it need to include the configuration of {network_keyword}  for {vendor} under a devices device configuration. 
       Do not use maapi/maagic API to configure the same configuration as config-template. However, it can be used for other things.
       Your answer must include config-template in XML, NSO {code_language} service code and the Yang Service Model. 
       Device name, Interface Name and all other parameters is input from the Yang service model. 
       All leaf in the Yang service model need to be used in the config-template and NSO {code_language} service code

           
    The answer provided by you need to satisfy the following requirment:
      All required imports and variables defined. 
      Structure your answer with a description of the code solution.
      Then list the imports. And finally list the functioning code block.
      List the source you use for your answer.
  `;
  '''
  else:
      code_language=None
      logger.error("Error: Unsupported programming language")
      raise Exception("Wrong Programming Language")
  return systemPrompt


def service_doc(code_language):
  if code_language.lower() =="python":
    nso_service_api_doc=gitbook_query(code_language+" Packages",top_result=1)
  elif code_language.lower() == "java":
     nso_service_api_doc=gitbook_query("Service and Action Callbacks",top_result=1,url_override=[("https://cisco-tailf.gitbook.io/nso-docs/guides/nso-6.3/development/core-concepts/api-overview/java-api-overview#d5e3716","#")]) + gitbook_query("Developing our First Service Application",top_result=1,url_override=[("https://cisco-tailf.gitbook.io/nso-docs/guides/development/advanced-development/developing-packages#d5e5392","#")])
  else:
      code_language=None
      logger.error("Error: Unsupported programming language")
      raise Exception("Wrong Programming Language")
  return nso_service_api_doc



def tavily_search(vendor,network):
  result = tavily_client.search(network+" configuration of "+ vendor)
  #print(result)
  if len(result["results"]) > 0 :
    url = result["results"][0]["url"]
    r=requests.get(url)
    if r.status_code <200 and r.status_code >300:
        raise requests.exceptions.HTTPError

    doc = Document(r.content)
    summary=doc.summary()
    soup = BeautifulSoup(summary, features="html.parser")
    text = os.linesep.join([s for s in soup.get_text().splitlines() if s])
    content="Source: \n"+url+"\nConfiguration Guide: \n"+text
  else:
     logger.error("No Tavily search result found")
     content=""
  return content


def vendor_keyword_scrapper(msg,deploy="remote"):
  messages = [
    {
      "role": "user",
      "content": f'what is the network device vendor and device model of the following phrase - "{msg}"? state your answer only in a string'
    }
  ]
  
  stream=llama32(messages,deploy)
  response=get_data(stream,deploy)
  data=""
  for str in response:
     data=data+str
  return data

def network_keyword_scrapper(msg,deploy="remote"):
  messages = [
    {
      "role": "user",
      "content": f'what is the keyword regarding to network concept in the following phrase - "{msg}"? state your answer only in a string'
    }
  ]
  
  stream=llama32(messages,deploy)
  response=get_data(stream,deploy)
  data=""
  for str in response:
     data=data+str
  return data

def keyword_scrapper(msg,deploy="remote"):
  messages = [
    {
      "role": "user",
      "content": f'what is the keyword of the question without verb - "{msg}"? list the keyword only in a string'
    }
  ]
  
  stream=llama32(messages,deploy)
  response=get_data(stream,deploy)
  data=""
  for str in response:
     data=data+str
  return data

def get_programming_language(keyword):
  if "python" in keyword.lower():
      code_language="Python"
  elif "java" in keyword.lower():
      code_language="Java"
  else:
      code_language=None
      print("Error: Unsupported programming language")
      logger.error("Error: Unsupported programming language")
  return code_language

def info_prep():
  logger.info("Caching How to write Yang Model")
  #nso_service_doc_yang=search("Service Model Captures Inputs",top_result=1)
  nso_service_doc_yang=gitbook_query("Service Model Captures Inputs",top_result=1)
  logger.info("Caching How to write Yang Model Done")

  logger.info("Caching python api doc")
  nso_service_pyapi_doc=service_doc("python")
  logger.info("Caching python api doc Done")

  logger.info("Caching java api doc")
  nso_service_japi_doc=service_doc("java")
  logger.info("Caching java api doc Done")

  return(nso_service_doc_yang,nso_service_pyapi_doc,nso_service_japi_doc)


def handler(msgs,cache):
  (nso_service_doc_yang,nso_service_pyapi_doc,nso_service_japi_doc)=cache
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
  keyword=keyword_scrapper(msg,config['deploy_mode'])
  logger.info("Keyword: "+keyword)
  logger.info("Getting Programming Language")
  code_language=get_programming_language(keyword)
  if not code_language:
     return ""
  logger.info("Getting Programming Language Done")

  logger.info(f'Getting Network Keyword')
  network_keyword=network_keyword_scrapper(msg,config['deploy_mode'])
  logger.info(f'Getting Network Keyword - {network_keyword} Done ')

  logger.info(f'Getting Network Device Vendor')
  vendor=vendor_keyword_scrapper(msg,config['deploy_mode'])
  logger.info(f'Getting Network Device Vendor - {vendor} Done ')


  logger.info(f'Getting Configuration Guide')
  config_doc=tavily_search(vendor,network_keyword)
  logger.info(f'Getting Configuration Done ')

  if code_language.lower() =="python":
     nso_service_api_doc=nso_service_pyapi_doc
  elif code_language.lower() =="java":
     nso_service_api_doc=nso_service_japi_doc
  else:
     logger.error("Undefined Programming Language")
     return "Undefined Programming Language"


  systemPrompt=create_system(code_language,nso_service_doc_yang,config_doc,network_keyword,vendor,nso_service_api_doc)

  logger.info(f'System Prompt: {systemPrompt}')
  messages.append({
                    "role": "system",
                    "content": systemPrompt,
                })
  logger.info("AI creating answer based on context")
  stream=llama32(messages,config['deploy_mode'])
  logger.info("AI creating answer based on context Done")

  response=get_data(stream,config['deploy_mode'])
  out=print_data(response, deploy=config['deploy_mode'],intf=config['com_int'])
  return out



def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data


if __name__=="__main__":
    cache=info_prep()
    while True:
       msg = input('\nUser>\n')
       if msg.lower() == "exit":
          exit()
       elif len(msg.lower()) ==0:
          "noop"
       else:
        start = time.time()
        handler(msg,cache,config)
        end = time.time()
        print(f"\nAverage execution time: {end - start}")
