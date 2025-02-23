import os
import logging
import requests
import threading
from uuid import uuid4
import hashlib
import json
import datetime;
try: 
    from BeautifulSoup import SoupStrainer
except ImportError:
    from bs4 import SoupStrainer
import re
from bs4 import BeautifulSoup 
from multiprocessing import Manager
import time
import schedule

os.environ['USER_AGENT'] = 'myagent'

from langchain_text_splitters import HTMLHeaderTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma

from langchain_community.document_loaders import WebBaseLoader
from langchain_core.documents import Document

handler = logging.FileHandler("logs/langchain_mem.log")        
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('langchain_gitbook')
logger.setLevel(logging.INFO)
logger.addHandler(handler)


def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data

config=load_config()

if config["deploy_mode"]=="remote":
    from langchain_huggingface import HuggingFaceEmbeddings
    embeddings = HuggingFaceEmbeddings(model_name=config["embedding_model"])
elif config["deploy_mode"]=="local":
    from langchain_ollama import OllamaEmbeddings
    embeddings = OllamaEmbeddings(model=config["embedding_model"])
else:
    logger.error("Wrong deploy_mode!")

persist_directory = 'resources/chat_mem'
init=False
if not os.path.exists(persist_directory+"/chroma.sqlite3"):
    init=True


def mem_create(cec):
    persist_directory = f'resources/chat_mem/{cec}'
    if not os.path.exists(persist_directory):
        os.makedirs(persist_directory)
    vectordb = Chroma(
            embedding_function=embeddings,
            persist_directory=persist_directory
        )
    return vectordb


def mem_retrive(cec_in,query,count=2):
    vectordb=mem_create(cec_in)
    data=query_vdb(query,vectordb,mode="similarity",top_result=count)
    #print(data)
    output=[]
    for data_l in data.split("##\n\n\n##"):
        data_l_lst=data_l.split("//**//")
        if len(data_l_lst) >=2:
            #print(data_l_lst)
            human=data_l_lst[0]
            ai=data_l_lst[1]
            output.append({"role": "user", "content":human})
            output.append({"role": "assistant", "content":ai})
    logger.info("Obtain the following information: "+str(output))
    return output

def mem_add(cec_in,query,answer):
    vectordb=mem_create(cec_in)
    add_vector_databases(query,answer,vectordb)
    logger.info("Save the following information for "+cec_in+": "+str((query,answer)))


def add_vector_databases(query,answer,vectordb_choice):
        add_vector_database(query,answer,vectordb_choice)

def add_vector_database(query,answer,vectordb_choice):
    (ids,splitted_doc)=cleaning_docs(query,answer)

    vectordb_choice.add_documents(documents=splitted_doc, ids=ids)
    return ids


def cleaning_docs(query,answer):
    lst_splitted_doc=[]
    ids=[]
    sha = hashlib.sha256()
    sha.update(str(query.lower().strip()).encode())
    id=sha.hexdigest()
    ids.append(str(id))
    splitted_doc = Document(
    page_content=f"{query}//**//{answer}##\n\n\n##",
    )
    lst_splitted_doc.append(splitted_doc)
    logger.info("Generating id: "+str(id))
    logger.info("doc: "+str(splitted_doc))
    return (ids,lst_splitted_doc)

def query_vdb(query,vectordb,mode="similarity",top_result=2):
    logger.info("Querying Vector DB in "+ mode+": "+ query)
    datas={}
    out=""
    if mode == "similarity":
        logger.info("similarity_search")
        results = vectordb.similarity_search(
        query,
        k=top_result
        )
    else:
        logger.info("max_marginal_relevance_search")
        results=vectordb.max_marginal_relevance_search(query,k=top_result)
    #print(str(results))
    for res in results:
        index=""
        for key,title in res.metadata.items():
            index=index+title+"-"
        index=index[:-1]
        #print(index)
        title_str="title: "
        url_str="url: "
        for title,data in res.metadata.items():
            if "Header" in title:
                title_str=title_str+data+" - "
            elif "url" in title:
                url_str=url_str+data
        #print(title_str)
        title_str= title_str[:-3]
        datas[index]=res.page_content
        #print("source: "+res.metadata['url']+"\nresult: "+res.page_content)
    for data in datas.values():
        out=out+data+"\n\n"
    logger.info("Querying Vector DB in "+ mode+": "+ query+" Done")
    return out




if __name__=="__main__":
    query="What is CDB?"
    mem_add("leeli4","What is CDB?","CDB is a database")
    print(mem_retrive("leeli4",query,count=2))

    
