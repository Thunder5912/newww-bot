import os
import json
import requests
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, request
from telebot import TeleBot, types

app = Flask(__name__)
bot = TeleBot(os.getenv("TELEGRAM_TOKEN"))
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

def get_sheet():
    # Load credentials from Vercel Environment Variables securely
    creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(os.getenv("SPREADSHEET_ID")).sheet1

@app.route('/api/webhook', methods=['POST'])
def webhook():
    # Telegram sends user messages here
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

@bot.message_handler(commands=['add'])
def add_movie(message):
    # Restrict management to the Admin ID
    ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Unauthorized. Only the admin can add media.")
        return
        
    query = message.text.replace('/add', '').strip()
    if not query:
        bot.reply_to(message, "Usage: /add <Movie Name>")
        return
        
    try:
        sheet = get_sheet()
        sheet.append_row([query])
        bot.reply_to(message, f"✅ '{query}' added to the authorized list.")
    except Exception as e:
        bot.reply_to(message, f"Error writing to database: {str(e)}")

@bot.message_handler(commands=['search'])
def search_movie(message):
    query = message.text.replace('/search', '').strip()
    if not query:
        bot.reply_to(message, "Usage: /search <Movie Name>")
        return
        
    try:
        sheet = get_sheet()
        # Fetch all authorized movies from Column 1
        authorized_movies = [m.lower() for m in sheet.col_values(1)]
        
        if query.lower() in authorized_movies:
            # Fetch data from OMDb
            url = f"http://www.omdbapi.com/?t={query}&apikey={OMDB_API_KEY}"
            resp = requests.get(url).json()
            
            if resp.get("Response") == "True":
                reply = f"🎬 *{resp['Title']}* ({resp['Year']})\n"
                reply += f"⭐ IMDb Rating: {resp['imdbRating']}\n"
                reply += f"📝 Plot: {resp['Plot']}"
                poster = resp.get("Poster")
                
                if poster and poster != "N/A":
                    bot.send_photo(message.chat.id, poster, caption=reply, parse_mode="Markdown")
                else:
                    bot.reply_to(message, reply, parse_mode="Markdown")
            else:
                bot.reply_to(message, "Movie is authorized, but details were not found on OMDb.")
        else:
            bot.reply_to(message, f"⛔ '{query}' is NOT in your authorized media sheet.")
            
    except Exception as e:
        bot.reply_to(message, f"Error accessing database: {str(e)}")
