import os
import logging
import requests
import threading
from time import sleep
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
from concurrent.futures import ThreadPoolExecutor

from .langchain_loader_resource import query_vdb as query_vdb_resource
from .langchain_loader_resource import resource_init as resource_init
from .langchain_loader_resource import get_db as get_db_resource

from .summarizer import summarize_add,summarize_get


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
    #pool={}
    with ThreadPoolExecutor(config['init_thread_limit']) as executor:
        for url in urls:
            #url=re.sub('/nso-6.[1-9]*/', '/', url)
            nso_ver = re.search('/nso-6.[1-9]*/', url)
            if nso_ver:
                nso_ver=nso_ver.group(0)
                nso_ver=nso_ver.replace("/","").replace("nso-","")
            else:
                nso_ver="latest"
            logger.info("catagorize doc for "+str(url)+" - "+str(nso_ver))

            current=datetime.datetime.now()
            if url in database.keys():
                database_obj=datetime.datetime.strptime(database[url], '%m/%d/%Y %H:%M:%S')
                diff=(current-database_obj).days
                logger.info("Url: "+str(url)+" Last day to update: "+str(diff)+" ago.")
                if diff >int(config["doc_keepalive"]):
                    executor.submit(splitter_document, url,contents,nso_ver)
            else:
                executor.submit(splitter_document, url,contents,nso_ver)
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

def splitter_document(url,contents,nso_ver):      
    logger.info("Splitting: "+url)
    headers_to_split_on = [
        ("h1", "Header 1"),
        ("h2", "Header 2"),
        ("h3", "Header 3")
    ]
    #print(document)
    html_splitter = HTMLHeaderTextSplitter(headers_to_split_on)
    #html_header_splits = html_splitter.split_text(document)
    try:
        html_header_splits = html_splitter.split_text_from_url(url)
    except:
        html_header_splits=web_splitter(url)
    #print(html_header_splits)
    header1=None
    hearder_obj=None
    header2_checker=False
    for data in html_header_splits:
        if len(data.metadata) > 0:
            if 'Header 1' in data.metadata.keys() and 'Header 2' not in data.metadata.keys() :
                #print("header 1 only:"+str(data)+" url: "+str(url))
                hearder_obj=data
                header1=data.metadata['Header 1']
                html_header_splits.remove(data)
            elif 'Header 2' in data.metadata.keys() or  'Header' in data.metadata.keys():
                header2_checker=True
            else:
                data.metadata['Header 1']=header1
                #print("header 1 and others:"+str(data))
                #print(data)
            data.metadata['url']=url
            data.metadata['NSO Version']=nso_ver
    if not header2_checker: 
        html_header_splits.append(hearder_obj)
    #print(html_header_splits)
    contents[url]=html_header_splits
    logger.info("Splitting: "+url+" Done. Length: "+str(len(html_header_splits)))
    #database[url]=datetime.datetime.now()
    return contents

def add_vector_databases(splitted_docs):
    for key,content in splitted_docs.items():
        add_vector_database(key,content)

def add_vector_database(key,splitted_doc):
    (ids,splitted_doc)=cleaning_docs(splitted_doc)
    logger.info("Adding: "+key+" to Chroma Vector Database")
    if len(splitted_doc) > 0:
        if config["summarizer"]["enable"] and config["summarizer"]["init_on_boot"]:
            logger.info("Summarizing: "+key+" to SQL Database")
            summarize_add(key,splitted_doc)
        vectordb.add_documents(documents=splitted_doc, ids=ids)
        logger.info("Adding: "+key+" to Chroma Vector Database - Done. Hash: "+ str(ids))
        save_database(key)
    else:
        logger.error("Adding: "+key+" to Chroma Vector Database - ERROR(doc is empty). Hash: "+ str(ids))
    return ids


def cleaning_docs(splitted_doc):
    lst_splitted_doc=[]
    ids=[]
    for doc in splitted_doc:
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
                    #logger.info("doc: "+str(doc))

    return (ids,lst_splitted_doc)



def get_db(url):
    meta={}
    resource_switch=False
    if "resource-manager" in url.lower() :
        logger.info("Resource Manager Filter Activated")
        meta["code_name"]="resource-manager"
        resource_switch=True
    elif  "observability-exporter" in  url.lower():
        logger.info("Observability Exporter Filter Activated")
        meta["code_name"]="observability-exporter"
        resource_switch=True
    elif "phased-provisioning" in  url.lower():
        logger.info("Phased Provisioning Filter Activated")
        meta["code_name"]="phased-provisioning"
        resource_switch=True
    elif "kubernetes" in  url.lower():
        logger.info("Kubernetes Filter Activated")
        meta["code_name"]="nso-on-kubernetes"
        resource_switch=True
    if resource_switch:
        result=get_db_resource(meta)
    else:
        meta["url"]=url
        result=vectordb.get(where=meta)
    return result
        

def query_vdb(query,mode="similarity",top_result=2):
    out=""
    metas={}

    if "resource manager" in  query.lower() or "resource-manager" in query.lower() or "IP Address Allocator" in query.lower() or "ID Allocator" in query.lower():
        logger.info("Resource Manager Filter Activated")
        metas["code_name"]="resource-manager"
    elif  "observability exporter" in  query.lower() or "observability-exporter" in  query.lower() or "observability" in  query.lower():
        logger.info("Observability Exporter Filter Activated")
        metas["code_name"]="observability-exporter"
    elif "phased provisioning" in  query.lower() or "phased-provisioning" in  query.lower():
        logger.info("Phased Provisioning Filter Activated")
        metas["code_name"]="phased-provisioning"
    elif "kubernetes" in  query.lower():
        logger.info("Kubernetes Filter Activated")
        metas["code_name"]="nso-on-kubernetes"

    if "code_name" in metas.keys():
        logger.info("Resource Tab Agent Query Mode")
        out=query_vdb_resource(query,mode,top_result=top_result,filter=metas)
    else:
        logger.info("Querying Vector DB in "+ mode+": "+ query)
        datas={}
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
        title_str_sum=""
        for res in results:
            logger.info("Result obtained from vdb: "+str(res))
            index=""
            for key,title in res.metadata.items():
                index=index+title+"-"
            index=index[:-1]
            #print(index)
            title_str="title: "
            url_str="url: "
            ver_str="NSO Version: "
            for title,data in res.metadata.items():
                if "Header" in title:
                    title_str=title_str+data+" - "
                    logger.info(title)
                    if "1" in title:
                        title_str_sum=title_str+data+" Summary"
                elif "url" in title:
                    url_str=url_str+data
                elif "NSO Version" in title:
                    ver_str=ver_str+data

            #print(title_str)
            title_str= title_str[:-3]
            source=title_str+", "+url_str+", "+ver_str
            #print(res)
            datas[index]="source: "+str(source)+"\nresult: "+res.page_content
            logger.info("Result obtained from vdb - Loaded: "+str(res))

            #print("source: "+res.metadata['url']+"\nresult: "+res.page_content)
        for data in datas.values():
            out=out+data+"\n\n"
        logger.info("Querying Vector DB in "+ mode+": "+ query+" Done")
    return out


#https://nso-docs.cisco.com/guides/nso-6.3/operation-and-usage/operations/nso-device-manager#user_guide.devicemanager.initialize-device

def add_vdb_byurls(urls):
    #documents=loader(urls)
    splitted_doc=splitter(urls)
    logger.info("Actual Processed URL: "+str(len(splitted_doc)))
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
#    url_nav=["https://nso-docs.cisco.com/guides"]
    nso_vers=config["doc_vers"]
    for ver in nso_vers:
        logger.info("Loading NSO "+str(ver)+" documentation")
        if ver == "latest":
            url_nav=["https://nso-docs.cisco.com/","https://nso-docs.cisco.com/guides/","https://nso-docs.cisco.com/developers/"]
        else:
            url_nav=["https://nso-docs.cisco.com/",f"https://nso-docs.cisco.com/guides/nso-{ver}/",f"https://nso-docs.cisco.com/developers/nso-{ver}/"]
        scraped_urls=get_all_urls(url_nav)
        scraped_urls=list(set(scraped_urls))
        logger.info("Total URL: "+str(len(scraped_urls)))
        if check:
            add_vdb_byurls(scraped_urls)
    resource_init()

#vdb_init(init)

def get_all_urls(url_nav):
    urls = []
    pool = {}
    with ThreadPoolExecutor(config['init_thread_limit']) as executor:
        future_pool={executor.submit(get_all_url, url,urls): url for url in url_nav}
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

def generate_summarize(url):
    if "," in url:
        url=url.replace(",","")
    url=url.strip()
    sum=summarize_get(url)
    if not sum or "final_summary" not in sum["summary"]:
        logger.info("no cached summary found for "+url+". regenerate")
        docs=get_db(url)
        splitted_doc=[]
        for meta,doc in zip(docs['metadatas'], docs['documents']):
            document = Document(
                page_content=doc,
                metadata=meta
                )
            splitted_doc.append(document)
        sum=summarize_add(url,splitted_doc)
        if sum:
            logger.info(sum)
            if "final_summary" in sum:
                sum=sum["final_summary"]
            else:
                sum=""
            sum="source:  url: "+url+sum
        else:
            sum=""
        #print(sum)
    else:
        logger.info("cached summary found for "+url+". extracted")
        #logger.info(sum)
        sum=sum["summary"]["final_summary"]
        sum="source:  url: "+url+sum
    return sum

    


if __name__=="__main__":
    vdb_init(True)

    #datas=generate_summarize("https://nso-docs.cisco.com/guides/administration/installation-and-deployment/system-install")
    #print(datas)
    # for key,data in datas.items():
    #     print()
    #     print("==========================================")
    #     print(key)
    #     print(data)
    #database={}
    #contents={}
    #nso_ver="latest"
    #manager = Manager()
    #global database
    #database={}
    #add_vdb_byurls(["https://nso-docs.cisco.com/guides/administration/installation-and-deployment/system-install"])


    #query="Which JDK version should I use for NSO 6.1?"
    #data=vdb_init(query,top_result=2)
    #print("===========Return Data=====================")
    #print(data)
    #print("================================")

    
