from flask import Flask, request, abort, render_template, session, jsonify, redirect, url_for
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, 
    TemplateSendMessage, ButtonsTemplate, PostbackAction, 
    PostbackEvent, QuickReply, QuickReplyButton,
    CarouselTemplate, CarouselColumn, URIAction,
    FlexSendMessage, BubbleContainer, BoxComponent, TextComponent,
    ButtonComponent, SeparatorComponent, IconComponent, ImageCarouselTemplate,
    ImageCarouselColumn, ConfirmTemplate, MessageAction, ImageComponent,
    LocationMessage, LocationAction, DatetimePickerAction
)
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
import uuid
import logging
import requests
from functools import wraps
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

# 載入環境變數
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret_key")
app.config['TEMPLATES_AUTO_RELOAD'] = True

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 初始化數據庫
def init_db():
    conn = sqlite3.connect('restaurant.db')
    c = conn.cursor()
    
    # 創建菜單表
    c.execute('''CREATE TABLE IF NOT EXISTS menu_categories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  description TEXT,
                  image_url TEXT,
                  display_order INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS menu_items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  category_id INTEGER,
                  name TEXT NOT NULL,
                  description TEXT,
                  price REAL NOT NULL,
                  image_url TEXT,
                  is_available BOOLEAN DEFAULT 1,
                  is_recommended BOOLEAN DEFAULT 0,
                  display_order INTEGER,
                  FOREIGN KEY (category_id) REFERENCES menu_categories (id))''')
    
    # 創建訂單表
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  order_number TEXT UNIQUE NOT NULL,
                  user_id TEXT NOT NULL,
                  user_name TEXT,
                  status TEXT DEFAULT 'pending',
                  total_amount REAL,
                  order_type TEXT DEFAULT 'pickup',
                  delivery_address TEXT,
                  phone_number TEXT,
                  note TEXT,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS order_items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  order_id INTEGER,
                  item_id INTEGER,
                  item_name TEXT,
                  quantity INTEGER,
                  price REAL,
                  FOREIGN KEY (order_id) REFERENCES orders (id))''')
    
    # 創用戶管理表
    c.execute('''CREATE TABLE IF NOT EXISTS admin_users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  role TEXT DEFAULT 'staff')''')
    
    # 插入默認管理員帳號 (username: admin, password: admin123)
    try:
        c.execute("INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
                  ('admin', generate_password_hash('admin123'), 'admin'))
    except sqlite3.IntegrityError:
        pass  # 用戶已存在
    
    conn.commit()
    conn.close()

# 初始化數據庫
init_db()

# 數據庫連接函數
def get_db_connection():
    conn = sqlite3.connect('restaurant.db')
    conn.row_factory = sqlite3.Row
    return conn

# 管理員登入裝飾器
def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# 菜單數據 - 從數據庫加載
def get_menu_data():
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM menu_categories ORDER BY display_order').fetchall()
    
    menu = {}
    for category in categories:
        items = conn.execute(
            'SELECT * FROM menu_items WHERE category_id = ? AND is_available = 1 ORDER BY display_order',
            (category['id'],)
        ).fetchall()
        
        category_items = {}
        for item in items:
            category_items[item['name']] = {
                'id': item['id'],
                'name': item['name'],
                'price': item['price'],
                'desc': item['description'],
                'image': item['image_url'] or f"https://via.placeholder.com/300x200/4ECDC4/FFFFFF?text={item['name']}"
            }
        
        menu[category['name']] = {
            'id': category['id'],
            'name': category['name'],
            'items': category_items
        }
    
    conn.close()
    return menu

# 獲取推薦商品
def get_recommended_items():
    conn = get_db_connection()
    items = conn.execute(
        'SELECT * FROM menu_items WHERE is_recommended = 1 AND is_available = 1 ORDER BY display_order'
    ).fetchall()
    
    recommended = {}
    for item in items:
        recommended[item['name']] = {
            'id': item['id'],
            'name': item['name'],
            'price': item['price'],
            'desc': item['description'],
            'image': item['image_url'] or f"https://via.placeholder.com/300x200/FF6B6B/FFFFFF?text={item['name']}"
        }
    
    conn.close()
    return recommended

# 訂單狀態
ORDER_STATUS = {
    "pending": "待確認",
    "confirmed": "已確認",
    "preparing": "準備中",
    "ready": "已完成",
    "cancelled": "已取消",
    "delivered": "已送達"
}

# 用戶購物車 (實際應用中應使用數據庫或Redis)
user_carts = {}
user_locations = {}
user_profiles = {}

# 生成唯一訂單ID
def generate_order_number():
    return datetime.now().strftime("%Y%m%d") + str(uuid.uuid4().int)[:6]

# 創建快速回覆按鈕
def create_quick_reply():
    items = [
        QuickReplyButton(action=PostbackAction(label="📋 查看菜單", data="action=view_categories")),
        QuickReplyButton(action=PostbackAction(label="🛒 購物車", data="action=view_cart")),
        QuickReplyButton(action=PostbackAction(label="📍 提供位置", data="action=request_location")),
        QuickReplyButton(action=PostbackAction(label="📞 聯絡我們", data="action=contact_us")),
        QuickReplyButton(action=PostbackAction(label="ℹ️ 幫助", data="action=help"))
    ]
    return QuickReply(items=items)

# 創建分類選單
def create_categories_menu():
    menu_data = get_menu_data()
    columns = []
    
    # 添加推薦分類
    recommended_items = get_recommended_items()
    if recommended_items:
        columns.append(ImageCarouselColumn(
            image_url="https://via.placeholder.com/1024x1024/FF6B6B/FFFFFF?text=推薦餐點",
            action=PostbackAction(
                label="推薦餐點",
                data="action=view_menu&category=推薦餐點"
            )
        ))
    
    # 添加其他分類
    for category_name in menu_data:
        if category_name != "推薦餐點":  # 已經單獨處理
            columns.append(ImageCarouselColumn(
                image_url=f"https://via.placeholder.com/1024x1024/4ECDC4/FFFFFF?text={category_name}",
                action=PostbackAction(
                    label=category_name,
                    data=f"action=view_menu&category={category_name}"
                )
            ))
    
    return TemplateSendMessage(
        alt_text="菜單分類",
        template=ImageCarouselTemplate(columns=columns)
    )

# 創建分類菜單
def create_menu_template(category_name):
    menu_data = get_menu_data()
    
    if category_name not in menu_data:
        # 檢查是否是推薦餐點
        if category_name == "推薦餐點":
            items = get_recommended_items()
            if items:
                return create_flex_carousel("推薦餐點", items)
        return None
        
    category = menu_data[category_name]
    return create_flex_carousel(category_name, category['items'])

# 創建Flex輪播消息
def create_flex_carousel(category_name, items):
    bubbles = []
    
    for item_name, item_data in items.items():
        bubble = BubbleContainer(
            size="micro",
            hero=ImageComponent(
                url=item_data["image"],
                size="full",
                aspect_mode="cover",
                aspect_ratio="1:1"
            ),
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text=item_data["name"],
                        weight="bold",
                        size="sm",
                        wrap=True
                    ),
                    TextComponent(
                        text=item_data["desc"],
                        size="xs",
                        color="#999999",
                        wrap=True
                    ),
                    BoxComponent(
                        layout="baseline",
                        spacing="sm",
                        contents=[
                            TextComponent(
                                text="$",
                                size="sm",
                                color="#ff6b6b",
                                flex=0
                            ),
                            TextComponent(
                                text=f"{item_data['price']}",
                                size="sm",
                                color="#ff6b6b",
                                weight="bold",
                                flex=0
                            )
                        ]
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
                            data=f"action=add_to_cart&item={item_name}&price={item_data['price']}&category={category_name}"
                        )
                    )
                ]
            )
        )
        bubbles.append(bubble)
    
    # 將商品分成每10個一組 (LINE限制)
    flex_messages = []
    for i in range(0, len(bubbles), 10):
        carousel = {
            "type": "carousel",
            "contents": bubbles[i:i+10]
        }
        
        flex_message = FlexSendMessage(
            alt_text=f"{category_name} 菜單",
            contents=carousel
        )
        flex_messages.append(flex_message)
    
    return flex_messages

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
    
    order_number = generate_order_number()
    
    # 獲取用戶位置信息
    location_text = "未提供位置信息"
    if user_id in user_locations:
        loc = user_locations[user_id]
        location_text = f"{loc['address']} (地圖)"
    
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
                            text=f"訂單編號: {order_number}",
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
                        TextComponent(
                            text=f"送餐地址: {location_text}",
                            size="sm",
                            wrap=True,
                            margin="md"
                        ),
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
                        label="💳 確認下單",
                        data=f"action=checkout&order_number={order_number}"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    action=PostbackAction(
                        label="✏️ 修改訂單",
                        data="action=edit_cart"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    action=URIAction(
                        label="📍 修改送餐地址",
                        uri="line://nv/location"
                    )
                )
            ]
        )
    )
    
    return FlexSendMessage(
        alt_text="訂單確認",
        contents=bubble
    )

# 保存訂單到數據庫
def save_order_to_db(user_id, order_number, cart, order_type="delivery", address="", phone="", note=""):
    conn = get_db_connection()
    total = sum(item["price"] * item["quantity"] for item in cart["items"])
    
    # 獲取用戶名稱
    user_name = user_profiles.get(user_id, {}).get('display_name', '未知用戶')
    
    # 插入訂單
    conn.execute(
        '''INSERT INTO orders 
           (order_number, user_id, user_name, status, total_amount, order_type, delivery_address, phone_number, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (order_number, user_id, user_name, 'pending', total, order_type, address, phone, note)
    )
    
    # 獲取剛插入的訂單ID
    order_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    
    # 插入訂單項目
    for item in cart["items"]:
        conn.execute(
            '''INSERT INTO order_items (order_id, item_id, item_name, quantity, price)
               VALUES (?, ?, ?, ?, ?)''',
            (order_id, item.get('id', 0), item['name'], item['quantity'], item['price'])
        )
    
    conn.commit()
    conn.close()
    
    return order_id

# 獲取用戶訂單
def get_user_orders(user_id, limit=5):
    conn = get_db_connection()
    orders = conn.execute(
        '''SELECT * FROM orders 
           WHERE user_id = ? 
           ORDER BY created_at DESC 
           LIMIT ?''',
        (user_id, limit)
    ).fetchall()
    
    result = []
    for order in orders:
        order_items = conn.execute(
            '''SELECT * FROM order_items WHERE order_id = ?''',
            (order['id'],)
        ).fetchall()
        
        items_list = []
        for item in order_items:
            items_list.append({
                'name': item['item_name'],
                'quantity': item['quantity'],
                'price': item['price']
            })
        
        result.append({
            'id': order['id'],
            'order_number': order['order_number'],
            'status': order['status'],
            'total': order['total_amount'],
            'created_at': order['created_at'],
            'items': items_list
        })
    
    conn.close()
    return result

# 主頁
@app.route("/")
def index():
    return render_template("index.html")

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
    
    # 保存用戶信息
    if user_id not in user_profiles:
        try:
            profile = line_bot_api.get_profile(user_id)
            user_profiles[user_id] = {
                'display_name': profile.display_name,
                'picture_url': profile.picture_url,
                'status_message': profile.status_message
            }
        except Exception as e:
            logger.error(f"獲取用戶信息失敗: {e}")
            user_profiles[user_id] = {'display_name': '用戶'}
    
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
            text="""🍔 美食點餐系統幫助 🍔

主要指令:
- 點餐: 瀏覽菜單並開始點餐
- 購物車: 查看當前購物車內容
- 訂單: 查看您的歷史訂單
- 幫助: 顯示此幫助訊息

您也可以使用下方的快速按鈕進行操作。

如有任何問題，請聯繫我們的客服人員。""",
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, help_message)
        
    else:
        # 預設回覆
        welcome_message = TextSendMessage(
            text="🍔 歡迎使用美食點餐系統！請選擇您需要的服務：",
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, welcome_message)

# 處理位置訊息
@handler.add(MessageEvent, message=LocationMessage)
def handle_location(event):
    user_id = event.source.user_id
    latitude = event.message.latitude
    longitude = event.message.longitude
    address = event.message.address
    
    # 保存用戶位置
    user_locations[user_id] = {
        'latitude': latitude,
        'longitude': longitude,
        'address': address
    }
    
    # 回覆確認訊息
    confirm_message = TextSendMessage(
        text=f"📍 已收到您的送餐位置: {address}",
        quick_reply=create_quick_reply()
    )
    
    line_bot_api.reply_message(event.reply_token, confirm_message)

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
        category_name = data_dict.get('category', '')
        menu_messages = create_menu_template(category_name)
        if menu_messages:
            # 如果有多個Flex訊息，需要逐個發送
            if len(menu_messages) > 1:
                line_bot_api.reply_message(event.reply_token, menu_messages[0])
                for msg in menu_messages[1:]:
                    line_bot_api.push_message(user_id, msg)
            else:
                line_bot_api.reply_message(event.reply_token, menu_messages[0])
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="找不到該菜單分類")
            )
            
    elif action == 'add_to_cart':
        item_name = data_dict.get('item', '')
        price = float(data_dict.get('price', 0))
        category_name = data_dict.get('category', '')
        add_to_cart(event, user_id, item_name, price, category_name)
        
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
        order_number = data_dict.get('order_number', '')
        checkout_order(event, user_id, order_number)
        
    elif action == 'view_orders':
        view_orders(event, user_id)
        
    elif action == 'request_location':
        request_location(event, user_id)
        
    elif action == 'contact_us':
        contact_us(event)
        
    elif action == 'help':
        help_message = TextSendMessage(
            text="""🍔 美食點餐系統幫助 🍔

主要指令:
- 點餐: 瀏覽菜單並開始點餐
- 購物車: 查看當前購物車內容
- 訂單: 查看您的歷史訂單
- 幫助: 顯示此幫助訊息

您也可以使用下方的快速按鈕進行操作。

如有任何問題，請聯繫我們的客服人員。""",
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, help_message)

# 添加到購物車
def add_to_cart(event, user_id, item_name, price, category_name):
    # 初始化用戶購物車
    if user_id not in user_carts:
        user_carts[user_id] = {
            "items": [],
            "updated_at": datetime.now().isoformat()
        }
    
    # 檢查商品是否已在購物車中
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
            "price": price,
            "quantity": 1,
            "category": category_name
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

# 請求位置信息
def request_location(event, user_id):
    location_message = TemplateSendMessage(
        alt_text="請求位置信息",
        template=ButtonsTemplate(
            text="請分享您的位置，以便我們為您送餐",
            actions=[
                LocationAction(label="分享位置")
            ]
        )
    )
    
    line_bot_api.reply_message(event.reply_token, location_message)

# 聯絡我們
def contact_us(event):
    contact_text = """📞 聯絡我們

營業時間: 10:00 - 22:00
電話: 02-1234-5678
地址: 台北市信義區松壽路12號

如有任何問題，歡迎隨時聯繫我們！"""
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=contact_text)
    )

# 結帳
def checkout_order(event, user_id, order_number):
    if user_id not in user_carts or not user_carts[user_id]["items"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="您目前沒有訂單可以結帳",
                quick_reply=create_quick_reply()
            )
        )
        return
    
    # 檢查是否有送餐地址
    if user_id not in user_locations:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="請先提供送餐位置再下單",
                quick_reply=create_quick_reply()
            )
        )
        return
    
    # 創建訂單
    cart = user_carts[user_id]
    location = user_locations[user_id]
    
    # 保存訂單到數據庫
    save_order_to_db(
        user_id, 
        order_number, 
        cart, 
        "delivery", 
        location['address']
    )
    
    # 清空購物車
    user_carts[user_id]["items"] = []
    
    # 回覆結帳成功訊息
    reply_text = f"✅ 訂單已確認！\n\n"
    reply_text += f"訂單編號: {order_number}\n"
    reply_text += f"送餐地址: {location['address']}\n"
    reply_text += f"預計送達時間: { (datetime.now() + timedelta(minutes=40)).strftime('%H:%M') }\n\n"
    reply_text += "我們將開始準備您的餐點，請保持手機暢通。\n"
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
    orders = get_user_orders(user_id)
    
    if not orders:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="您目前沒有訂單",
                quick_reply=create_quick_reply()
            )
        )
        return
    
    bubbles = []
    
    for order in orders:
        items_text = ""
        for item in order['items']:
            items_text += f"{item['name']} x{item['quantity']}\n"
        
        status_text = ORDER_STATUS.get(order['status'], "未知狀態")
        created_time = datetime.strptime(order['created_at'], "%Y-%m-%d %H:%M:%S").strftime("%m/%d %H:%M")
        
        bubble = BubbleContainer(
            size="kilo",
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text=f"訂單 #{order['order_number']}",
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

# 管理員登入頁面
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM admin_users WHERE username = ?', (username,)
        ).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['admin_role'] = user['role']
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error='帳號或密碼錯誤')
    
    return render_template('admin_login.html')

# 管理員儀表板
@app.route('/admin')
@admin_login_required
def admin_dashboard():
    conn = get_db_connection()
    
    # 獲取訂單統計
    today = datetime.now().strftime("%Y-%m-%d")
    orders_today = conn.execute(
        "SELECT COUNT(*) as count FROM orders WHERE DATE(created_at) = ?", (today,)
    ).fetchone()['count']
    
    total_orders = conn.execute("SELECT COUNT(*) as count FROM orders").fetchone()['count']
    pending_orders = conn.execute(
        "SELECT COUNT(*) as count FROM orders WHERE status = 'pending'"
    ).fetchone()['count']
    
    # 獲取最近訂單
    recent_orders = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         orders_today=orders_today,
                         total_orders=total_orders,
                         pending_orders=pending_orders,
                         recent_orders=recent_orders)

# 訂單管理
@app.route('/admin/orders')
@admin_login_required
def admin_orders():
    status = request.args.get('status', 'all')
    
    conn = get_db_connection()
    
    if status == 'all':
        orders = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC"
        ).fetchall()
    else:
        orders = conn.execute(
            "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC",
            (status,)
        ).fetchall()
    
    conn.close()
    
    return render_template('admin_orders.html', orders=orders, status=status)

# 菜單管理
@app.route('/admin/menu')
@admin_login_required
def admin_menu():
    conn = get_db_connection()
    categories = conn.execute("SELECT * FROM menu_categories ORDER BY display_order").fetchall()
    items = conn.execute(
        """SELECT mi.*, mc.name as category_name 
           FROM menu_items mi 
           JOIN menu_categories mc ON mi.category_id = mc.id 
           ORDER BY mc.display_order, mi.display_order"""
    ).fetchall()
    conn.close()
    
    return render_template('admin_menu.html', categories=categories, items=items)

# 管理員登出
@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
