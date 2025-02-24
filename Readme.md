# NSO AI Assistant
This project explore 3 approach to build a AI Assistant that can answer NSO related question based on the NSO Gitbook Guide - https://cisco-tailf.gitbook.io/nso-docs/. 

* Gitbook Search - The first approach rely on the Gitbook Search of the NSO Gitbook Guide and build a RAG and Vector Database above it. Gitbook does have its own AI feature, however it is not tailed for NSO usage. In this case, the answer that came back can not be used as support purpose. 
* Langchain RAG - While the second way is with Langchain to construct a tailed RAG that have the following goal
    * Vector Datastore need to tailed to NSO Gitbook Guide with one chapter per chunk
    * When query, enough support is provided to retrive from the Vector Datastore
    * Data must be cleaned and easy to understand by the LLM
* Hybrid - Hybrid between Gitbook Search and Langchain RAG by taking the top 1 result from both search and use it together to construct query towards AI module. In this case, we benifit from the pros and cons on both module and trying to create more neutral result. At the same time, Gitbook Search failed to match, Langchain RAG will try to take over. In this case, we can make up to the non-match issue of the Gitbook Search.

At the same time, this repository also have Userbased Agent Memory. It can answer the question based on previous interaction with the AI. The memory is constructed with a conversational RAG. By query the RAG and extract top 2 relevent conversation previously.

Therefore I created this repository to provide more accurate AI searching engine/bot to answer quick question from NSO Customer and Developer side. 

To compare our design with more general approach like AnythingLLM, we also provide testcode to interact with AnythingLLM as RAG and retrive answer. We call it alternative approach in this readme guide.

<img src="https://github.com/NSO-developer/nso_ai_assistant/blob/main/others/nso_ai_design.png" alt="NSO AI Pipeline Design" width="800" height="600">

## Available Feature and Known Issue
* Answer NSO related question that has been specified in the Gitbook
* Code Generation is not ideal at moment. It can generate, but it has quite a lot of mistake. Especially Java API perform much worse than Python API.

## Pros and Cons  
![Pros and Cons](https://github.com/NSO-developer/nso_ai_assistant/blob/main/others/pros_cons.png)

## Pre-requisition
* Chat Model Requirment: 
    * llama3.3 70B(Recommend) llama3.1 7B(Entry Requirment but with slow reply speed and instability answer)  
        * llama3.3 70B use together.ai - meta-llama/Llama-3.3-70B-Instruct-Turbo-Free
        * llama3.1 7B offline model with ollama and AnythingLLM
    * Deepseek is not supported since it complicated task some time. 
* Embedded Model Requirment
    * By default, the repository is built and tested with "sentence-transformers/all-mpnet-base-v2". We also recommend to use this one from Huggingface
* Hardware Requirment on AI Model Server(if deploy localy)
    * llama3.3 70B - Min 64gb RAM + RTX 4090. Recommend 128gb RAM + RTX4090 * 2
    * llama3.1 7B - Min 64gb RAM + RTX3070. Recommend 128gb RAM + RTX3070
    The lack of physical RAM can be compensate by GPU vRAM. Lacking of memory will triger OOM and cause AI model reply empty content. 
* Take in mind that this code use Selenium with Chrome as driver to scrap the gitbook search feature(Not gitbook AI). This might violet some security regulation for some orgnization. 

If you want to use the alternative approach compare the result with our version of approach, the following pre-requisiton is also required.
* RAG - AnythingLLM Docker
* (OPTIONAL) Ngrok towards AnythingLLM Port if needed

## Test Enviorment
* Linux Ubuntu 24
* Python 3.9.21 / Python 3.13
* AI Chat Model - Together.ai "meta-llama/llama-3.3-70B-Instruct-Turbo-Free"
* Embedder for LangChain RAG - HuggingFace "sentence-transformers/all-mpnet-base-v2"


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
    "database_check_time":"01:00"
}
```
deploy_mode can be "remote" or "local". "remote" is remote deployment with together.ai while "local" is offline deployment with ollama. At the same time "model_name" is the AI model you are decide to use locally or remote from together.ai. The "together_mode" is the mode of the API which can be "legacy" API request through "requets" via HTTPs  - "legacy" or throuhg together Python API - "api". This option is not used when "deploy_mode" is set to "local". Than the parameter "com_int" is the communication interface setting. It can set to "webex" that makes the AI act as a webex bot or interact with CLI interface locally. Eventually, the "bot_email_prefix" parameter limit which email address prefix will the bot answer to. This can help orgnization limit the coverage of the bot.  
The repository also support Github issue creting feature to collect feedback from the user. To specify which repository you want to open issue on, configure the repository url under "github_repo_url".  
For data knowledge base, the repository support 3 mode that configured in "get_content_type". "gitbook_search" mode rely on Gitbook search to obtain informtion. At the same time, "langchain_rag" pull all the information from the Gitbook first and construct a Vector Datastore, than search inside this Vector Datastore with specific keyword that extract from the question. This Vector Datstore is tailed for NSO Gitbook Guide to make sure the search maintain high efficiency. Embedder that used in the langchain is specified in "embedding_model" and this embedder reside on Huggingface when the "deploy_mode" is remote. When the "deploy_mode" is local, embedder is used from Ollama server locally. Eventually, the database is checked at everyday at the time mentioned in "database_check_time" to see if it is up to date. The up to date standard is defined by if the last documentation pull is later than "doc_keepalive" amount of days or not. The last mode is "hybrid" mode which balance between the two mode and take the first chice of each method when constructing the query. The pros and cons of each mode can find in the Pros and Cons chapter above. 



### CLI - "com_int":"cli"

#### Online Model - llama3.3 70B use together.ai
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


#### Offline Model - llama3.1 8B

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
export OLLAMA_URL="<Ollama URL>"
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


## Sample Interaction
### Webex
<img src="https://github.com/NSO-developer/nso_ai_assistant/blob/main/others/webex.png" alt="Webex Bot" width="500" height="800">


### CLI

```
User>
What is CDB?
AI> 
Seems like you want some answer on general question. Let me think.....

AI> 
CDB stands for Configuration Database, which is a built-in database in Cisco NSO (Network Services Orchestrator). The CDB is designed to store two main things: 

1. Intent: This describes what you want from the network, traditionally referred to as a network service, which is what the network ultimately provides to its users.
2. Network state: This is a copy of the configuration of the managed devices. Knowledge of the network state is essential for correctly provisioning new services, enabling faster diagnosis of problems, and is required for advanced functionality such as self-healing.

The CDB is a crucial component of NSO, allowing it to keep track of the desired network configuration (intent) and the actual network configuration (network state). This enables NSO to automate network configuration and management tasks.

In terms of structure, the CDB can be extended with packages, which allows users to add custom data models and functionality to NSO. For example, the `examples.ncs/getting-started/cdb-yang` package provides an example implementation of how to extend the CDB with YANG models.

To interact with the CDB, NSO provides various APIs and tools, such as the `ncs-run` command, which allows users to execute scripts and automate tasks on the network devices.

Source:
- https://cisco-tailf.gitbook.io/nso-docs/guides/nso-6.3/development/introduction-to-automation/cdb-and-yang
- https://cisco-tailf.gitbook.io/nso-docs/guides/development/introduction-to-automation/cdb-and-yang
      
Average execution time: 29.175559043884277
      
I did not do well? Leave me a [Feedback]() on Github 

```
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
            * Gitbook URL - https://cisco-tailf.gitbook.io/nso-docs
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


## Feedback Feature

The repository also have the feature of collecting feedback in Github as an issues. By default this is set towards the NSO-developer repository - "https://github.com/NSO-developer/nso_ai_assistant". When creating the issue, the issue description will be pre-populated with the following content. This can make the issue open easier. 
```
**Question**
{Question Asked}

**Answer from AI**
{Anser Got}

**Expected Answer(Optional)**
What do you want to see and how should it be improved.

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
