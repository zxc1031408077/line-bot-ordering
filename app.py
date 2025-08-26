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
    LocationMessage, LocationAction, DatetimePickerAction, StickerSendMessage
)
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
import uuid
import logging
import sqlite3
from functools import wraps
import requests
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
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

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
                  order_number TEXT UNIQUE,
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
    
    # 創用戶表
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  line_user_id TEXT UNIQUE,
                  name TEXT,
                  phone TEXT,
                  address TEXT,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # 插入示例數據
    c.execute("SELECT COUNT(*) FROM menu_categories")
    if c.fetchone()[0] == 0:
        # 添加菜單分類
        categories = [
            ('推薦餐點', '精選推薦組合', 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1),
            ('主餐', '各式主餐選擇', 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 2),
            ('副餐', '美味副餐小點', 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 3),
            ('飲料', '清涼飲品', 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 4),
            ('甜點', '甜蜜滋味', 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 5)
        ]
        
        c.executemany('INSERT INTO menu_categories (name, description, image_url, display_order) VALUES (?, ?, ?, ?)', categories)
        
        # 添加推薦餐點
        recommended_items = [
            (1, '超值全餐', '漢堡+薯條+可樂', 120, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 1, 1),
            (1, '雙人分享餐', '雙漢堡+雙薯條+雙可樂+雞塊', 220, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 1, 2),
            (1, '豪華套餐', '大漢堡+大薯+大可樂+蘋果派', 180, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 1, 3)
        ]
        
        # 添加主餐
        main_items = [
            (2, '經典牛肉堡', '100%純牛肉，搭配新鮮蔬菜', 80, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 1),
            (2, '雙層起司堡', '雙倍起司，雙倍滿足', 100, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 2),
            (2, '照燒雞腿堡', '鮮嫩多汁的雞腿肉', 85, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 3),
            (2, '素食蔬菜堡', '健康素食選擇', 75, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 4)
        ]
        
        # 添加副餐
        side_items = [
            (3, '薯條', '金黃酥脆', 50, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 1),
            (3, '洋蔥圈', '香脆可口', 60, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 2),
            (3, '雞塊(6塊)', '外酥內嫩', 65, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 3),
            (3, '沙拉', '新鮮蔬菜', 70, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 4)
        ]
        
        # 添加飲料
        drink_items = [
            (4, '可樂', '冰涼暢快', 30, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 1),
            (4, '雪碧', '清爽解渴', 30, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 2),
            (4, '紅茶', '香醇濃郁', 25, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 3),
            (4, '咖啡', '現煮咖啡', 40, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 4)
        ]
        
        # 添加甜點
        dessert_items = [
            (5, '蘋果派', '香甜可口', 45, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 1),
            (5, '巧克力聖代', '濃郁巧克力', 55, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 2),
            (5, '冰淇淋', '清涼消暑', 35, 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d', 1, 0, 3)
        ]
        
        c.executemany('INSERT INTO menu_items (category_id, name, description, price, image_url, is_available, is_recommended, display_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                     recommended_items + main_items + side_items + drink_items + dessert_items)
    
    conn.commit()
    conn.close()

# 初始化數據庫
init_db()

# 數據庫幫助函數
def get_db_connection():
    conn = sqlite3.connect('restaurant.db')
    conn.row_factory = sqlite3.Row
    return conn

# 管理員登入裝飾器
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# 生成唯一訂單編號
def generate_order_number():
    return datetime.now().strftime("%Y%m%d") + str(uuid.uuid4().int)[:6].upper()

# 獲取菜單分類
def get_menu_categories():
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM menu_categories ORDER BY display_order').fetchall()
    conn.close()
    return categories

# 獲取菜單項目
def get_menu_items(category_id=None, recommended=False):
    conn = get_db_connection()
    
    if category_id:
        items = conn.execute('''
            SELECT * FROM menu_items 
            WHERE category_id = ? AND is_available = 1 
            ORDER BY display_order
        ''', (category_id,)).fetchall()
    elif recommended:
        items = conn.execute('''
            SELECT * FROM menu_items 
            WHERE is_recommended = 1 AND is_available = 1 
            ORDER BY display_order
        ''').fetchall()
    else:
        items = conn.execute('''
            SELECT * FROM menu_items 
            WHERE is_available = 1 
            ORDER BY category_id, display_order
        ''').fetchall()
    
    conn.close()
    return items

# 獲取購物車
def get_cart(user_id):
    conn = get_db_connection()
    cart = conn.execute('''
        SELECT ci.*, mi.name, mi.price, mi.image_url 
        FROM cart_items ci 
        JOIN menu_items mi ON ci.item_id = mi.id 
        WHERE ci.user_id = ?
    ''', (user_id,)).fetchall()
    conn.close()
    return cart

# 添加到購物車
def add_to_cart_db(user_id, item_id, quantity=1):
    conn = get_db_connection()
    
    # 檢查是否已在購物車中
    existing = conn.execute('SELECT * FROM cart_items WHERE user_id = ? AND item_id = ?', (user_id, item_id)).fetchone()
    
    if existing:
        conn.execute('UPDATE cart_items SET quantity = quantity + ? WHERE user_id = ? AND item_id = ?', 
                    (quantity, user_id, item_id))
    else:
        conn.execute('INSERT INTO cart_items (user_id, item_id, quantity) VALUES (?, ?, ?)', 
                    (user_id, item_id, quantity))
    
    conn.commit()
    conn.close()

# 更新購物車項目數量
def update_cart_item_quantity(user_id, item_id, quantity):
    conn = get_db_connection()
    
    if quantity <= 0:
        conn.execute('DELETE FROM cart_items WHERE user_id = ? AND item_id = ?', (user_id, item_id))
    else:
        conn.execute('UPDATE cart_items SET quantity = ? WHERE user_id = ? AND item_id = ?', 
                    (quantity, user_id, item_id))
    
    conn.commit()
    conn.close()

# 清空購物車
def clear_cart(user_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM cart_items WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# 創建訂單
def create_order(user_id, order_data):
    conn = get_db_connection()
    order_number = generate_order_number()
    
    # 插入訂單
    conn.execute('''
        INSERT INTO orders (order_number, user_id, user_name, status, total_amount, order_type, delivery_address, phone_number, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (order_number, user_id, order_data.get('user_name'), 'pending', order_data.get('total_amount'), 
          order_data.get('order_type'), order_data.get('delivery_address'), order_data.get('phone_number'), 
          order_data.get('note')))
    
    order_id = conn.lastrowid
    
    # 插入訂單項目
    cart_items = get_cart(user_id)
    for item in cart_items:
        conn.execute('''
            INSERT INTO order_items (order_id, item_id, item_name, quantity, price)
            VALUES (?, ?, ?, ?, ?)
        ''', (order_id, item['item_id'], item['name'], item['quantity'], item['price']))
    
    # 清空購物車
    clear_cart(user_id)
    
    conn.commit()
    conn.close()
    
    return order_number

# 獲取用戶訂單
def get_user_orders(user_id, limit=5):
    conn = get_db_connection()
    orders = conn.execute('''
        SELECT * FROM orders 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (user_id, limit)).fetchall()
    conn.close()
    return orders

# 獲取訂單詳情
def get_order_details(order_id):
    conn = get_db_connection()
    order = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    items = conn.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,)).fetchall()
    conn.close()
    return order, items

# 創建快速回覆按鈕
def create_quick_reply():
    items = [
        QuickReplyButton(action=PostbackAction(label="📋 查看菜單", data="action=view_categories")),
        QuickReplyButton(action=PostbackAction(label="🛒 購物車", data="action=view_cart")),
        QuickReplyButton(action=PostbackAction(label="📦 我的訂單", data="action=view_orders")),
        QuickReplyButton(action=PostbackAction(label="ℹ️ 餐廳資訊", data="action=restaurant_info")),
        QuickReplyButton(action=PostbackAction(label="🏠 回到主頁", data="action=go_home"))
    ]
    return QuickReply(items=items)

# 創建分類選單
def create_categories_menu():
    categories = get_menu_categories()
    columns = []
    
    for category in categories:
        column = ImageCarouselColumn(
            image_url=category['image_url'],
            action=PostbackAction(
                label=category['name'],
                data=f"action=view_menu&category_id={category['id']}"
            )
        )
        columns.append(column)
    
    return TemplateSendMessage(
        alt_text="菜單分類",
        template=ImageCarouselTemplate(columns=columns)
    )

# 創建菜單項目Flex訊息
def create_menu_flex_message(category_id=None, recommended=False):
    if recommended:
        items = get_menu_items(recommended=True)
        title = "推薦餐點"
    else:
        items = get_menu_items(category_id=category_id)
        category = get_menu_categories()[category_id-1] if category_id else None
        title = category['name'] if category else "菜單"
    
    bubbles = []
    
    for item in items:
        bubble = BubbleContainer(
            size="micro",
            hero=ImageComponent(
                url=item['image_url'],
                size="full",
                aspect_mode="cover",
                aspect_ratio="1:1"
            ),
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text=item['name'],
                        weight="bold",
                        size="sm",
                        wrap=True
                    ),
                    TextComponent(
                        text=item['description'],
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
                            data=f"action=add_to_cart&item_id={item['id']}"
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
            alt_text=title,
            contents=carousel
        )
        flex_messages.append(flex_message)
    
    return flex_messages

# 創建購物車Flex訊息
def create_cart_flex(user_id):
    cart_items = get_cart(user_id)
    
    if not cart_items:
        return TextSendMessage(
            text="🛒 您的購物車是空的",
            quick_reply=create_quick_reply()
        )
    
    total = 0
    items_text = ""
    
    for idx, item in enumerate(cart_items, 1):
        item_total = item['price'] * item['quantity']
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
                        label="✅ 結帳",
                        data="action=checkout"
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

# 創建結帳確認Flex訊息
def create_checkout_flex(user_id):
    cart_items = get_cart(user_id)
    
    if not cart_items:
        return None
        
    total = 0
    items_text = ""
    
    for idx, item in enumerate(cart_items, 1):
        item_total = item['price'] * item['quantity']
        total += item_total
        items_text += f"{item['name']} x{item['quantity']} - ${item_total}\n"
    
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
                            text="訂單內容:",
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
                        data="action=confirm_payment"
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

# 創建訂單Flex訊息
def create_order_flex(order):
    items_text = ""
    total = 0
    
    order_items = get_order_details(order['id'])[1]
    for item in order_items:
        item_total = item['price'] * item['quantity']
        total += item_total
        items_text += f"{item['item_name']} x{item['quantity']} - ${item_total}\n"
    
    status_text = {
        'pending': '待確認',
        'confirmed': '已確認',
        'preparing': '準備中',
        'ready': '已完成',
        'cancelled': '已取消'
    }.get(order['status'], '未知狀態')
    
    created_time = datetime.strptime(order['created_at'], '%Y-%m-%d %H:%M:%S').strftime("%m/%d %H:%M")
    
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
                            text=f"${total}",
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
    
    return bubble

# 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip().lower()
    
    if text == "點餐" or text == "menu":
        reply_message = create_categories_menu()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text == "購物車" or text == "cart":
        reply_message = create_cart_flex(user_id)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text == "訂單" or text == "orders":
        view_orders(event, user_id)
        
    elif text == "推薦" or text == "recommended":
        menu_messages = create_menu_flex_message(recommended=True)
        if menu_messages:
            line_bot_api.reply_message(event.reply_token, menu_messages[0])
            for msg in menu_messages[1:]:
                line_bot_api.push_message(user_id, msg)
        
    elif text == "幫助" or text == "help":
        help_message = TextSendMessage(
            text="""歡迎使用美食點餐系統！
            
指令說明：
- 點餐：查看菜單
- 購物車：查看購物車
- 訂單：查看我的訂單
- 推薦：查看推薦餐點
- 幫助：顯示此幫助訊息
            
您也可以使用下方的快速按鈕進行操作。""",
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, help_message)
        
    else:
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
        category_id = data_dict.get('category_id', '')
        menu_messages = create_menu_flex_message(category_id=category_id)
        if menu_messages:
            line_bot_api.reply_message(event.reply_token, menu_messages[0])
            for msg in menu_messages[1:]:
                line_bot_api.push_message(user_id, msg)
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="找不到該菜單分類")
            )
            
    elif action == 'add_to_cart':
        item_id = data_dict.get('item_id', '')
        add_to_cart_db(user_id, item_id)
        
        # 獲取商品名稱
        conn = get_db_connection()
        item = conn.execute('SELECT name FROM menu_items WHERE id = ?', (item_id,)).fetchone()
        conn.close()
        
        item_name = item['name'] if item else "商品"
        
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
        
    elif action == 'view_cart':
        reply_message = create_cart_flex(user_id)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'checkout':
        reply_message = create_checkout_flex(user_id)
        if reply_message:
            line_bot_api.reply_message(event.reply_token, reply_message)
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="您的購物車是空的，無法結帳",
                    quick_reply=create_quick_reply()
                )
            )
            
    elif action == 'confirm_payment':
        # 這裡可以整合金流服務
        cart_items = get_cart(user_id)
        total = sum(item['price'] * item['quantity'] for item in cart_items)
        
        order_data = {
            'total_amount': total,
            'order_type': 'pickup',  # 預設為自取
            'user_name': '顧客'  # 可從用戶資料獲取
        }
        
        order_number = create_order(user_id, order_data)
        
        reply_text = f"✅ 訂單已確認！\n\n"
        reply_text += f"訂單編號: {order_number}\n"
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
        
    elif action == 'view_orders':
        view_orders(event, user_id)
        
    elif action == 'restaurant_info':
        info_message = TextSendMessage(
            text="""🍔 美味餐廳資訊 🍔

📍 地址：台北市信義區美食街123號
📞 電話：02-1234-5678
🕒 營業時間：10:00 - 22:00

提供內用、外帶、外送服務
滿$300可外送，詳情請洽店內""",
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, info_message)
        
    elif action == 'go_home':
        welcome_message = TextSendMessage(
            text="歡迎使用美食點餐系統！請選擇您需要的服務：",
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, welcome_message)

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
        bubbles.append(create_order_flex(order))
    
    flex_message = FlexSendMessage(
        alt_text="我的訂單",
        contents={
            "type": "carousel",
            "contents": bubbles
        }
    )
    
    line_bot_api.reply_message(event.reply_token, flex_message)

# 首頁
@app.route("/")
def index():
    categories = get_menu_categories()
    recommended_items = get_menu_items(recommended=True)
    return render_template("index.html", categories=categories, recommended_items=recommended_items)

# 管理員登入
@app.route("/admin/login", methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error="密碼錯誤")
    
    return render_template('admin_login.html')

# 管理員儀表板
@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    
    # 獲取訂單統計
    orders_count = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
    pending_orders = conn.execute('SELECT COUNT(*) FROM orders WHERE status = "pending"').fetchone()[0]
    total_revenue = conn.execute('SELECT SUM(total_amount) FROM orders WHERE status = "ready"').fetchone()[0] or 0
    
    # 獲取最近訂單
    recent_orders = conn.execute('''
        SELECT o.*, COUNT(oi.id) as item_count 
        FROM orders o 
        LEFT JOIN order_items oi ON o.id = oi.order_id 
        GROUP BY o.id 
        ORDER BY o.created_at DESC 
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         orders_count=orders_count, 
                         pending_orders=pending_orders,
                         total_revenue=total_revenue,
                         orders=recent_orders)

# 訂單管理
@app.route("/admin/orders")
@admin_required
def admin_orders():
    status = request.args.get('status', 'all')
    
    conn = get_db_connection()
    
    if status == 'all':
        orders = conn.execute('''
            SELECT o.*, COUNT(oi.id) as item_count 
            FROM orders o 
            LEFT JOIN order_items oi ON o.id = oi.order_id 
            GROUP BY o.id 
            ORDER BY o.created_at DESC
        ''').fetchall()
    else:
        orders = conn.execute('''
            SELECT o.*, COUNT(oi.id) as item_count 
            FROM orders o 
            LEFT JOIN order_items oi ON o.id = oi.order_id 
            WHERE o.status = ?
            GROUP BY o.id 
            ORDER BY o.created_at DESC
        ''', (status,)).fetchall()
    
    conn.close()
    
    return render_template('admin_orders.html', orders=orders, status=status)

# 更新訂單狀態
@app.route("/admin/order/<int:order_id>/update", methods=['POST'])
@admin_required
def update_order_status(order_id):
    new_status = request.form.get('status')
    
    conn = get_db_connection()
    conn.execute('UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (new_status, order_id))
    conn.commit()
    conn.close()
    
    return redirect(request.referrer or url_for('admin_orders'))

# 菜單管理
@app.route("/admin/menu")
@admin_required
def admin_menu():
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM menu_categories ORDER BY display_order').fetchall()
    items = conn.execute('''
        SELECT mi.*, mc.name as category_name 
        FROM menu_items mi 
        JOIN menu_categories mc ON mi.category_id = mc.id 
        ORDER BY mc.display_order, mi.display_order
    ''').fetchall()
    conn.close()
    
    return render_template('admin_menu.html', categories=categories, items=items)

# 編輯菜單項目
@app.route("/admin/menu/item/<int:item_id>/edit", methods=['GET', 'POST'])
@admin_required
def edit_menu_item(item_id):
    conn = get_db_connection()
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        is_available = 1 if request.form.get('is_available') else 0
        is_recommended = 1 if request.form.get('is_recommended') else 0
        display_order = request.form.get('display_order')
        
        conn.execute('''
            UPDATE menu_items 
            SET name = ?, description = ?, price = ?, is_available = ?, is_recommended = ?, display_order = ?
            WHERE id = ?
        ''', (name, description, price, is_available, is_recommended, display_order, item_id))
        conn.commit()
        
        conn.close()
        return redirect(url_for('admin_menu'))
    
    item = conn.execute('SELECT * FROM menu_items WHERE id = ?', (item_id,)).fetchone()
    categories = conn.execute('SELECT * FROM menu_categories ORDER BY display_order').fetchall()
    conn.close()
    
    return render_template('edit_menu_item.html', item=item, categories=categories)

# 新增菜單項目
@app.route("/admin/menu/item/new", methods=['GET', 'POST'])
@admin_required
def new_menu_item():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        category_id = request.form.get('category_id')
        is_available = 1 if request.form.get('is_available') else 0
        is_recommended = 1 if request.form.get('is_recommended') else 0
        display_order = request.form.get('display_order')
        image_url = request.form.get('image_url') or 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d'
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO menu_items (name, description, price, category_id, is_available, is_recommended, display_order, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, price, category_id, is_available, is_recommended, display_order, image_url))
        conn.commit()
        conn.close()
        
        return redirect(url_for('admin_menu'))
    
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM menu_categories ORDER BY display_order').fetchall()
    conn.close()
    
    return render_template('new_menu_item.html', categories=categories)

# 管理員登出
@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

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

if __name__ == "__main__":
    app.run(debug=True)
