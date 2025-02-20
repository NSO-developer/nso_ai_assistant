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

handler = logging.FileHandler("logs/langchain_gitbook.log")        
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

persist_directory = 'resources/vectordb'
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


def splitter(urls):
    contents={}
    pool={}
    for url in urls:
        url=re.sub('/nso-6.[1-9]*/', '/', url)

        current=datetime.datetime.now()
        if url in database.keys():
            database_obj=datetime.datetime.strptime(database[url], '%m/%d/%Y %H:%M:%S')
            diff=(current-database_obj).days
        else:
            diff=config["doc_keepalive"]+1
        if diff >config["doc_keepalive"]:
            pool[url]=threading.Thread(target=splitter_document, args=(url,contents))

    for thread in pool.values():
        thread.start()
    for thread in pool.values():
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
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
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

def splitter_document(url,contents):      
    logger.info("Splitting: "+url)
    headers_to_split_on = [
        ("h1", "Header 1"),
        ("h2", "Header 2"),
        ("h3", "Header 3"),
    ]
    #print(document)
    html_splitter = HTMLHeaderTextSplitter(headers_to_split_on)
    #html_header_splits = html_splitter.split_text(document)
    try:
        html_header_splits = html_splitter.split_text_from_url(url)
    except:
        html_header_splits=web_splitter(url)

    contents[url]=html_header_splits
    logger.info("Splitting: "+url+" Done. Length: "+str(len(html_header_splits)))
    save_database(url)
    #database[url]=datetime.datetime.now()
    return contents

def add_vector_databases(splitted_docs):
    for key,content in splitted_docs.items():
        for docs in content:
            #logger.info("before docs: "+str(docs))
            if len(docs.metadata) > 0:
                docs.metadata['url']=key
            #logger.info("after docs: "+str(docs))
        add_vector_database(key,content)

def add_vector_database(key,splitted_doc):
    #print(splitted_doc)
    #logger.info("before splitted_doc: "+str(splitted_doc))
    (ids,splitted_doc)=cleaning_docs(splitted_doc)
    
    logger.info("Adding: "+key+" to Chroma Vector Database")
    #uuids = [str(uuid4()) for _ in range(len(splitted_doc))]
    vectordb.add_documents(documents=splitted_doc, ids=ids)
    logger.info("Adding: "+key+" to Chroma Vector Database - Done. Hash: "+ str(ids))
    return ids


def cleaning_docs(splitted_doc):
    lst_splitted_doc=[]
    ids=[]
    for doc in splitted_doc:
        if len(doc.metadata)>0:
            sha = hashlib.sha256()
            sha.update(str(doc.metadata).encode())
            id=sha.hexdigest()
            if id not in ids:
                ids.append(str(id))
                lst_splitted_doc.append(doc)
                logger.info("Generating id: "+str(id)+" / metadata: "+str(doc.metadata))
                logger.info("doc: "+str(doc))
    return (ids,lst_splitted_doc)

def query_vdb(query,mode="similarity",top_result=2):
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
        source=title_str+", "+url_str
        datas[index]="source: "+str(source)+"\nresult: "+res.page_content
        #print("source: "+res.metadata['url']+"\nresult: "+res.page_content)
    for data in datas.values():
        out=out+data+"\n\n"
    logger.info("Querying Vector DB in "+ mode+": "+ query+" Done")
    return out


#https://cisco-tailf.gitbook.io/nso-docs/guides/nso-6.3/operation-and-usage/operations/nso-device-manager#user_guide.devicemanager.initialize-device

def add_vdb_byurls(urls):
    #documents=loader(urls)
    splitted_doc=splitter(urls)
    #print(splitted_doc.keys())
    add_vector_databases(splitted_doc)



def langchain_query(urls,query,top_result=2):
    if len(urls) > top_result:
        urls=urls[:top_result]
    
    logger.info("Will Process the following urls: "+str(urls))
    add_vdb_byurls(urls)
    datas=query_vdb(query,top_result=top_result)
    out=""
    for data in datas.values():
        out=out+data+"\n\n"
    logger.info("Knowledge Base Status: "+str(database))
    return out

    #print(f"fetched {len(content)} documents.")
    #rint(content[0].page_content)


def vdb_init(check):
    manager = Manager()
    global database
    database=load_database(manager)
#    url_nav=["https://cisco-tailf.gitbook.io/nso-docs/guides"]
    url_nav=["https://cisco-tailf.gitbook.io/nso-docs/guides","https://cisco-tailf.gitbook.io/nso-docs/developers"]
    scraped_urls=get_all_urls(url_nav)
    scraped_urls=list(set(scraped_urls))
    #for url in scraped_urls:
    #    print(url)
    if check:
        add_vdb_byurls(scraped_urls)

#vdb_init(init)

def get_all_urls(url_nav):
    urls = []
    pool = {}
    for url in url_nav:
        pool[url]=threading.Thread(target=get_all_url, args=(url,urls))
    for thread in pool.values():
        thread.start()
    for thread in pool.values():
        thread.join()
    return urls

def get_all_url(url,urls):
    url_lst=url.split("/")
    search_key=url_lst[-2]+"/"+url_lst[-1]
    reqs = requests.get(url)
    soup = BeautifulSoup(reqs.text, 'html.parser')
    for link in soup.find_all('a'):
        link=link.get('href')
        if "http" not in link and search_key in link and "?" not in link and "#" not in link and "whats-new" not in link and "errata" not in link and link != "/"+search_key and "get-started" not in link:
            urls.append("https://cisco-tailf.gitbook.io"+link)
            #print("https://cisco-tailf.gitbook.io"+link)
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
    vdb_init(True)

    #urls=['https://cisco-tailf.gitbook.io/nso-docs/guides/resources/index/section3','https://cisco-tailf.gitbook.io/nso-docs/guides/nso-6.1/resources/index/section5','https://cisco-tailf.gitbook.io/nso-docs/guides/resources/index/section5']
    query="worker query timeout"
    data=query_vdb(query,top_result=2)
    #data=langchain_query(urls,query)
    print("===========Return Data=====================")
    print(data)
    print("================================")

    
