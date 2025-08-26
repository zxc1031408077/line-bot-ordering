from flask import Flask, request, abort, render_template, session
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, 
    TemplateSendMessage, ButtonsTemplate, PostbackAction, 
    PostbackEvent, QuickReply, QuickReplyButton,
    CarouselTemplate, CarouselColumn, URIAction
)
import os
from dotenv import load_dotenv
import json
from datetime import datetime

# 載入環境變數
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret_key")

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 完整菜單
MENU = {
    "主餐": {
        "經典漢堡": 120,
        "雙層起司堡": 150,
        "照燒雞腿堡": 130,
        "素食蔬菜堡": 110
    },
    "副餐": {
        "薯條": 50,
        "洋蔥圈": 60,
        "沙拉": 70,
        "玉米湯": 40
    },
    "飲料": {
        "可樂": 30,
        "雪碧": 30,
        "紅茶": 25,
        "咖啡": 40
    }
}

# 訂單狀態
ORDER_STATUS = {
    "pending": "待確認",
    "preparing": "準備中",
    "ready": "已完成",
    "cancelled": "已取消"
}

# 用戶訂單記錄
orders = {}

# 生成快速回覆按鈕
def create_quick_reply():
    items = [
        QuickReplyButton(action=PostbackAction(label="查看菜單", data="action=view_menu")),
        QuickReplyButton(action=PostbackAction(label="我的訂單", data="action=view_order")),
        QuickReplyButton(action=PostbackAction(label="結帳", data="action=checkout")),
        QuickReplyButton(action=PostbackAction(label="取消訂單", data="action=cancel_order"))
    ]
    return QuickReply(items=items)

# 生成分類菜單
def create_category_menu():
    carousel_columns = []
    
    for category, items in MENU.items():
        actions = []
        for name, price in items.items():
            actions.append(PostbackAction(
                label=f"{name} - ${price}",
                data=f"action=add&item={name}&price={price}"
            ))
        
        # 每列最多只能有3個動作
        if len(actions) > 3:
            actions = actions[:3]
            
        column = CarouselColumn(
            title=category,
            text="選擇您喜歡的餐點",
            actions=actions
        )
        carousel_columns.append(column)
    
    return TemplateSendMessage(
        alt_text="菜單",
        template=CarouselTemplate(columns=carousel_columns)
    )

# 首頁
@app.route("/")
def index():
    return render_template("index.html", menu=MENU)

# LINE Webhook
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip().lower()
    
    if text == "點餐":
        # 發送分類菜單
        reply_message = create_category_menu()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text == "查看菜單":
        reply_message = create_category_menu()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text == "我的訂單":
        view_order(event, user_id)
        
    elif text == "結帳":
        checkout_order(event, user_id)
        
    elif text == "取消訂單":
        cancel_order(event, user_id)
        
    else:
        # 預設回覆
        welcome_message = TextSendMessage(
            text="歡迎使用美味點餐系統！請選擇您需要的服務：",
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, welcome_message)

# 處理按鈕點選
@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    
    # 解析數據
    data_dict = {}
    for item in data.split('&'):
        key, value = item.split('=')
        data_dict[key] = value
    
    action = data_dict.get('action', '')
    
    if action == 'add':
        item = data_dict.get('item', '')
        price = int(data_dict.get('price', 0))
        add_to_order(event, user_id, item, price)
        
    elif action == 'view_menu':
        reply_message = create_category_menu()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'view_order':
        view_order(event, user_id)
        
    elif action == 'checkout':
        checkout_order(event, user_id)
        
    elif action == 'cancel_order':
        cancel_order(event, user_id)

# 添加到訂單
def add_to_order(event, user_id, item, price):
    if user_id not in orders:
        orders[user_id] = {
            "items": [],
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    orders[user_id]["items"].append({"name": item, "price": price})
    
    total = sum(item["price"] for item in orders[user_id]["items"])
    
    reply_text = f"已加入 {item} 到您的訂單\n\n目前訂單內容：\n"
    for idx, item in enumerate(orders[user_id]["items"], 1):
        reply_text += f"{idx}. {item['name']} - ${item['price']}\n"
    
    reply_text += f"\n總金額：${total}\n\n請選擇下一步操作："
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text=reply_text,
            quick_reply=create_quick_reply()
        )
    )

# 查看訂單
def view_order(event, user_id):
    if user_id not in orders or not orders[user_id]["items"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="您目前沒有訂單",
                quick_reply=create_quick_reply()
            )
        )
        return
    
    order = orders[user_id]
    reply_text = "您的訂單內容：\n\n"
    
    for idx, item in enumerate(order["items"], 1):
        reply_text += f"{idx}. {item['name']} - ${item['price']}\n"
    
    total = sum(item["price"] for item in order["items"])
    status = ORDER_STATUS.get(order["status"], "未知狀態")
    
    reply_text += f"\n總金額：${total}\n"
    reply_text += f"訂單狀態：{status}\n"
    reply_text += f"建立時間：{order['created_at']}\n\n"
    reply_text += "請選擇下一步操作："
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text=reply_text,
            quick_reply=create_quick_reply()
        )
    )

# 結帳
def checkout_order(event, user_id):
    if user_id not in orders or not orders[user_id]["items"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="您目前沒有訂單可以結帳",
                quick_reply=create_quick_reply()
            )
        )
        return
    
    order = orders[user_id]
    total = sum(item["price"] for item in order["items"])
    
    # 這裡可以整合金流服務，目前先模擬結帳成功
    order["status"] = "preparing"
    
    reply_text = "結帳成功！\n\n"
    reply_text += "訂單詳情：\n"
    
    for idx, item in enumerate(order["items"], 1):
        reply_text += f"{idx}. {item['name']} - ${item['price']}\n"
    
    reply_text += f"\n總金額：${total}\n"
    reply_text += "我們將開始準備您的餐點，請稍候。\n"
    reply_text += "感謝您的訂購！"
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# 取消訂單
def cancel_order(event, user_id):
    if user_id not in orders or not orders[user_id]["items"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="您目前沒有訂單可以取消",
                quick_reply=create_quick_reply()
            )
        )
        return
    
    order = orders[user_id]
    order["status"] = "cancelled"
    
    reply_text = "您的訂單已取消\n\n"
    reply_text += "已取消的訂單內容：\n"
    
    for idx, item in enumerate(order["items"], 1):
        reply_text += f"{idx}. {item['name']} - ${item['price']}\n"
    
    total = sum(item["price"] for item in order["items"])
    reply_text += f"\n總金額：${total}\n"
    reply_text += "期待再次為您服務！"
    
    # 清空訂單
    orders[user_id]["items"] = []
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    app.run(debug=True)
