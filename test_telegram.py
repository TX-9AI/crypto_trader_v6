import requests

token   = '7889560828:AAH7Zk5D6-Dyf6cFmU1bNsN9TN_eE5wpX7k'
chat_id = '6075312586'

r = requests.post(
    f'https://api.telegram.org/bot{token}/sendMessage',
    json={'chat_id': chat_id, 'text': '✅ crypto-trader Telegram alerts working'}
)
print(r.status_code, r.json())
