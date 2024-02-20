import telebot
from telebot import types
from pymongo import MongoClient
import json
from datetime import datetime
import os

bot = telebot.TeleBot(os.environ('TELEBOT_API'))
print("Connected!")

client = MongoClient(os.environ('MONGO_KEY'))
db = client['Composter']
collection_regions = db['regions']
collection_queue = db['queue']
collection_operator = db['operator']

region_names = collection_regions.find({}, {'RegionName': 1, '_id': 0})
PLACES_OPERATORS_REGIONS = [region['RegionName'] for region in region_names]

@bot.message_handler(commands=['start'])
def start(message):
  global districts

  queue_table = collection_queue.find_one({"user_id": message.chat.id})
  if queue_table and queue_table["user_state"] != 100 and queue_table["user_state"] != 200:
    not_markup = types.InlineKeyboardMarkup()
    not_markup.add(types.InlineKeyboardButton(text="Delete last request", callback_data="queue_del"))
    not_markup.add(types.InlineKeyboardButton(text="Finish last request", callback_data="queue_con"))
    bot.send_message(message.chat.id, "You have not finished last request. Choose to finish:", reply_markup=not_markup)
  elif queue_table and queue_table["user_state"] == 0:
    collection_queue.delete_one({"user_id": message.chat.id})
    markup = types.ReplyKeyboardMarkup(row_width=3)
    for district in PLACES_OPERATORS_REGIONS:
        button = types.KeyboardButton(district)
        markup.add(button)
    
    new_document = {
      "user_name": False,
      "user_id": message.chat.id,
      "region": False,
      "operator": False,
      "operator_id": False,
      "create_time": datetime.now(),
      "message": False,
      "close_time": False,
      "user_state": 0 
      # us0 = new user
      # us13 = waiting for operator 
      # us52 = waiting for request access 
      # us100 = request accepted
      # us200 = request denied
      # us300 = compost accepted
      # us400 = compost part accepted
      # us500 = compost denied
      
    }
    collection_queue.insert_one(new_document)
    
    bot.send_message(message.chat.id, ":", reply_markup=markup)

  else:
    markup = types.ReplyKeyboardMarkup(row_width=3)
    for district in PLACES_OPERATORS_REGIONS:
        button = types.KeyboardButton(district)
        markup.add(button)

    new_document = {
      "user_name": False,
      "user_id": message.chat.id,
      "region": False,
      "operator": False,
      "operator_id": False,
      "create_time": datetime.now(),
      "message": False,
      "close_time": False,
      "user_state": 0 
      # us0 = new user
      # us13 = waiting for operator 
      # us15 = waiting for region 
      # us52 = waiting for request access 
      # us100 = request accepted
      # us200 = request denied

    }
    collection_queue.insert_one(new_document)
    bot.send_message(message.chat.id, "Choose neighborhood:", reply_markup=markup)

# @bot.message_handler(commands=['order'])
# def order(message):
#   operator_ids = []
#   for i in collection_operator.find():
#     operator_ids.append(i['username'])
   
#   if message.chat.id in operator_ids: 
#     #collection_operator.update_one({"username": operator_ids}, {'$set': {'order': text}})
#     operator_table = collection_operator.find_one({"username": message.chat.id})
#     if operator_table['orders'] == None:
#       bot.send_message(message.chat.id, "You do not have any orders")
#     else:
#       bot.send_message(message.chat.id, f"All your orders:{operator_table['orders']}") 
#   else:
#     bot.send_message(message.chat.id, "You do not have access to orders", reply_markup=markup)
  


@bot.message_handler(content_types=['text'])
def text_reception(message):
  user_id = message.chat.id
  user_text = message.text
  queue_table = collection_queue.find_one({"user_id": user_id})
  if queue_table["user_state"] == 13:
    markup = types.InlineKeyboardMarkup()
    access_button = types.InlineKeyboardButton(text="✅ Accept", callback_data=f"request_access_{message.chat.id}")
    deny_button = types.InlineKeyboardButton(text="❌ Deny", callback_data=f"request_deny_{message.chat.id}")
    answer_button = types.InlineKeyboardButton(text="Get details", callback_data=f"request_answer_{message.chat.id}")
    markup.add(access_button, deny_button, answer_button)


   
    collection_queue.update_one({"user_id": user_id}, {'$set': {"message": user_text}})
    bot.send_message(queue_table["operator_id"], f"<a href='tg://user?id={user_id}'>User</a>: {user_text}", reply_markup=markup, parse_mode='HTML')
    bot.send_message(user_id, "Wait for operator...")
    collection_queue.update_one({"user_id": message.chat.id}, {'$set': {"user_state": 52}})
  else:
    if message.text in PLACES_OPERATORS_REGIONS:
        collection_queue.update_one({"user_id": message.chat.id}, {'$set': {"user_state": 15}})
        region_choice(message, message.text)

def region_choice(message, region_name):
    response = f"You chose: {region_name}."
    collection_queue.update_one({"user_id": message.chat.id}, {'$set': {'region': region_name}})
  
    bot.send_message(chat_id=message.chat.id, text=response, reply_markup=types.ReplyKeyboardRemove())
    markup = types.InlineKeyboardMarkup()
    response = "Choose operator in region {region_name}:\n"

    operators_documents = collection_regions.find({"RegionName": region_name}, {'_id': 0})
    operators = []
    for document in operators_documents:
      for key, value in document.items():
        if key.startswith('operator_') and 'id' not in key and value not in operators:
          operators.append(value)

    for operator in operators:
        button_text = f"Choose {operator}"
        callback_data = f"select_{operator}_{region_name}"
        button = types.InlineKeyboardButton(text=button_text, callback_data=callback_data)
        markup.add(button)

    bot.send_message(message.chat.id, response.format(region_name=region_name), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('request_'))
def select_action(call):
  action = call.data.split('_')[1]
  user_id = int(call.data.split('_')[2])
  operator_id = collection_queue.find_one({"user_id": user_id})["operator_id"]

  if action == 'access':
    accessed(user_id)
    bot.delete_message(operator_id, call.message.message_id)
  elif action == 'deny':
    denied(user_id)
    bot.delete_message(operator_id, call.message.message_id)

def accessed(user_id):
  document = collection_queue.find_one({"user_id": user_id})
  operator = collection_queue.find_one({"user_id": user_id})["operator"]
  operator_id = collection_queue.find_one({"user_id": user_id})["operator_id"]
  collection_queue.update_one({"user_id": user_id}, {'$set': {'user_state': 100, 'close_time': datetime.now()}})
  zakidoperatoru(document['message'], operator_id)
  
  bot.send_message(user_id, f"✅ Your order accepted\nText <a href='tg://user?id={operator_id}'>{operator}</a> if you have more questions", parse_mode='HTML')

def zakidoperatoru(text, operator_id):
  collection_operator.update_one({"username":     operator_id}, {'$set': {'orders': f"\n{text}"}})

def denied(user_id):
  denied_markup = types.InlineKeyboardMarkup()
  deny_button1 = types.InlineKeyboardButton(text="Reason 1", callback_data=f"denied_1_{user_id}")
  deny_button2 = types.InlineKeyboardButton(text="Reason 2", callback_data=f"denied_2_{user_id}")
  deny_button3 = types.InlineKeyboardButton(text="Reason 3", callback_data=f"denied_3_{user_id}")
  deny_button4 = types.InlineKeyboardButton(text="Reason 4", callback_data=f"denied_4_{user_id}")
  denied_markup.add(deny_button1, deny_button2, deny_button3, deny_button4)
  operator_id = collection_queue.find_one({"user_id": user_id})["operator_id"]
  bot.send_message(operator_id, f"Mention the reason of deny:", reply_markup=denied_markup)
  collection_queue.update_one({"user_id": user_id}, {'$set': {'user_state': 200, 'close_time': datetime.now()}})

@bot.callback_query_handler(func=lambda call: call.data.startswith('denied_'))
def denied_callback(call):
  reasons = ["Reason 1", "Reason 2", "Reason 3", "Reason 4"]
  reason = int(call.data.split('_')[1])-1
  user_id = int(call.data.split('_')[2])
  bot.send_message(user_id, f"Your request was denied.\nReason: {reasons[reason]}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def callback_query_handler(call):
  user_id = call.message.chat.id
  queue_table = collection_queue.find_one({"user_id": user_id})
  operator = call.data.split('_')[1]
  region_name = call.data.split('_')[2]
  address = get_operator_information(user_id, region_name, operator)[0]
  operator_id = get_operator_information(user_id, region_name, operator)[1]
  telegram_username = get_operator_information(user_id, region_name, operator)[2]
  
  bot.delete_message(user_id, call.message.message_id)
  
  bot.send_message(user_id, f"Describe type and quantity of compost to operator: ({operator}) with address ({address}):", parse_mode='HTML')
  get_user_state(user_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('queue_'))
def select_action_queue(call):
  action = call.data.split('_')[1]
  user_id = call.message.chat.id
  queue_table = collection_queue.find_one({"user_id": user_id})
  if action == "con":
    bot.delete_message(user_id, call.message.message_id)
    if queue_table["user_state"] == 15:
      region_choice(call.message, queue_table["region"])
    elif queue_table["user_state"] == 13:
      bot.send_message(user_id, f"Describe type and quantity of compost to operator: ({queue_table['operator']}) with address ({get_operator_information(user_id, queue_table['region'], queue_table['operator'])[0]}):", parse_mode='HTML')
  elif action == "del":
    collection_queue.delete_one({"user_id": user_id})
    bot.delete_message(user_id, call.message.message_id)
    start(call.message)
  

def get_operator_information(user_id, region_name, operator):
  operators_documents = collection_regions.find({"RegionName": region_name})

  address = ""
  operator_id = ""
  telegram_username = ""

  for doc in operators_documents:
    operator_key = None
    for key, value in doc.items():
        if key.startswith('operator_') and value == operator:
            operator_key = key
            break

    if operator_key:
      address = doc.get('address_' + operator_key.split('_')[1])
      telegram_username = doc.get('telegram_username_' + operator_key.split('_')[1])
      operator_id = doc.get('operator_id_' + operator_key.split('_')[1])

  collection_queue.update_one({"user_id": user_id}, {'$set': {'operator': operator, "operator_id": operator_id, "user_state": 13}})
  return [address, operator_id, telegram_username]

def get_user_state(user_id):
  user_state = collection_queue.find_one({"user_id": user_id})["user_state"]
  return user_state

if __name__ == "__main__":
  bot.polling(none_stop=True)
