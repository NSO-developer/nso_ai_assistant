cat ~/git/nso_ai_assistant/logs/webex.log | grep "Receive request!" > ~/git/nso_ai_assistant/logs/audit.log

echo "User List:"
python stats.py

