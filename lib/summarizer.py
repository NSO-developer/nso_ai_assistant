#https://python.langchain.com/docs/tutorials/summarization/

from langchain_core.prompts import ChatPromptTemplate

from typing import Annotated, List, Literal, TypedDict
from langchain.chains.combine_documents.reduce import (
    collapse_docs,
    split_list_of_docs,
)
from langchain_core.documents import Document
from langgraph.constants import Send
from langgraph.graph import END, START, StateGraph
from langchain_together import ChatTogether
from langchain_ollama import ChatOllama
from openai import RateLimitError
from langgraph.pregel import RetryPolicy
from langchain_core.rate_limiters import InMemoryRateLimiter


import operator
import json
import os
import sqlite3
import logging
import pickle
import time

handler = logging.FileHandler("logs/langchain_summarizer.log")        
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('langchain_summarizer')
logger.setLevel(logging.INFO)
logger.addHandler(handler)

conn = None

def sql_create():
    logger.info(f"sql_create")
    conn.execute('''CREATE TABLE SUMMARY
         (URL TEXT PRIMARY KEY     NOT NULL,
         SUMMARY          BLOB    NOT NULL);''')
    logger.info("Table created successfully")

def sql_update(url,summary):
    #sum=summary["final_summary"].replace('"', r'\"').replace("'", r"\'").replace("`", r"\`")
    #sum=pickle.dumps(summary["final_summary"])
    summary_bin=pickle.dumps(summary)
    logger.info(f"sql_update - {url}  - {summary_bin}")
    query=f'UPDATE SUMMARY set SUMMARY=? where URL="{url}"'
    #print(query)
    conn.execute(query, (summary_bin,))
    conn.commit()
    logger.info(f"Records {url} update successfully")


def sql_add(url,summary):
    if sql_get(url):
        logger.info(f"Index {url} exist. Updating")
        sql_update(url,summary)
    else:
        #sum=summary["final_summary"].replace('"', r'\"').replace("'", r"\'").replace("`", r"\`")
        #sum=pickle.dumps(summary["final_summary"]) 
        summary_bin=pickle.dumps(summary) 
        logger.info(f"sql_add - {url} - {summary_bin}")
        conn.execute(f'INSERT INTO SUMMARY (URL,SUMMARY) VALUES ("{url}", ?)', (summary_bin,))
        conn.commit()
        logger.info("Records created successfully")

def sql_get(url):
    out={}
    #url_bin=pickle.dumps(url) 
    #print(f'SELECT URL,SUMMARY from SUMMARY where URL ="{url}"')
    logger.info(f"sql_get - {url}")
    try:
        cursor = conn.execute(f'SELECT SUMMARY from SUMMARY where URL="{url}"')
    except:
        logger.info(f"Table not exist. Creating Table")
        sql_create()
        cursor = conn.execute(f'SELECT SUMMARY from SUMMARY where URL="{url}"')
    if not cursor:
        logger.info(f'Item not found for  URL = "{url}"')
    else:    
        for row in cursor:
            #print(row[0])
            out['url']=url
            #print( str(row[0]))
            out['summary']=pickle.loads(row[0])
        #logger.info(out)
        logger.info(f"Operation sql_get done successfully - {out}")
    if len(out) == 0:
        out=None
        logger.info(f'Item not found for  URL = "{url}"')
    return out

def sql_close():
    conn.close()


def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data


def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data

config=load_config()
token=os.environ['TOGETHER_API_KEY']
rate_limiter = InMemoryRateLimiter(
    requests_per_second=config["llm_rate_limit_summarizer"]["requests_per_second"],  # <-- Super slow! We can only make a request once every 10 seconds!!
    check_every_n_seconds=config["llm_rate_limit_summarizer"]["check_every_n_seconds"],  # Wake up every 100 ms to check whether allowed to make a request,
    max_bucket_size=config["llm_rate_limit_summarizer"]["max_bucket_size"],  # Controls the maximum burst size.
)

def init_llm_local():
    llm = ChatOllama(model=config["model_name"],base_url=config["ollama"]["url"], rate_limiter=rate_limiter)
    return llm

def init_llm():
    if config["deploy_mode"] == "local":
        llm=init_llm_local()
    elif config["deploy_mode"] == "remote":
        llm = ChatTogether(
            together_api_key=token,
            model=config["model_name"],
            rate_limiter=rate_limiter,
            max_retries=3
        )
    return llm

llm=init_llm()
map_prompt = ChatPromptTemplate.from_messages(
    [("system", "Write a concise summary of the following:\\n\\n{context}")]
)
token_max = 1000
reduce_template = """
    The following is a set of summaries:
    {docs}
    Take these and distill it into a final, consolidated summary
    of the main themes.
    """
reduce_prompt = ChatPromptTemplate([("human", reduce_template)])


def length_function(documents: List[Document]) -> int:
    """Get number of tokens for input contents."""
    return sum(llm.get_num_tokens(doc.page_content) for doc in documents)


# This will be the overall state of the main graph.
# It will contain the input document contents, corresponding
# summaries, and a final summary.
class OverallState(TypedDict):
    # Notice here we use the operator.add
    # This is because we want combine all the summaries we generate
    # from individual nodes back into one list - this is essentially
    # the "reduce" part
    contents: List[str]
    summaries: Annotated[list, operator.add]
    collapsed_summaries: List[Document]
    final_summary: str


# This will be the state of the node that we will "map" all
# documents to in order to generate summaries
class SummaryState(TypedDict):
    content: str


# Here we generate a summary, given a document
def generate_summary(state: SummaryState):
    logger.info("generate_summary")
    prompt = map_prompt.invoke(state["content"])
    # try:
    response = llm.invoke(prompt)
    # except RateLimitError as e:
    #     print("Timeout. Retry in 1 min")
    #     time.sleep(60)
    #     generate_summary(state)
    logger.info({"summaries": [response.content]})
    return {"summaries": [response.content]}


# Here we define the logic to map out over the documents
# We will use this an edge in the graph
def map_summaries(state: OverallState):
    logger.info("map_summaries")
    # We will return a list of `Send` objects
    # Each `Send` object consists of the name of a node in the graph
    # as well as the state to send to that node
    return [
        Send("generate_summary", {"content": content}) for content in state["contents"]
    ]


def collect_summaries(state: OverallState):
    logger.info("collect_summaries")
    return {
        "collapsed_summaries": [Document(summary) for summary in state["summaries"]]
    }


def _reduce(input: dict) -> str:
    logger.info("_reduce")
    prompt = reduce_prompt.invoke(input)
    response = llm.invoke(prompt)
    return response.content


# Add node to collapse summaries
def collapse_summaries(state: OverallState):
    logger.info("collapse_summaries")
    doc_lists = split_list_of_docs(
        state["collapsed_summaries"], length_function, token_max
    )
    results = []
    for doc_list in doc_lists:
        results.append(collapse_docs(doc_list, _reduce))

    return {"collapsed_summaries": results}


# This represents a conditional edge in the graph that determines
# if we should collapse the summaries or not
def should_collapse(
    state: OverallState,
) -> Literal["collapse_summaries", "generate_final_summary"]:
    logger.info("should_collapse")
    num_tokens = length_function(state["collapsed_summaries"])
    if num_tokens > token_max:
        return "collapse_summaries"
    else:
        return "generate_final_summary"


# Here we will generate the final summary
def generate_final_summary(state: OverallState):
    logger.info("generate_final_summary")
    response = _reduce(state["collapsed_summaries"])
    return {"final_summary": response}


# Construct the graph
# Nodes:
graph = StateGraph(OverallState)
# RetryPolicy(initial_interval=0.5, backoff_factor=2.0, max_interval=128.0, max_attempts=3, jitter=True, retry_on=<function default_retry_on at 0x78b964b89940>)
graph.add_node("generate_summary", generate_summary,retry=RetryPolicy(retry_on=RateLimitError,initial_interval=config["llm_rate_limit_summarizer"]["retry_timeout"],max_attempts=30))  # same as before
graph.add_node("collect_summaries", collect_summaries,retry=RetryPolicy(retry_on=RateLimitError,initial_interval=config["llm_rate_limit_summarizer"]["retry_timeout"],max_attempts=30))
graph.add_node("collapse_summaries", collapse_summaries,retry=RetryPolicy(retry_on=RateLimitError,initial_interval=config["llm_rate_limit_summarizer"]["retry_timeout"],max_attempts=30))
graph.add_node("generate_final_summary", generate_final_summary,retry=RetryPolicy(retry_on=RateLimitError,initial_interval=config["llm_rate_limit_summarizer"]["retry_timeout"],max_attempts=30))

# Edges:
graph.add_conditional_edges(START, map_summaries, ["generate_summary"])
graph.add_edge("generate_summary", "collect_summaries")
graph.add_conditional_edges("collect_summaries", should_collapse)
graph.add_conditional_edges("collapse_summaries", should_collapse)
graph.add_edge("generate_final_summary", END)


def invoke_summarizer(app, split_docs,counter=0):      
    data=app.invoke(
                {"contents": [doc.page_content for doc in split_docs]},
                {"recursion_limit":25 },
    )

    return data


def black_list_add(url):
    path='resources/index_db/black_list.json'
    with open(path, 'r') as file:
      black_list = json.load(file)
    black_list["block"].append(url)

    with open(path, "w+") as outfile:
        outfile.write(json.dumps(black_list))

def black_list_check(url):
    path='resources/index_db/black_list.json'
    with open(path, 'r') as file:
      black_list = json.load(file)
    if url not in black_list["block"]:
        return False
    else:
        return True
       

def summarize_add(url,split_docs):
    #print(split_docs)
    global conn
    if "section" not in url and not black_list_check(url):
        try:
            conn = sqlite3.connect('resources/index_db/index.db')
            logger.info("Opened database successfully")
            app = graph.compile()
            logger.info("summary start")
            data=invoke_summarizer(app, split_docs)
            sql_add(url,data)
            sql_close()
            return data
        except Exception as e:
            logger.error("Error indicat when summarizing - "+ str(url) + " SKIPPING")
            logger.error(e)
            black_list_add(url)
            return None
    else:
        logger.error("URL - "+ url +" Found in the Black List. SKIPPING")
        return None

def summarize_get(url):
    global conn
    conn = sqlite3.connect('resources/index_db/index.db')
    logger.info("Opened database successfully")
    output=sql_get(url)
    logger.info("Summary Extracted - "+str(output))
    sql_close()
    return output    




# if __name__=="__main__":
#     summarize(split_docs)