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
from requests_html import HTMLSession,AsyncHTMLSession
import asyncio
import nest_asyncio

nest_asyncio.apply()
os.environ['USER_AGENT'] = 'myagent'

from langchain_text_splitters import HTMLSectionSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma

from langchain_community.document_loaders import WebBaseLoader
from langchain_core.documents import Document

import sys
sys.setrecursionlimit(1500)


handler = logging.FileHandler("logs/langchain_changlog.log")        
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('langchain_changlog')
logger.setLevel(logging.INFO)
logger.addHandler(handler)


def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data

config=load_config()

url=os.environ['OLLAMA_URL']
ollama_url=f'{url}'

if config["deploy_mode"]=="remote":
    from langchain_huggingface import HuggingFaceEmbeddings
    embeddings = HuggingFaceEmbeddings(model_name=config["embedding_model"])
elif config["deploy_mode"]=="local":
    from langchain_ollama import OllamaEmbeddings
    embeddings = OllamaEmbeddings(base_url=ollama_url,model=config["embedding_model"])
else:
    logger.error("Wrong deploy_mode!")



persist_directory = 'resources/changelog_db'
init=False
if not os.path.exists(persist_directory+"/chroma.sqlite3"):
    init=True

vectordb = Chroma(
        embedding_function=embeddings,
        persist_directory=persist_directory
    )



def load_database(manager):
    if os.path.exists(persist_directory+'/database.json'):
        with open(persist_directory+'/database.json') as f:
            out = manager.dict(json.load(f))
    else:
        out = manager.dict()
    return out


def save_database(url):
    t=datetime.datetime.now()
    database[url]=t.strftime('%m/%d/%Y %H:%M:%S')
#    print(database)
    with open(persist_directory+"/database.json", "w+") as outfile: 
        json.dump(dict(database), outfile)


async def splitter(urls):
    contents={}
    pool={}
    tasks=[]
    semaphore = asyncio.Semaphore(10)

    for url in urls:
        if url not in database.keys():
            tasks.append(splitter_document(url,semaphore))

    responses = await asyncio.gather(*tasks)
    
    for(soup,ver,url) in responses:
        pool[url]=threading.Thread(target=process_docs, args=(soup,ver,url,contents))
        pool[url].start()
        
    for url,thread in pool.items():
        thread.join()
        
    return contents

def web_splitter(url):
    logger.error("HTML Splitting failed. Try web splitter")
    loader = WebBaseLoader(
    web_path = url,
    bs_kwargs=dict(
        parse_only=SoupStrainer(name=["p", "h2", "h3"])
    ),
    )
    doc=loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    texts = text_splitter.split_text(doc[0].page_content)
    out=[]
    counter=0
    for text in texts:
        document = Document(
        page_content=text,
        metadata={"Header":str(counter),"url": url}
        )
        out.append(document)
        counter+=1
    return out

def process_doc(content,ver,url,contents_url):
    meta=content.text.split("\n\n[")[1]
    [eng_nr,rest]=meta.split("/")
    type_split=rest.split(";")
    type=type_split[0].replace("]","")
    if len(type_split) > 1:
        case_nrs=type_split[1]
    else:
        case_nrs='Internal Found Issue'
    case_nrs=case_nrs.replace("]","")

    bems=re.search('BEMS[0-9]*',  case_nrs,re.IGNORECASE)
    cdets_nr = re.search('CSC[a-z,A-Z,0-9]*', case_nrs,re.IGNORECASE)
    ps_nr = re.search('PS-[0-9]*',  case_nrs,re.IGNORECASE)
    rt_nr = re.search('RT-[0-9]*',  case_nrs,re.IGNORECASE)
    out={"BEMs Number":bems,"CDETs Number":cdets_nr,"PS Number":ps_nr,"RT Number":rt_nr}
    metas={"source": url,'Header 1': "NSO Version: "+str(ver),'Header 2':"ENG Number: "+str(eng_nr),'Header 3':"Component: "+str(type)}

    for key,value in out.items():
        if value:
            metas[key]=value.group().replace(",","")

    document = Document(
    page_content=content.text,
    metadata=metas
    )

    logger.info(f"Parsed: {eng_nr} from NSO {ver}")
    contents_url[eng_nr]=document
    return contents_url


async def splitter_document(url,semaphore):
    session = AsyncHTMLSession()
    logger.info("Parsing: "+ url)
    async with semaphore:
        r = await session.get(url)
        await r.html.arender()   
    resp=r.html.html
    soup = BeautifulSoup(resp, 'html.parser')
    ver=url.split("to=")[1]
    logger.info("Parsing: "+ url + " Done")
    return (soup,ver,url)

def process_docs(soup,ver,url,contents):
    pool=[]
    eng_list=soup.find_all('div',{"class": "ticket"})
    logger.info("Splitting: "+url)
    start = time.time()
    contents_url={}
    for content in eng_list:   
        th=threading.Thread(target=process_doc, args=(content,ver,url,contents_url))
        th.start()
        pool.append(th)
    for thread in pool:
        thread.join()
    end = time.time()
    contents[url]=contents_url
    logger.info("Splitting: "+url+" Done. Expect Length: "+str(len(eng_list))+". Actual Length: "+str(len(contents_url)) +" ,Current Total Length: "+str(len(contents)) + f" ({end - start})")
    save_database(url)

    return contents

def add_vector_databases(splitted_docs):
    for url,doc in splitted_docs.items():
        (ids,splitted_doc)=cleaning_docs(doc)
        add_vector_database(ids,splitted_doc)

def add_vector_database(ids,splitted_doc):
    #(ids,splitted_doc)=cleaning_docs(splitted_doc)
    if len(splitted_doc) > 0:
        vectordb.add_documents(documents=splitted_doc, ids=ids)
        logger.info("Adding: "+str(len(splitted_doc))+" ENGs to Chroma Vector Database - Done. Hash: "+ str(ids))
    else:
        logger.error("Adding: "+str(len(splitted_doc))+" ENGs to Chroma Vector Database - ERROR(doc is empty). Hash: "+ str(ids))
    return ids


def cleaning_docs(splitted_docs):
    lst_splitted_doc=[]
    ids=[]
    for key,doc in splitted_docs.items():
        logger.info(f"Cleaning {doc} for ENG {key}")
        if not doc:
            logger.error("Doc is empty. Doc: "+str(doc))
        elif not doc.metadata:
            logger.error("Doc metadata is empty. Doc: "+str(doc)+" / metadata: "+str(doc.metadata))
        else:
            if len(doc.metadata)>0:
                sha = hashlib.sha256()
                sha.update(str(doc.metadata).encode())
                id=sha.hexdigest()
                if id not in ids:
                    ids.append(str(id))
                    lst_splitted_doc.append(doc)
                    logger.info("Generating id: "+str(id)+" / metadata: "+str(doc.metadata))
    return (ids,lst_splitted_doc)


def query_vdb(query,nr,mode="similarity",top_result=2):
    logger.info("Querying Vector DB in "+ mode+": "+ query)
    datas={}
    out=""
    (nr_database,check)=nr
    if mode == "similarity":
        logger.info("similarity_search")
        if check:
            results = vectordb.similarity_search(
            query,
            k=top_result,
            filter=nr_database
            )
        else:
            results = vectordb.similarity_search(
            query,
            k=top_result
            )
    else:
        logger.info("max_marginal_relevance_search")
        results=vectordb.max_marginal_relevance_search(query,k=top_result)
    #print(str(results))
    for res in results:
        logger.info("Result obtained from vdb: "+str(res))
        #logger.info("Metadata: "+str(res.metadata))

        index=""
        source=""
        for title,data in res.metadata.items():
            source=title+": "+data+", "+source
        index=res.metadata["Header 2"]
        datas[index]="url: "+str(source)+"\nresult: "+res.page_content
        logger.info("Result obtained from vdb - Loaded: "+str(res))

        #print("source: "+res.metadata['url']+"\nresult: "+res.page_content)
    for data in datas.values():
        out=out+data+"\n\n"
    logger.info("Querying Vector DB in "+ mode+": "+ query+" Done")
    return out


#https://cisco-tailf.gitbook.io/nso-docs/guides/nso-6.3/operation-and-usage/operations/nso-device-manager#user_guide.devicemanager.initialize-device

async def add_vdb_byurls(urls):
    #documents=loader(urls)
    logger.info("Spliting Document Start")
    splitted_doc=await splitter(urls)
    logger.info(f"Spliting Document Start - Done ENG:{splitted_doc}")

    logger.info("Adding Spliited Doc to the VDB")
    add_vector_databases(splitted_doc)


def vdb_init(check):
    manager = Manager()
    global database
    database=load_database(manager)
#    url_nav=["https://cisco-tailf.gitbook.io/nso-docs/guides"]
    logger.info("Loading NSO Changelog Explorer")
    url_nav="https://developer.cisco.com/docs/nso/changelog-explorer/"
    logger.info("Extracting all Changelog Exploer URL from Various NSO version")
    scraped_urls=get_all_urls(url_nav)
    scraped_urls=list(set(scraped_urls))
    if check:
        asyncio.run(add_vdb_byurls(scraped_urls))

        

#vdb_init(init)

def get_all_urls(url_nav):
    urls = []
    get_all_url(url_nav,urls)
    return urls

def get_all_url(url,urls):
    session = HTMLSession()
    r = session.get(url)
    r.html.render()
    ver_html=r.html.find('option')[:-58]
    len_ver=int(len(ver_html)/2*-1)
    old_ver=None
    for ver in ver_html[:len_ver]:
        if old_ver:
            url=f"https://developer.cisco.com/docs/nso/changelog-explorer/?from={old_ver.text}&to={ver.text}"
            urls.append(url)
        old_ver=ver
    #url=f"https://developer.cisco.com/docs/nso/changelog-explorer/?from={}&to={}"
    return urls


def update_database():
    logger.info("Updating Database")
    vdb_init(True)

def check_schedule(interval):
    logger.info("Watchdog up. Checking every "+str(interval)+" seconds.")
    while True:
        schedule.run_pending()
        time.sleep(interval)
    
def schedule_update():
    logger.info("Set watchdog to updating database at - "+str(config["database_check_time"]))
    schedule.every().day.at(config["database_check_time"]).do(update_database)
    t1=threading.Thread(target=check_schedule, args=(1,))
    t1.start()


    


if __name__=="__main__":
    asyncio.run(add_vdb_byurls("https://developer.cisco.com/docs/nso/changelog-explorer/?from=5.5.6&to=5.5.7"))
    #vdb_init(True)
    #vdb_init(True)
    #query_vdb("which NSO version SSHJ version 0.39.0 has been introduced?",mode="similarity",top_result=2)
    #query="which NSO version does CDB Persistent introduced?"
    #query="Which NSO version does ENG-25888 introduced?"
    #data=query_vdb(query,mode="similarity",top_result=1)
    #print("===========Return Data=====================")
    #print(data)
    #print("================================")

    
