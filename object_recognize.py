from flask import Flask

import requests
import json
import base64
import os, io
import threading
import time
import traceback
import datetime

import telebot
from telebot import types

#import g4f

from pymongo import MongoClient
from gridfs import GridFS
from bson import ObjectId

from translate import Translator

app = Flask(__name__)

@app.route('/')
def index():
    return 'Hello from PhotoCap!'

client = MongoClient(os.environ('MONGO_CAP_KEY'))
db = client['CapBotDB']
users = db['users']
queue = db['queue']
moderation = db['moderation']
fs = GridFS(db)

url = "https://autocap-2djjl6ol5q-ew.a.run.app/"

token_bot = "6499675235:AAFXizHfWphpAdGcGmxrZaOCuoj7xln7Oe8"#os.environ.get('bot_token')
bot = telebot.TeleBot(token_bot)

chat_id = 0

username = ""
caption = ""

queue_list = [item['photo'] for item in queue.find()]

print("Connected!")

markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
lang_rus = types.KeyboardButton("На русском")
lang_kaz = types.KeyboardButton("Қазақша")
lang_eng = types.KeyboardButton("In English")
lang_ind = types.KeyboardButton("In Indonesian")

style_custom = types.KeyboardButton("Custom")
style_object = types.KeyboardButton("Object")

markup.add(lang_rus, lang_kaz, lang_eng, lang_ind)

def add_in_queue(chat_id):
  global queue_list
  lang = queue.find_one({"chat_id": chat_id}).get("lang")
  if lang == "rus":
    bot.send_message(chat_id, "Вы находитесь в очереди\nПодождите пару секунд...", reply_markup=types.ReplyKeyboardRemove())
  elif lang == "eng":
    bot.send_message(chat_id, "You are in the waiting line\nWait for a few seconds...", reply_markup=types.ReplyKeyboardRemove())
  elif lang == "kaz":
    bot.send_message(chat_id, "Сіз кезекте тұрсыз\nБірнеше секунд күтіңіз...", reply_markup=types.ReplyKeyboardRemove())
  elif lang == "ind":
    bot.send_message(chat_id, "Anda berada dalam antrian\nTunggu beberapa detik...", reply_markup=types.ReplyKeyboardRemove())
  queue_list = [item['photo'] for item in queue.find()]
  print(queue_list)

def generate_image():
  while True:
    global caption
    global queue_list

    if queue_list:
      try:
        photo_id = ObjectId(queue_list[0])
        user = queue.find_one({"photo": photo_id})
        if user:
          photo_object_id = user.get('photo')
          if photo_object_id:
              photo = fs.get(photo_object_id).read()
          lang = user.get('lang')
          style = user.get('style')
          id = user.get('id')
          money_count = user.get('money_count')
          chat_id = user.get('chat_id')
          username = user.get('username')
        
          base64_photo = base64.b64encode(photo).decode('utf-8')
        
          money_count = users.find_one({'id': id})['money_gpt4']
          if money_count < 50:
            bot.send_message(chat_id, "To buy more captions, contact the admin @sbsqcom\nЧтобы купить больше описаний к картинкам, напишите админу @sbsqcom", reply_markup=types.ReplyKeyboardRemove())
          elif money_count >= 50:
            caption = ''
          
            asticaAPI_key = '37D1AB8B-5945-4EA6-82C5-FBF1E4F3A7BCE665BEB2-6862-4299-A7B4-CF037A608A84'#os.environ.get('astica_token')
            asticaAPI_visionParams = 'gpt_detailed, describe_all, objects, faces'
            asticaAPI_modelVersion = '2.1_full'
            asticaAPI_gpt_prompt = ''
            asticaAPI_prompt_length = 40
            asticaAPI_timeout = 60
            asticaAPI_endpoint = 'https://vision.astica.ai/describe'
            asticaAPI_payload = {
              'tkn': asticaAPI_key,
              'modelVersion': asticaAPI_modelVersion,
              'input': base64_photo,
              'visionParams': asticaAPI_visionParams,
              'gpt_prompt': str(asticaAPI_gpt_prompt) + str(style),
              'prompt_length': asticaAPI_prompt_length
            }
            response = requests.post(asticaAPI_endpoint,
                                    data=json.dumps(asticaAPI_payload),
                                    timeout=asticaAPI_timeout,
                                    headers={
                                        'Content-Type': 'application/json',
                                    })
            if response.status_code == 200:
              caption = response.json().get('caption_GPTS')
              if lang == "rus":
                caption = Translator(from_lang="en", to_lang="ru").translate(caption)
              elif lang == "ind":
                caption = Translator(from_lang="en", to_lang="id").translate(caption)
              elif lang == "kaz":
                caption = Translator(from_lang="en", to_lang="kk").translate(caption)
              elif lang == "eng":
                caption = caption
          
              is_admin = users.find_one({'id': id})['is_admin']
              if is_admin == 0:
                users.update_one({'id': id}, {'$set': {'money_gpt4': money_count-50}})
                  
              markup = types.InlineKeyboardMarkup()    
              share = types.InlineKeyboardButton("🔥 Share in channel", callback_data="share")
              view = types.InlineKeyboardButton("🌐 View channel", callback_data="channel", url="https://t.me/aivisiongroup")
              markup.add(share, view)
              print(f"{username}:", caption)
              if lang == "rus" or lang == "kaz":
                  bot.send_message(chat_id, f'{caption}\n\nЕсли вы хотите поделиться своим результатом с комьюнити бота, нажмите на кнопку "Share in channel"', reply_markup=markup)
              else:
                  bot.send_message(chat_id, f'{caption}\n\nIf you want to share your result with community, press the button "Share in channel"', reply_markup=markup)
              bot.send_message(chat_id, "To upload new photo tap on /generate", reply_markup=types.ReplyKeyboardRemove())
            else:
              print('Failed to connect to the API.')
            queue.delete_one({"photo": photo_id})
            queue_list = [item['photo'] for item in queue.find()]
            print(queue_list)
      except:
          pass
    else:
      time.sleep(1)

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    global username
    global caption
    text = caption
    message_id = ''
    if call.data == "share":
        bot.answer_callback_query(call.id, "Thanks for sharing! Our admins check your description and post it to the channel")

        # markup = types.InlineKeyboardMarkup()    
        # accept = types.InlineKeyboardButton("✅ Принять", callback_data="accept")
        # deny = types.InlineKeyboardButton("❌ Отклонить", callback_data="deny")
        # markup.add(accept, deny)
        message_id = bot.send_photo(1128438093, photo, f"{username}: {text}", reply_markup=markup)
      
    # if call.data == "accept":
    #     if username == "None":
    #         username = "Unnamed"
         
    #     bot.send_photo("@aivisiongroup", photo, f"{username}: {text}")
    # elif call.data == "deny":
    #     pass
       
@bot.message_handler(commands=['start'])
def start_message(message):
  global chat_id
  global username

  requests.get(url)

  chat_id = message.chat.id
  if message.from_user.username is not None:
    username = message.from_user.username
  else:
    username = "None"
  id = message.from_user.id
  if users.find_one({'id': id}) is None:
    post = {"username": username, "id": id, "money": 150, "is_admin": 0, "money_gpt4": 50}
    users.insert_one(post) #CapCoin
    money_count = users.find_one({'id': id}).get('money_gpt4')
  else:
    money_count = users.find_one({'id': id}).get('money_gpt4')
  bot.send_message(message.chat.id, f"Hi! I am bot to describe pictures.\nYou have {money_count} CapCoins!\nYou have free trial to test 1 picture.")
  if money_count >= 50:
    bot.send_message(message.chat.id, "Send a picture and I will describe it.", reply_markup=types.ReplyKeyboardRemove())
  elif money_count < 50:
    bot.send_message(message.chat.id, "To buy more captions, contact the admin @sbsqcom\nЧтобы купить больше описаний к картинкам, напишите админу @sbsqcom", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(commands=['generate'])
def generate_message(message):
  global chat_id

  requests.get(url)

  chat_id = message.chat.id
  if message.from_user.username is not None:
    username = message.from_user.username
  else:
    username = "None"
  id = message.from_user.id

  #time.sleep(1)
  if users.find_one({'id': id}) is None:
    post = {"username": username, "id": id, "money": 150, "is_admin": 0, "money_gpt4": 50}
    users.insert_one(post) #CapCoin
    money_count = users.find_one({'id': id}).get('money_gpt4')
  else:
    money_count = users.find_one({'id': id}).get('money_gpt4')
  if money_count >= 50:
    bot.send_message(message.chat.id, "Send a picture and I will describe it.", reply_markup=types.ReplyKeyboardRemove())
  elif money_count < 50:
    bot.send_message(message.chat.id, "To buy more captions, contact the admin @sbsqcom\nЧтобы купить больше описаний к картинкам, напишите админу @sbsqcom", reply_markup=types.ReplyKeyboardRemove())#, reply_markup=markup)

@bot.message_handler(commands=['balance'])
def balance_message(message):
  global chat_id

  requests.get(url)

  chat_id = message.chat.id
  id = message.from_user.id
  money_count = users.find_one({'id': id})['money_gpt4']
  bot.send_message(message.chat.id, "Your balance: " + str(money_count) + " CapCoins\n\nCost of 1 image: 50 CapCoins\n\nIf you want to buy more CapCoins, contact admins: @sbsqcom", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(commands=['contact'])
def contact_message(message):

  requests.get(url)

  bot.send_message(message.chat.id, "Our telegram: @sbsqcom", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(commands=['buy'])
def buy_message(message):

  requests.get(url)

  bot.send_message(message.chat.id, "To buy more captions,  contact the admin @sbsqcom\nЧтобы купить больше описаний к картинкам, напишите админу @sbsqcom", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(commands=['help'])
def help_message_en(message):

  requests.get(url)

  bot.send_message(message.chat.id, '''
How to use this bot?

/generate to upload new picture and bot will describe it.
/balance to check how much money you have left.
/contact to contact us. 
/buy to buy more captions.

1) When /generate send image from your photo roll and bot will show keyboard. 
2) Choose language of description you want.
3) Choose style of description on keyboard.
4) You can also Custom Prompt and type max 100 characters. 
5) In Custom, you can also request bot to describe in any language possible. For example, “Describe picture in funny way in German.”
6) Get description.
7) /Generate again to upload new image.
8) You can share results with our channel by tapping “share in channel button” and admins will review it. 
9) Find channel at t.me/aivisionbotgroup''')

@bot.message_handler(commands=['help_ru'])
def help_message_ru(message):

  requests.get(url)

  bot.send_message(message.chat.id, '''
Как использовать этот бот?

/buy — чтобы купить больше описаний к картинкам, напишите админу @sbsqcom.
/generate — загрузить новую картинку, и бот ее опишет.
/balance — проверить, сколько денег у вас осталось.
/contact — связаться с нами. 

1) Когда /generate отправьте фото из вашей фото галлереи, и бот выведет клавиатуру. 
2) Выберите язык описания, который вам нужен. 
3) Выберите стиль описания на клавиатуре. 
4) Вы также можете ввести Custom Prompt (Пользовательский запрос) 
 и ввести не более 100 символов. 
5) В Custom вы также можете попросить бота описать его на любом возможном языке. Например, «Опишите картинку забавно на немецком языке». 
6) Получить описание. 
7) /generate еще раз, чтобы загрузить новое фото.
8) Вы можете поделиться результатами с нашим каналом, нажав кнопку «Share in Channel», и администраторы проверят описание.
9) Найдите канал по адресу t.me/aivisionbotgroup''')

@bot.message_handler(commands=['dataset'])
def dataset_message(message):

    requests.get(url)

    bot.send_message(message.chat.id, "To test, train or add your dataset to AI Vision Bot, reach admins at @sbsqcom")

@bot.message_handler(content_types=['photo'])
def photo_caption(message):
  global style
  global id
  global chat_id
  global base64_photo
  global photo

  requests.get(url)
  
  chat_id = message.chat.id
  id = message.from_user.id
  username = message.from_user.username
  photo = fs.put(bot.download_file(bot.get_file(message.photo[-1].file_id).file_path), content_type='image/jpeg')
  money_count = users.find_one({'id': id}).get('money_gpt4')

  
  if money_count >= 50:
    queue.insert_one({"join_time": datetime.datetime.utcnow(), "photo": photo, "chat_id": chat_id, "style": None, "lang": None, "id": id, "username": username, "money_count": money_count})
    bot.send_message(message.chat.id, "And now сhoose the language in which you want to see the description", reply_markup=markup)
  elif money_count < 50:
    bot.send_message(message.chat.id, "To buy more captions, contact the admin @sbsqcom\nЧтобы купить больше описаний к картинкам, напишите админу @sbsqcom", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['text'])
def get_text_messages(message):
  global chat_id
  global base64_photo
  global username

  requests.get(url)

  chat_id = message.chat.id
  print(chat_id)
  username = message.from_user.username

  money_count = users.find_one({'id': id}).get('money_gpt4')

  if message.text == "На русском":
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(style_humor, style_sale, style_academic, style_narrative, style_poetic, style_love, style_lana, style_rap, style_scary, style_custom, style_product)
    bot.send_message(message.chat.id, "Выберите стиль:", reply_markup=markup)
    queue.update_one({'chat_id': chat_id}, {'$set': {'lang': "rus"}})
  elif message.text == "Қазақша":
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(style_humor, style_sale, style_academic, style_narrative, style_poetic, style_love, style_lana, style_rap, style_scary, style_custom, style_product)
    bot.send_message(message.chat.id, "Стильді таңдаңыз:", reply_markup=markup)
    queue.update_one({'chat_id': chat_id}, {'$set': {'lang': "kaz"}})
  elif message.text == "In Indonesian":
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(style_humor, style_sale, style_academic, style_narrative, style_poetic, style_love, style_lana, style_rap, style_scary, style_custom, style_product)
    bot.send_message(message.chat.id, "Pilih gaya:", reply_markup=markup)
    queue.update_one({'chat_id': chat_id}, {'$set': {'lang': "ind"}})
  elif message.text == "In English":
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(style_humor, style_sale, style_academic, style_narrative, style_poetic, style_love, style_lana, style_rap, style_scary, style_custom, style_product)
    bot.send_message(message.chat.id, "Choose style:", reply_markup=markup)
    queue.update_one({'chat_id': chat_id}, {'$set': {'lang': "eng"}})

  if message.text == "Custom":
    bot.send_message(message.chat.id, "Write your prompt:\nUse max 100 characters:\nUse any language", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, custom_style)
  elif message.text == "Objects":
    style = "what type of objects are on photo"
    queue.update_one({'chat_id': chat_id}, {'$set': {'style': style}})
    add_in_queue(chat_id)

def custom_style(message):
  global style

  requests.get(url)

  style = message.text
  username = message.from_user.username
  chat_id = message.chat.id
  lang = queue.find_one({"chat_id": chat_id}).get("lang")
  money_count = users.find_one({'id': id}).get('money_gpt4')
  
  if lang == "rus":
    style = Translator(from_lang="ru", to_lang="en").translate(message.text)
  elif lang == "ind":
    style = Translator(from_lang="id", to_lang="en").translate(message.text)
  elif lang == "eng":
    style = style
  elif lang == "kaz":
    style = Translator(from_lang="kk", to_lang="en").translate(message.text)

  if len(style) > 100:
    bot.send_message(message.chat.id, "Sorry, but the length of the prompt is too long. The prompt must be no more than 100 characters. \nTry again: /generate", reply_markup=types.ReplyKeyboardRemove())
  else:
    queue.update_one({'chat_id': chat_id}, {'$set': {'style': style}})
    add_in_queue(chat_id)

def clean_up_queue():
  while True:
    threshold_time = datetime.datetime.utcnow() - datetime.timedelta(hours=1)

    incomplete_records = queue.find({
        "$or": [
            {"style": None},
            {"lang": None},
            {"join_time": {"$lt": threshold_time}}
        ]
    })
    for record in incomplete_records:
        queue.delete_one({"_id": record["_id"]})

    time.sleep(3600)


def error_notification(chat_id, message):

  requests.get(url)
  bot.send_message(chat_id, message)

def run_bot():
  while True:
      try:
          bot.polling(none_stop=True, interval=1)
      except Exception as e:
        # error_notification(chat_id, traceback.format_exc())
        print(e)
        error_notification(chat_id, "Something went wrong.\nTry again later.")

def run_app():
  app.run(host='0.0.0.0', port=8080)

bot_thread = threading.Thread(target=run_bot)
web_thread = threading.Thread(target=run_app)
generate_thread = threading.Thread(target=generate_image)
cleanup_thread = threading.Thread(target=clean_up_queue)


bot_thread.start()
web_thread.start()
generate_thread.start()
cleanup_thread.start()
