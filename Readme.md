# NSO AI Assistant
This project intend to build a Multi-Agent AI Assistant that can answer NSO related question based on the NSO Gitbook Guide - https://nso-docs.cisco.com/ and NSO Changelog Explorer - https://developer.cisco.com/docs/nso/ned-changelog-explorer/. 


For NSO Gitbook Agent, we explore 3 different approach to achieve as high accuracy as possible
* Gitbook Search - The first approach rely on the Gitbook Search of the NSO Gitbook Guide as search engine. Gitbook does have its own AI feature, however it is not tailed for NSO usage. In this case, the answer that came back can not be used as support purpose. Do not recommend to use this mode by itself as it use large memory with low accuracy.
* Langchain RAG - The second way is with Langchain to construct a tailed RAG that have the following goal
    * Vector Datastore need to tailed to NSO Gitbook Guide with one chapter per chunk
    * When query, enough support is provided to retrive from the Vector Datastore
    * Data must be cleaned and easy to understand by the LLM
* Hybrid - Hybrid between Gitbook Search and Langchain RAG by taking the top 1 result from both search and use it together to construct query towards AI module. In this case, we benifit from the pros and cons on both module and trying to create more neutral result. At the same time, Gitbook Search failed to match, Langchain RAG will try to take over. In this case, we can make up to the non-match issue of the Gitbook Search.

For NSO Changelog Agent, only Langchain RAG mode is allowed since no complicated method is required. 

At the same time, this repository also have User-based Agent Memory. It can answer the question based on previous interaction with the AI. The memory is constructed with a conversational RAG. By query the RAG and extract top 2 relevent conversation previously.

To compare our design with more general approach like AnythingLLM, we also provide testcode to interact with AnythingLLM as RAG and retrive answer. We call it alternative approach in this readme guide.

## Architecture
![Arch](https://github.com/NSO-developer/nso_ai_assistant/blob/main/others/nso_ai_arch.png)


Design is inspired by the following post
[1]“How to build an AI search engine (OSS Perplexity Clone),” Together, 2025. https://docs.together.ai/docs/ai-search-engine (accessed Jan. 28, 2025).


## Available Feature and Limitations
* Answer NSO related question that has been specified in the Gitbook
* Answer queston about specific fix or from specific BEMs support case number, CDETs number, RT Number or SR number from Changelog Explorer
* Code Generation is not ideal at moment. It can generate, but it has quite a lot of mistake. Especially Java API perform much worse than Python API.
* Only support Webex direct message for now. Group message is not supported.
* Unique support hybrid context mode that use the context between Gitbook Search and Langchain Chroma RAG to provide the best result.


## Sample Interaction
### Webex
![Webex Bot](https://github.com/NSO-developer/nso_ai_assistant/blob/main/others/webex.png)

### CLI
```
User>
AI>
Before we start, please let me know who you are. What is your Username?
User>
testuser
Hi testuser. What can I help you about Cisco NSO today?

testuser>
what is CDB
AI> 
Seems like you want some answer on general question. Let me think..... This might takes around 45 sec to 1 min.

AI> 
The Configuration Database (CDB) in Cisco NSO is a dedicated, built-in storage for data that efficiently stores and accesses network configuration data, such as device configurations, service parameters, and even configuration for NSO itself. It functions as a central repository for storing and managing network device configurations, playing a crucial role in network automation.

The CDB has several key features that make it an excellent choice for a configuration store:

1. **Hierarchical database structure**: The CDB has a tree-like structure, similar to a big XML document, which allows it to store all kinds of data.
2. **Fast and lightweight database access**: The CDB provides fast and lightweight database access through a well-defined API.
3. **Subscription mechanism**: The CDB has a subscription ("push") mechanism for change notification, which enables real-time updates.
4. **Transaction support**: The CDB supports transactions, ensuring data consistency and preventing data corruption.
5. **Rich and extensible schema**: The CDB's schema is based on YANG (RFC 7950), a standard modeling language that describes constraints on the data and allows for efficient storage.
6. **Built-in support for schema and data upgrade**: The CDB has built-in support for schema and associated data upgrade, making it easy to manage changes to the configuration.
7. **Close integration with NSO**: The CDB is closely integrated with NSO, providing low-maintenance operation.

The CDB stores two primary types of data:

1. **Intent**: The CDB stores the intent, which describes what you want from the network, traditionally referred to as a network service.
2. **Network state**: The CDB stores a copy of the configuration of the managed devices, which represents the network state.

By storing both intent and network state, the CDB enables correct provisioning of new services, faster diagnosis of problems, and advanced functionality like self-healing.

In terms of performance, the CDB keeps a configurable amount of configuration data in RAM, in addition to persisting it to disk, which speeds up operations. The CDB also stores transient operational data, such as alarms and traffic statistics, which can be persisted to disk if required.

Sources:

* https://nso-docs.cisco.com/guides/nso-6.3/development/introduction-to-automation/cdb-and-yang
* Title: CDB and YANG - Key Features of the CDB (no URL provided)
      
Average execution time: 21.693789958953857
      
I did not do well? Leave me a [Feedback]() on Github 

```
Video Demo: https://youtu.be/ZpOkrgI_0E4
## Pros and Cons  
![Pros and Cons](https://github.com/NSO-developer/nso_ai_assistant/blob/main/others/pros_cons.png)

## Pre-requisition
* Chat Model Requirment: 
    Use "remote" mode can ignore the hardware requirment listed below.
    * Gitbook/Hybrid:
        llama3.3 70B - Min 128gb RAM + RTX 4090. Recommend 128gb RAM + RTX 5090
    * Langchain RAG
        llama3.1 8B  - Min 64gb RAM + RTX3070. Recommend 128gb RAM + RTX3070
    * Deepseek is not supported since it complicated task some time. 
* Embedded Model Requirment
    * By default, the repository is built and tested with "sentence-transformers/all-mpnet-base-v2". We also recommend to use this one from Huggingface 
* Take in mind that this code use Selenium with Chrome as driver to scrap the gitbook search feature(Not gitbook AI). This might violet some security regulation for some orgnization. 

If you want to use the alternative approach compare the result with our version of approach, the following pre-requisiton is also required.
* RAG - AnythingLLM Docker
* (OPTIONAL) Ngrok towards AnythingLLM Port if needed

## Test Enviorment
* Linux Ubuntu 24
* Python 3.9.21 / Python 3.11
* AI Chat Model
    * remote - Together.ai "meta-llama/llama-3.3-70B-Instruct-Turbo-Free"
    * local - Ollama "llama3.1:8b" / "llama3.3:70b"
* Embedder for LangChain RAG
    * remote - HuggingFace "sentence-transformers/all-mpnet-base-v2"
    * local - Ollama "nomic-embed-text"


## Usage
* Install Python API requirment
```
make deps
```
You can choose the deployment method between online deployment with together.ai or local deployment with ollama. Configure the deployment method in "deploy_mode" variable in config.json file. 
```
{
    "deploy_mode": "remote",
    "model_name":"meta-llama/llama-3.3-70B-Instruct-Turbo-Free",
    "embedding_model":"sentence-transformers/all-mpnet-base-v2",
    "together_mode":"api",
    "com_int":"cli",
    "bot_email_prefix":"cisco.com",
    "github_repo_url": "https://github.com/NSO-developer/nso_ai_assistant",
    "doc_keepalive": 14,
    "get_content_type":"langchain_rag",
    "database_check_time":"01:00",
    "doc_vers":["6.1","latest"],
    "api_token":[""],
    "init_thread_limit":3

}
```
deploy_mode can be "remote" or "local". "remote" is remote deployment with together.ai while "local" is offline deployment with ollama. At the same time "model_name" is the AI model you are decide to use locally or remote from together.ai. The "together_mode" is the mode of the API which can be "legacy" API request through "requets" via HTTPs  - "legacy" or throuhg together Python API - "api". This option is not used when "deploy_mode" is set to "local". Than the parameter "com_int" is the communication interface setting. It can set to "webex" that makes the AI act as a webex bot or interact with CLI interface locally. Eventually, the "bot_email_prefix" parameter limit which email address prefix will the bot answer to. This can help orgnization limit the coverage of the bot.  
The repository also support Github issue creting feature to collect feedback from the user. To specify which repository you want to open issue on, configure the repository url under "github_repo_url".  

For data knowledge base, the repository support 3 mode that configured in "get_content_type". "gitbook_search" mode rely on Gitbook search to obtain informtion. At the same time, "langchain_rag" pull all the information from the Gitbook first and construct a Vector Datastore, than search inside this Vector Datastore with specific keyword that extract from the question. This Vector Datstore is tailed for NSO Gitbook Guide to make sure the search maintain high efficiency.  
The Embedder that used in the langchain is specified in "embedding_model" and this embedder reside on Huggingface when the "deploy_mode" is remote. When the "deploy_mode" is local, embedder is used from Ollama server locally.  

When starting up the agent, the code will load various version of NSO Gitbook documentation that specify in "doc_vers" into the RAG. These docment construct the initial version of the vector knowledge base. The knowledge is checked at everyday at the time mentioned in "database_check_time" to see if it is up to date. The up to date standard is defined by if the last documentation pull is later than "doc_keepalive" amount of days or not. The last mode is "hybrid" mode which balance between the two mode and take the first chice of each method when constructing the query. The pros and cons of each mode can find in the Pros and Cons chapter above. 



### CLI - "com_int":"cli"

#### Online Model
* Fill in the API keys in start.sh
```
export TOGETHER_API_KEY=""
export TAVILY_API_KEY=""
```
TOGETHER_API_KEY is the key for together.ai 
TAVILY_API_KEY is the key that used from Tavily LLM Search engine that used to locate nessasary network knowledge and Support Knowledge. 
* Start the bot with the following command
```
sh start.sh --cli
```


#### Offline Model

* Deploy offline model
```
make build_model_server
```
or follow the guide - https://ollama.com/download/linux
* Add the following enviormental parameter in /etc/systemd/system/ollama.service
```
Environment="OLLAMA_MODELS=/usr/share/ollama/.ollama/models"
Environment="OLLAMA_HOST=0.0.0.0:11434"
```
* Reload the ollama.service
```
systemctl daemon-reload
systemctl start ollama
```
* Modify client API by providing Ollama server contact detail in start.sh
```
export OLLAMA_URL="<Ollama URL>" #for example - "http://1.8.0.2:11434"
```
OLLAMA_URL is the remote address of the Ollama instance. This field is not needed if the "deploy_mode" set as "remote". You can leave it as a empty string.

* Start the bot with the following command
```
sh start.sh --cli
```

### Webex - "com_int":"webex"
Except the parameter required above, also proceed with the following
* Fill in the API keys and Webhook access URL for Webex server in start.sh
```
export "ai_bot_token="

Webhook_URL=""
```
"ai_bot_token" is the webex bot auth token
Webhook_URL is the Webhook access URL

* Register Webhook towards Webex bot with the token "ai_bot_token"
```
sh start.sh --webhook_reg
```

* Start the bot server with the following command
```
sh start.sh --webex
```

* Find your bot on Webex and interact with it

## Enhance Context Validation Mode (Expiermental Feature)
The Agent also feature enhance Context Validation Mode in Hybrid and Langchain RAG mode. When the feature is enabled, the Hybrid mode will use the summary of the full text as a extra factor to correct the incorrect context. For example, if context 1 is incorrect and context 2 is correct. Conext 1 will be swap to better source while a Summary is generated for Context 2 to provide better higher level overview based on the correct context.  The generated summary will be cached inside a SQL database. User can also choose if they want to pre-populate the summary during the Agent Booting Phase instead always generate on-demand.  
While using Langchain RAG mode, the summary will always be provided as part of the context.
This feature can be enalbed by switching the summarizer/enable to true in config.json. At the same time, decide if the summary should be pre-populated on the boot by setting summarizer/init_on_boot to true. If this is set to false, the summary will generate during the qurey phase. During the summary generation, one might want to limit the rate by setting the parameter under llm_rate_limit_summarizer. Some user might using a AI API that have rate limit. This will make the summary generation failed if the rate limit has been repeatly hit. Therefore limit the rate into a reasonable value is a good idea.  
Sample configuration can be found as below.
```
    "summarizer":{
        "enable": true,
        "init_on_boot":true
    },
    "llm_rate_limit_summarizer":{
        "requests_per_second": 0.2,
        "check_every_n_seconds":10,
        "max_bucket_size":10,
        "retry_timeout":61
    }
```

**BE AWARE!**  
Generating summary is extremly time consuming on boot or the query phase depends on the configuration of summarizer/init_on_boot. Turn this feature on can highly increase the accuracy of the outcome. However, if your AI API have very tough rate limit or your token cost a lot. We suggest you turn this feature off. However, after initial database population, the time consumption is negligible.

## API Access
Webex server mode also have a api access feature that can use to bridge this agent to other tools. API must be protected via token by specify the token in "api_token" at config.json.  To access the API use the following request
```
payload='{"data":{"id":"'$3'","personEmail":"'$2'","query":"'$4'"}}'
curl --header "Content-Type: application/json" \
  --header "Authorization: Bearer $5" \
  --request POST \
  --data  "$payload"\
  $1
```
while $1 is the url of the webex server, $2 is the email address of the user, $3 is the message id, $4 is the question you want to ask the AI and eventually $5 is the access token that specified in "api_token" at config.json.

## Feedback Feature

The repository also have the feature of collecting feedback in Github as an issues. By default this is set towards the NSO-developer repository - "https://github.com/NSO-developer/nso_ai_assistant". When creating the issue, the issue description will be pre-populated with the following content. This can make the issue open easier. 
```
**Question**
{Question Asked}

**Answer from AI**
{Answer Got}

**Expected Answer(Optional)**
What do you want to see and how should it be improved.

```

## Pre-populated Database
If you are having a hard time to populate the Summary Database or the RAG Database due to resource limitation, we have a pre-compiled one in populated_db folder. This database is compiled at 2025-04-18 and it might get outdated by the time goes since NSO doumentation is updated from time to time. To use this Pre-populated Database, simply untar the tarball inside the populated_db and replace the resource folder.

## Alternative Approach
This chapter shows how to use more general approach with RAG(AnythingLLM) + Ollama. You can test the result of this approach with the one we created as a AI Agent.  
This part of the code is for demo and testing purpose to compare with our version of approach.

#### Offline Model - llama3.1 8B with RAG
* Deploy offline model
```
make build_model_server
```
or follow the guide - https://ollama.com/download/linux
* Add the following enviormental parameter in /etc/systemd/system/ollama.service
```
Environment="OLLAMA_MODELS=/usr/share/ollama/.ollama/models"
Environment="OLLAMA_HOST=0.0.0.0:11434"
```
* Reload the ollama.service
```
systemctl daemon-reload
systemctl start ollama
```
* Install RAG -  AnythingLLM
```
docker run -d -p 3001:3001 \
--cap-add SYS_ADMIN \
-e STORAGE_DIR="/app/server/storage" \
mintplexlabs/anythingllm
```
* Configure AnythingLLM to link with Ollama as guide https://docs.anythingllm.com/installation-docker/local-docker 
* Create Workspace for AnythingLLM and start feed NSO Gitbook
    * Method 1 - Feed Gitbook Github Repository
        * Choose Data Connectors in Data Upload
        * Choose Gitbhub Repo
        * Provide the following Parameter:
            * GitHub Repo URL - https://github.com/NSO-developer/nso-gitbook/tree/main
            * Github Access Token - Generate token from your own account via https://github.com/settings/personal-access-tokens/new
            * Branch - main
    * Method 2 - Feed Gitbook HTML from URL
        * Choose Data Connectors in Data Upload 
        * Choose Bult Link Scraper
        * Provide the following Parameter:
            * Gitbook URL - https://nso-docs.cisco.com/
            * Depth - 3
            * Max Links - 100
* Add the newly added data into the Workspace
    * Choose Document in Data Upload
    * Choose newly added data and click "Move to Workspace"


* Modify client API by providing Ollama server contact detail in  start_ollama.sh
```
export WORKSPACE="<Workspace Name>" 
export ANYTHINGLLM_IP="<AnythingLLM IP Address>"
export ANYTHINGLLM_PORT=<AnythingLLM Port Default:3001>
export ANYTHINGLLM_API_TOKEN=<AnythingLLM API Token>
```
WORKSPACE obtained from Workspace Config - Vector Database - Vector database identifier
ANYTHINGLLM_API_TOKEN obtained from AnythingLLM Config - Tools - Developer API - Generate New

* Start the bot with the following command
```
sh start_ollama.sh --cli
```


## License
```
Copyright (c) 2025 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.  
```
