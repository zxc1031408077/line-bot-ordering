from flask import Flask, request, abort, render_template, session, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, 
    TemplateSendMessage, ButtonsTemplate, PostbackAction, 
    PostbackEvent, QuickReply, QuickReplyButton,
    CarouselTemplate, CarouselColumn, URIAction,
    FlexSendMessage, BubbleContainer, BoxComponent, TextComponent,
    ButtonComponent, SeparatorComponent, IconComponent, ImageCarouselTemplate,
    ImageCarouselColumn, ConfirmTemplate, MessageAction
)
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
import uuid
import logging

# 載入環境變數
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret_key")

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 完整菜單數據
MENU = {
    "recommended": {
        "id": "recommended",
        "name": "推薦餐點",
        "items": {
            "1號餐": {"name": "1號餐", "price": 120, "desc": "漢堡+薯條+可樂", "image": "https://example.com/combo1.jpg"},
            "2號餐": {"name": "2號餐", "price": 150, "desc": "雙層漢堡+薯條+紅茶", "image": "https://example.com/combo2.jpg"},
            "3號餐": {"name": "3號餐", "price": 180, "desc": "雞腿堡+雞塊+雪碧", "image": "https://example.com/combo3.jpg"}
        }
    },
    "main": {
        "id": "main",
        "name": "主餐",
        "items": {
            "經典漢堡": {"name": "經典漢堡", "price": 70, "desc": "100%純牛肉", "image": "https://example.com/burger.jpg"},
            "雙層起司堡": {"name": "雙層起司堡", "price": 90, "desc": "雙倍起司雙倍滿足", "image": "https://example.com/double-cheese.jpg"},
            "照燒雞腿堡": {"name": "照燒雞腿堡", "price": 85, "desc": "鮮嫩多汁的雞腿肉", "image": "https://example.com/chicken.jpg"},
            "素食蔬菜堡": {"name": "素食蔬菜堡", "price": 75, "desc": "健康素食選擇", "image": "https://example.com/veggie.jpg"}
        }
    },
    "side": {
        "id": "side",
        "name": "副餐",
        "items": {
            "薯條": {"name": "薯條", "price": 50, "desc": "金黃酥脆", "image": "https://example.com/fries.jpg"},
            "洋蔥圈": {"name": "洋蔥圈", "price": 60, "desc": "香脆可口", "image": "https://example.com/onion-rings.jpg"},
            "雞塊": {"name": "雞塊", "price": 65, "desc": "6塊裝", "image": "https://example.com/nuggets.jpg"},
            "沙拉": {"name": "沙拉", "price": 70, "desc": "新鮮蔬菜", "image": "https://example.com/salad.jpg"}
        }
    },
    "drink": {
        "id": "drink",
        "name": "飲料",
        "items": {
            "可樂": {"name": "可樂", "price": 30, "desc": "冰涼暢快", "image": "https://example.com/cola.jpg"},
            "雪碧": {"name": "雪碧", "price": 30, "desc": "清爽解渴", "image": "https://example.com/sprite.jpg"},
            "紅茶": {"name": "紅茶", "price": 25, "desc": "香醇濃郁", "image": "https://example.com/tea.jpg"},
            "咖啡": {"name": "咖啡", "price": 40, "desc": "現煮咖啡", "image": "https://example.com/coffee.jpg"}
        }
    }
}

# 訂單狀態
ORDER_STATUS = {
    "cart": "購物車",
    "pending": "待確認",
    "confirmed": "已確認",
    "preparing": "準備中",
    "ready": "已完成",
    "cancelled": "已取消"
}

# 用戶數據存儲 (實際應用中應使用數據庫)
user_carts = {}
user_orders = {}

# 生成唯一訂單ID
def generate_order_id():
    return datetime.now().strftime("%Y%m%d") + str(uuid.uuid4().int)[:6]

# 創建快速回覆按鈕
def create_quick_reply():
    items = [
        QuickReplyButton(action=PostbackAction(label="📋 查看菜單", data="action=view_categories")),
        QuickReplyButton(action=PostbackAction(label="🛒 我的購物車", data="action=view_cart")),
        QuickReplyButton(action=PostbackAction(label="📦 我的訂單", data="action=view_orders")),
        QuickReplyButton(action=PostbackAction(label="🏠 回到主頁", data="action=go_home"))
    ]
    return QuickReply(items=items)

# 創建分類選單
def create_categories_menu():
    columns = []
    
    categories = [
        {"id": "recommended", "name": "推薦餐點", "image": "https://example.com/combo.jpg"},
        {"id": "main", "name": "主餐", "image": "https://example.com/main.jpg"},
        {"id": "side", "name": "副餐", "image": "https://example.com/side.jpg"},
        {"id": "drink", "name": "飲料", "image": "https://example.com/drink.jpg"}
    ]
    
    for category in categories:
        column = ImageCarouselColumn(
            image_url=category["image"],
            action=PostbackAction(
                label=category["name"],
                data=f"action=view_menu&category={category['id']}"
            )
        )
        columns.append(column)
    
    return TemplateSendMessage(
        alt_text="菜單分類",
        template=ImageCarouselTemplate(columns=columns)
    )

# 創建分類菜單
def create_menu_template(category_id):
    if category_id not in MENU:
        return None
        
    category = MENU[category_id]
    columns = []
    
    # 將商品分組，每組最多10個
    items = list(category["items"].values())
    for i in range(0, len(items), 10):
        category_items = items[i:i+10]
        
        bubbles = []
        for item in category_items:
            bubble = BubbleContainer(
                size="micro",
                hero=BoxComponent(
                    layout="vertical",
                    contents=[
                        ImageComponent(
                            url=item["image"],
                            size="full",
                            aspect_mode="cover",
                            aspect_ratio="1:1"
                        )
                    ]
                ),
                body=BoxComponent(
                    layout="vertical",
                    contents=[
                        TextComponent(
                            text=item["name"],
                            weight="bold",
                            size="sm",
                            wrap=True
                        ),
                        TextComponent(
                            text=item["desc"],
                            size="xs",
                            color="#999999",
                            wrap=True
                        ),
                        TextComponent(
                            text=f"${item['price']}",
                            size="sm",
                            weight="bold",
                            color="#ff6b6b"
                        )
                    ],
                    spacing="sm",
                    paddingAll="10px"
                ),
                footer=BoxComponent(
                    layout="vertical",
                    contents=[
                        ButtonComponent(
                            style="primary",
                            color="#ff6b6b",
                            height="sm",
                            action=PostbackAction(
                                label="加入購物車",
                                data=f"action=add_to_cart&category={category_id}&item={item['name']}"
                            )
                        )
                    ]
                )
            )
            bubbles.append(bubble)
        
        # 創建Flex訊息
        flex_message = FlexSendMessage(
            alt_text=f"{category['name']} 菜單",
            contents={
                "type": "carousel",
                "contents": bubbles
            }
        )
        columns.append(flex_message)
    
    return columns

# 查看購物車
def view_cart(user_id):
    if user_id not in user_carts or not user_carts[user_id]["items"]:
        return TextSendMessage(
            text="🛒 您的購物車是空的",
            quick_reply=create_quick_reply()
        )
    
    cart = user_carts[user_id]
    total = 0
    items_text = ""
    
    for idx, item in enumerate(cart["items"], 1):
        item_total = item["price"] * item["quantity"]
        total += item_total
        items_text += f"{idx}. {item['name']} x{item['quantity']} - ${item_total}\n"
    
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="🛒 購物車內容",
                    weight="bold",
                    size="xl",
                    color="#ff6b6b"
                ),
                SeparatorComponent(margin="md"),
                BoxComponent(
                    layout="vertical",
                    margin="md",
                    spacing="sm",
                    contents=[
                        TextComponent(
                            text=items_text,
                            wrap=True,
                            size="md"
                        ),
                        SeparatorComponent(margin="md"),
                        BoxComponent(
                            layout="baseline",
                            spacing="sm",
                            contents=[
                                TextComponent(
                                    text="總金額:",
                                    color="#aaaaaa",
                                    size="md",
                                    flex=2
                                ),
                                TextComponent(
                                    text=f"${total}",
                                    size="md",
                                    color="#111111",
                                    weight="bold",
                                    flex=1
                                )
                            ]
                        )
                    ]
                )
            ]
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="sm",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#ff6b6b",
                    action=PostbackAction(
                        label="✅ 確認訂單",
                        data="action=confirm_order"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    action=PostbackAction(
                        label="✏️ 編輯購物車",
                        data="action=edit_cart"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    action=PostbackAction(
                        label="⬅️ 繼續點餐",
                        data="action=view_categories"
                    )
                )
            ]
        )
    )
    
    return FlexSendMessage(
        alt_text="購物車內容",
        contents=bubble
    )

# 確認訂單模板
def create_order_confirmation(user_id):
    if user_id not in user_carts or not user_carts[user_id]["items"]:
        return None
        
    cart = user_carts[user_id]
    total = 0
    items_text = ""
    
    for idx, item in enumerate(cart["items"], 1):
        item_total = item["price"] * item["quantity"]
        total += item_total
        items_text += f"{item['name']} x{item['quantity']} - ${item_total}\n"
    
    order_id = generate_order_id()
    
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="✅ 訂單確認",
                    weight="bold",
                    size="xl",
                    color="#ff6b6b"
                ),
                SeparatorComponent(margin="md"),
                BoxComponent(
                    layout="vertical",
                    margin="md",
                    spacing="sm",
                    contents=[
                        TextComponent(
                            text=f"訂單編號: {order_id}",
                            size="sm",
                            color="#555555"
                        ),
                        TextComponent(
                            text="\n訂單內容:",
                            size="md",
                            weight="bold"
                        ),
                        TextComponent(
                            text=items_text,
                            wrap=True,
                            size="md"
                        ),
                        SeparatorComponent(margin="md"),
                        BoxComponent(
                            layout="baseline",
                            spacing="sm",
                            contents=[
                                TextComponent(
                                    text="總金額:",
                                    color="#aaaaaa",
                                    size="md",
                                    flex=2
                                ),
                                TextComponent(
                                    text=f"${total}",
                                    size="md",
                                    color="#111111",
                                    weight="bold",
                                    flex=1
                                )
                            ]
                        )
                    ]
                )
            ]
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="sm",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#ff6b6b",
                    action=PostbackAction(
                        label="💳 確認付款",
                        data=f"action=checkout&order_id={order_id}"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    action=PostbackAction(
                        label="✏️ 修改訂單",
                        data="action=edit_cart"
                    )
                )
            ]
        )
    )
    
    return FlexSendMessage(
        alt_text="訂單確認",
        contents=bubble
    )

# 首頁
@app.route("/")
def index():
    return render_template("index.html", menu=MENU)

# 管理後台
@app.route("/admin")
def admin():
    # 這裡應該有身份驗證
    return render_template("admin.html", orders=user_orders)

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
    
    if text == "點餐" or text == "menu":
        # 發送分類菜單
        reply_message = create_categories_menu()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text == "購物車" or text == "cart":
        reply_message = view_cart(user_id)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text == "訂單" or text == "orders":
        view_orders(event, user_id)
        
    elif text == "幫助" or text == "help":
        help_message = TextSendMessage(
            text="""歡迎使用美食點餐系統！
            
指令說明：
- 點餐：查看菜單
- 購物車：查看購物車
- 訂單：查看我的訂單
- 幫助：顯示此幫助訊息
            
您也可以使用下方的快速按鈕進行操作。""",
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, help_message)
        
    else:
        # 預設回覆
        welcome_message = TextSendMessage(
            text="歡迎使用美食點餐系統！請選擇您需要的服務：",
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
        if '=' in item:
            key, value = item.split('=', 1)
            data_dict[key] = value
    
    action = data_dict.get('action', '')
    
    if action == 'view_categories':
        reply_message = create_categories_menu()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'view_menu':
        category_id = data_dict.get('category', '')
        menu_messages = create_menu_template(category_id)
        if menu_messages:
            line_bot_api.reply_message(event.reply_token, menu_messages)
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="找不到該菜單分類")
            )
            
    elif action == 'add_to_cart':
        category_id = data_dict.get('category', '')
        item_name = data_dict.get('item', '')
        add_to_cart(event, user_id, category_id, item_name)
        
    elif action == 'view_cart':
        reply_message = view_cart(user_id)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'confirm_order':
        reply_message = create_order_confirmation(user_id)
        if reply_message:
            line_bot_api.reply_message(event.reply_token, reply_message)
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="您的購物車是空的，無法建立訂單",
                    quick_reply=create_quick_reply()
                )
            )
            
    elif action == 'checkout':
        order_id = data_dict.get('order_id', '')
        checkout_order(event, user_id, order_id)
        
    elif action == 'view_orders':
        view_orders(event, user_id)
        
    elif action == 'go_home':
        welcome_message = TextSendMessage(
            text="歡迎使用美食點餐系統！請選擇您需要的服務：",
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, welcome_message)

# 添加到購物車
def add_to_cart(event, user_id, category_id, item_name):
    if category_id not in MENU or item_name not in MENU[category_id]["items"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="找不到該商品")
        )
        return
    
    # 初始化用戶購物車
    if user_id not in user_carts:
        user_carts[user_id] = {
            "items": [],
            "updated_at": datetime.now().isoformat()
        }
    
    # 檢查商品是否已在購物車中
    item_data = MENU[category_id]["items"][item_name]
    cart = user_carts[user_id]
    
    item_found = False
    for item in cart["items"]:
        if item["name"] == item_name:
            item["quantity"] += 1
            item_found = True
            break
    
    # 如果商品不在購物車中，添加它
    if not item_found:
        cart["items"].append({
            "name": item_name,
            "price": item_data["price"],
            "quantity": 1,
            "category": category_id
        })
    
    cart["updated_at"] = datetime.now().isoformat()
    
    # 回覆添加成功訊息
    confirm_template = ConfirmTemplate(
        text=f"已將 {item_name} 加入購物車！",
        actions=[
            PostbackAction(label="查看購物車", data="action=view_cart"),
            PostbackAction(label="繼續點餐", data="action=view_categories")
        ]
    )
    
    template_message = TemplateSendMessage(
        alt_text="已加入購物車",
        template=confirm_template
    )
    
    line_bot_api.reply_message(event.reply_token, template_message)

# 結帳
def checkout_order(event, user_id, order_id):
    if user_id not in user_carts or not user_carts[user_id]["items"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="您目前沒有訂單可以結帳",
                quick_reply=create_quick_reply()
            )
        )
        return
    
    # 創建訂單
    cart = user_carts[user_id]
    total = sum(item["price"] * item["quantity"] for item in cart["items"])
    
    if user_id not in user_orders:
        user_orders[user_id] = []
    
    order = {
        "id": order_id,
        "user_id": user_id,
        "items": cart["items"].copy(),
        "total": total,
        "status": "confirmed",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    user_orders[user_id].append(order)
    
    # 清空購物車
    user_carts[user_id]["items"] = []
    
    # 回覆結帳成功訊息
    reply_text = f"✅ 訂單已確認！\n\n"
    reply_text += f"訂單編號: {order_id}\n"
    reply_text += f"總金額: ${total}\n\n"
    reply_text += "我們將開始準備您的餐點，請稍候。\n"
    reply_text += "感謝您的訂購！"
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text=reply_text,
            quick_reply=create_quick_reply()
        )
    )

# 查看訂單
def view_orders(event, user_id):
    if user_id not in user_orders or not user_orders[user_id]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="您目前沒有訂單",
                quick_reply=create_quick_reply()
            )
        )
        return
    
    orders = user_orders[user_id]
    bubbles = []
    
    for order in orders[-5:]:  # 顯示最近5筆訂單
        items_text = ""
        for item in order["items"]:
            items_text += f"{item['name']} x{item['quantity']}\n"
        
        status_text = ORDER_STATUS.get(order["status"], "未知狀態")
        created_time = datetime.fromisoformat(order["created_at"]).strftime("%m/%d %H:%M")
        
        bubble = BubbleContainer(
            size="kilo",
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text=f"訂單 #{order['id']}",
                        weight="bold",
                        size="md",
                        color="#ff6b6b"
                    ),
                    TextComponent(
                        text=f"狀態: {status_text}",
                        size="sm",
                        color="#666666",
                        margin="sm"
                    ),
                    TextComponent(
                        text=f"時間: {created_time}",
                        size="xs",
                        color="#999999",
                        margin="sm"
                    ),
                    SeparatorComponent(margin="md"),
                    TextComponent(
                        text=items_text,
                        size="sm",
                        margin="md",
                        wrap=True
                    ),
                    SeparatorComponent(margin="md"),
                    BoxComponent(
                        layout="baseline",
                        contents=[
                            TextComponent(
                                text="總金額:",
                                color="#aaaaaa",
                                size="sm",
                                flex=2
                            ),
                            TextComponent(
                                text=f"${order['total']}",
                                size="sm",
                                color="#111111",
                                weight="bold",
                                flex=1
                            )
                        ]
                    )
                ]
            )
        )
        bubbles.append(bubble)
    
    flex_message = FlexSendMessage(
        alt_text="我的訂單",
        contents={
            "type": "carousel",
            "contents": bubbles
        }
    )
    
    line_bot_api.reply_message(event.reply_token, flex_message)

if __name__ == "__main__":
    app.run(debug=True)
