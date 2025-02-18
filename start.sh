# online with together.ai
export "ai_bot_token="
export pipline_mode="nso"

export TOGETHER_API_KEY=""
export TAVILY_API_KEY=""

#offline with ollama
export OLLAMA_URL=""
export TOKENIZERS_PARALLELISM=true


if [ "$1" == "--webhook_reg" ]
  then 
  python webex.py --webhook_reg $OLLAMA_URL
elif [ "$1" == "--webex" ]
  then 
  python webex.py
elif [ "$1" == "--cli" ]
  then 
  python llama_handler.py
fi
