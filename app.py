from flask import Flask, request, abort, render_template
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, ButtonsTemplate, PostbackAction, PostbackEvent
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 預設菜單
MENU = {
    "漢堡": 100,
    "薯條": 50,
    "可樂": 30
}

# 用戶訂單記錄 (簡單示範，部署後可改用 DB)
orders = {}

# 首頁
@app.route("/")
def index():
    return render_template("index.html")

# LINE Webhook
@app.route("/callback", methods=['GET', 'POST'])
def callback():
    if request.method == 'GET':
        return "OK", 200  # 給 LINE 驗證用
    
    # POST 的情況才處理 LINE 的訊息
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
    text = event.message.text

    if text == "點餐":
        buttons_template = ButtonsTemplate(
            title="菜單",
            text="請選擇餐點",
            actions=[PostbackAction(label=f"{name} {price}元", data=name) for name, price in MENU.items()]
        )
        template_message = TemplateSendMessage(
            alt_text="菜單",
            template=buttons_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="輸入「點餐」開始點餐"))

# 處理按鈕點選
@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    item = event.postback.data

    if user_id not in orders:
        orders[user_id] = []
    orders[user_id].append(item)

    total = sum(MENU[i] for i in orders[user_id])
    order_list = ", ".join(orders[user_id])

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"已加入 {item} 到你的訂單\n目前訂單：{order_list}\n總金額：{total}元\n輸入「點餐」繼續點餐"))
