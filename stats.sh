cat logs/webex.log | grep "Receive request!" > logs/audit.log

echo "User List:"
python stats.py

