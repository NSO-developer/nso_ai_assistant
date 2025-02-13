export WORKSPACE=""
#export WORKSPACE="escalation-team-test-bed"
export ANYTHINGLLM_IP=""
export ANYTHINGLLM_PORT=""
export ANYTHINGLLM_API_TOKEN=""
export pipline_mode="general"
export ai_bot_token=""

#Webhook URL for Webex Server
Webhook_URL=""

if [ "$1" == "--webhook_reg" ]
  then 
  python webex.py --webhook_reg $Webhook_URL
elif [ "$1" == "--webex" ]
  then 
  python webex.py
elif [ "$1" == "--cli" ]
  then 
  python ollama_handler.py
fi