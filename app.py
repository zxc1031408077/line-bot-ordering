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
    c.execute('''
        CREATE TABLE IF NOT EXISTS menu_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            display_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            image_url TEXT,
            is_available BOOLEAN DEFAULT 1,
            is_recommended BOOLEAN DEFAULT 0,
            display_order INTEGER DEFAULT 0,
            FOREIGN KEY (category_id) REFERENCES menu_categories (id)
        )
    ''')
    
    # 創建購物車相關表
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_carts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cart_id INTEGER,
            item_id INTEGER,
            quantity INTEGER DEFAULT 1,
            price REAL NOT NULL,
            special_instructions TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cart_id) REFERENCES user_carts (id),
            FOREIGN KEY (item_id) REFERENCES menu_items (id)
        )
    ''')
    
    # 創建訂單表
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            user_name TEXT,
            status TEXT DEFAULT 'pending',
            total_amount REAL DEFAULT 0,
            order_type TEXT DEFAULT 'pickup',
            delivery_address TEXT,
            pickup_time TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            item_id INTEGER,
            quantity INTEGER DEFAULT 1,
            price REAL NOT NULL,
            special_instructions TEXT,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (item_id) REFERENCES menu_items (id)
        )
    ''')
    
    # 創建用戶管理表
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_user_id TEXT UNIQUE NOT NULL,
            name TEXT,
            phone TEXT,
            email TEXT,
            favorite_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 創建管理員表
    c.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'staff',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 插入示例數據
    c.execute("SELECT COUNT(*) FROM menu_categories")
    if c.fetchone()[0] == 0:
        # 添加分類
        categories = [
            ("推薦餐點", "最受歡迎的餐點組合", "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38", 1),
            ("主餐", "美味主餐", "https://images.unsplash.com/photo-1551782450-a2132b4ba21d", 2),
            ("副餐", "精選副餐", "https://images.unsplash.com/photo-1573080496219-bb080dd4f877", 3),
            ("飲料", "清涼飲品", "https://images.unsplash.com/photo-1622483767028-3f66f32aef97", 4),
            ("甜點", "甜蜜享受", "https://images.unsplash.com/photo-1570197788417-0e82375c9371", 5)
        ]
        c.executemany("INSERT INTO menu_categories (name, description, image_url, display_order) VALUES (?, ?, ?, ?)", categories)
        
        # 添加菜單項目
        menu_items = [
            (1, "豪華套餐", "漢堡+薯條+可樂+甜點", 199, "https://images.unsplash.com/photo-1551782450-a2132b4ba21d", 1, 1, 1),
            (1, "雙人分享餐", "兩個漢堡+兩份薯條+兩杯飲料", 299, "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38", 1, 1, 2),
            (2, "經典牛肉漢堡", "100%澳洲牛肉，新鮮生菜，特製醬料", 120, "https://images.unsplash.com/photo-1551782450-a2132b4ba21d", 1, 0, 1),
            (2, "照燒雞腿堡", "鮮嫩雞腿肉，照燒醬，新鮮蔬菜", 110, "https://images.unsplash.com/photo-1565299507177-b0ac66763828", 1, 0, 2),
            (2, "雙層起司牛肉堡", "雙層牛肉，雙層起司，雙重享受", 150, "https://images.unsplash.com/photo-1551782450-a2132b4ba21d", 1, 1, 3),
            (3, "金黃薯條", "現切馬鈴薯，金黃酥脆", 50, "https://images.unsplash.com/photo-1573080496219-bb080dd4f877", 1, 0, 1),
            (3, "洋蔥圈", "香脆可口，洋蔥香甜", 60, "https://images.unsplash.com/photo-1633896949678-1b4f11d6f7ac", 1, 0, 2),
            (3, "雞塊（6塊）", "精選雞肉，外酥內嫩", 65, "https://images.unsplash.com/photo-1606755962773-d324e0a13086", 1, 0, 3),
            (4, "可樂", "冰涼暢快，經典口味", 30, "https://images.unsplash.com/photo-1622483767028-3f66f32aef97", 1, 0, 1),
            (4, "雪碧", "清爽解渴，檸檬風味", 30, "https://images.unsplash.com/photo-1629203851122-3726ecdf080e", 1, 0, 2),
            (4, "冰紅茶", "香醇濃郁，清涼解膩", 25, "https://images.unsplash.com/photo-1556679343-c7306c1976bc", 1, 0, 3),
            (5, "巧克力聖代", "香濃巧克力，冰淇淋，鮮奶油", 80, "https://images.unsplash.com/photo-1570197788417-0e82375c9371", 1, 1, 1),
            (5, "蘋果派", "新鮮蘋果，肉桂風味，酥脆外皮", 70, "https://images.unsplash.com/photo-1572383672419-ab35444a5c63", 1, 0, 2)
        ]
        c.executemany(
            "INSERT INTO menu_items (category_id, name, description, price, image_url, is_available, is_recommended, display_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            menu_items
        )
    
    # 創建管理員帳號
    try:
        c.execute("INSERT OR IGNORE INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
                  ('admin', generate_password_hash('admin123'), 'admin'))
        c.execute("INSERT OR IGNORE INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
                  ('staff', generate_password_hash('staff123'), 'staff'))
    except sqlite3.Error as e:
        print(f"創建管理員帳號時出錯: {e}")
    
    conn.commit()
    conn.close()

# 初始化數據庫
init_db()

# 數據庫助手函數
def get_db_connection():
    conn = sqlite3.connect('restaurant.db')
    conn.row_factory = sqlite3.Row
    return conn

# 登入裝飾器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# 獲取菜單分類
def get_menu_categories():
    conn = get_db_connection()
    categories = conn.execute(
        'SELECT * FROM menu_categories WHERE is_active = 1 ORDER BY display_order'
    ).fetchall()
    conn.close()
    return categories

# 獲取菜單項目
def get_menu_items(category_id=None, recommended=False):
    conn = get_db_connection()
    query = 'SELECT * FROM menu_items WHERE is_available = 1'
    params = []
    
    if category_id:
        query += ' AND category_id = ?'
        params.append(category_id)
    
    if recommended:
        query += ' AND is_recommended = 1'
    
    query += ' ORDER BY display_order'
    
    items = conn.execute(query, params).fetchall()
    conn.close()
    return items

# 獲取用戶購物車
def get_user_cart(user_id):
    conn = get_db_connection()
    cart = conn.execute(
        'SELECT * FROM user_carts WHERE user_id = ?',
        (user_id,)
    ).fetchone()
    
    if cart:
        cart_items = conn.execute(
            '''SELECT ci.*, mi.name, mi.price, mi.image_url 
               FROM cart_items ci 
               JOIN menu_items mi ON ci.item_id = mi.id 
               WHERE ci.cart_id = ?''',
            (cart['id'],)
        ).fetchall()
        conn.close()
        return {'cart': cart, 'items': cart_items}
    
    conn.close()
    return None

# 獲取用戶訂單
def get_user_orders(user_id, limit=5):
    conn = get_db_connection()
    orders = conn.execute(
        '''SELECT o.*, 
           GROUP_CONCAT(mi.name || ' x' || oi.quantity) as items_summary
           FROM orders o
           JOIN order_items oi ON o.id = oi.order_id
           JOIN menu_items mi ON oi.item_id = mi.id
           WHERE o.user_id = ?
           GROUP BY o.id
           ORDER BY o.created_at DESC
           LIMIT ?''',
        (user_id, limit)
    ).fetchall()
    conn.close()
    return orders

# 生成唯一訂單編號
def generate_order_number():
    return datetime.now().strftime("%Y%m%d") + str(uuid.uuid4().int)[:6].upper()

# 創建快速回覆按鈕
def create_quick_reply():
    items = [
        QuickReplyButton(action=PostbackAction(label="📋 查看菜單", data="action=view_categories")),
        QuickReplyButton(action=PostbackAction(label="🛒 購物車", data="action=view_cart")),
        QuickReplyButton(action=PostbackAction(label="📦 我的訂單", data="action=view_orders")),
        QuickReplyButton(action=PostbackAction(label="ℹ️ 餐廳資訊", data="action=restaurant_info")),
        QuickReplyButton(action=PostbackAction(label="📞 聯絡我們", data="action=contact_us"))
    ]
    return QuickReply(items=items)

# 創建分類選單
def create_categories_menu():
    categories = get_menu_categories()
    columns = []
    
    category_images = {
        1: "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38",
        2: "https://images.unsplash.com/photo-1551782450-a2132b4ba21d",
        3: "https://images.unsplash.com/photo-1573080496219-bb080dd4f877",
        4: "https://images.unsplash.com/photo-1622483767028-3f66f32aef97",
        5: "https://images.unsplash.com/photo-1570197788417-0e82375c9371"
    }
    
    for category in categories:
        image_url = category_images.get(category['id'], "https://images.unsplash.com/photo-1513104890138-7c749659a591")
        
        column = ImageCarouselColumn(
            image_url=image_url,
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

# 創建推薦菜單
def create_recommended_menu():
    recommended_items = get_menu_items(recommended=True)
    return create_menu_flex_message(recommended_items, "推薦餐點")

# 創建分類菜單
def create_category_menu(category_id):
    conn = get_db_connection()
    category = conn.execute(
        'SELECT * FROM menu_categories WHERE id = ?', (category_id,)
    ).fetchone()
    conn.close()
    
    if not category:
        return None
        
    items = get_menu_items(category_id=category_id)
    return create_menu_flex_message(items, category['name'])

# 創建菜單Flex訊息 - 改進字體大小和設計
def create_menu_flex_message(items, title):
    if not items:
        return None
    
    bubbles = []
    for item in items:
        bubble = BubbleContainer(
            size="micro",
            hero=ImageComponent(
                url=item['image_url'],
                size="full",
                aspect_mode="cover",
                aspect_ratio="1:1",
                margin="none"
            ),
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text=item['name'],
                        weight="bold",
                        size="md",  # 增大字體
                        wrap=True,
                        margin="md"
                    ),
                    TextComponent(
                        text=item['description'],
                        size="sm",  # 增大字體
                        color="#999999",
                        wrap=True,
                        margin="sm"
                    ),
                    BoxComponent(
                        layout="baseline",
                        margin="md",
                        contents=[
                            TextComponent(
                                text=f"${item['price']}",
                                size="md",  # 增大字體
                                weight="bold",
                                color="#ff6b6b",
                                flex=0
                            ),
                            TextComponent(
                                text="立即點餐" if item['is_available'] else "暫停供應",
                                size="sm",
                                color="#aaaaaa",
                                align="end",
                                flex=1
                            )
                        ]
                    )
                ],
                spacing="sm",
                paddingAll="10px"
            )
        )
        
        if item['is_available']:
            bubble.footer = BoxComponent(
                layout="vertical",
                contents=[
                    ButtonComponent(
                        style="primary",
                        color="#ff6b6b",
                        height="sm",
                        margin="md",
                        action=PostbackAction(
                            label="加入購物車",
                            data=f"action=add_to_cart&item_id={item['id']}",
                            display_text=f"已將 {item['name']} 加入購物車"
                        )
                    )
                ]
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
            alt_text=f"{title} 菜單",
            contents=carousel
        )
        flex_messages.append(flex_message)
    
    return flex_messages

# 查看購物車 - 改進設計並添加編輯功能
def view_cart(user_id):
    cart_data = get_user_cart(user_id)
    
    if not cart_data or not cart_data['items']:
        return TextSendMessage(
            text="🛒 您的購物車是空的",
            quick_reply=create_quick_reply()
        )
    
    total = 0
    items_text = ""
    
    for item in cart_data['items']:
        item_total = item['price'] * item['quantity']
        total += item_total
        items_text += f"• {item['name']} x{item['quantity']} - ${item_total}\n"
    
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="🛒 購物車內容",
                    weight="bold",
                    size="xl",
                    color="#ff6b6b",
                    margin="md"
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
                            size="md"  # 增大字體
                        ),
                        SeparatorComponent(margin="md"),
                        BoxComponent(
                            layout="baseline",
                            spacing="sm",
                            margin="md",
                            contents=[
                                TextComponent(
                                    text="總金額:",
                                    color="#aaaaaa",
                                    size="md",  # 增大字體
                                    flex=2
                                ),
                                TextComponent(
                                    text=f"${total}",
                                    size="md",  # 增大字體
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

# 編輯購物車功能
def edit_cart(user_id):
    cart_data = get_user_cart(user_id)
    
    if not cart_data or not cart_data['items']:
        return TextSendMessage(
            text="🛒 您的購物車是空的",
            quick_reply=create_quick_reply()
        )
    
    bubbles = []
    for item in cart_data['items']:
        bubble = BubbleContainer(
            size="micro",
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text=item['name'],
                        weight="bold",
                        size="md",
                        wrap=True,
                        margin="md"
                    ),
                    BoxComponent(
                        layout="baseline",
                        margin="md",
                        contents=[
                            TextComponent(
                                text=f"數量: {item['quantity']}",
                                size="sm",
                                flex=2
                            ),
                            TextComponent(
                                text=f"${item['price'] * item['quantity']}",
                                size="sm",
                                color="#ff6b6b",
                                weight="bold",
                                flex=1
                            )
                        ]
                    )
                ]
            ),
            footer=BoxComponent(
                layout="horizontal",
                spacing="sm",
                contents=[
                    ButtonComponent(
                        style="primary",
                        color="#4ecdc4",
                        height="sm",
                        action=PostbackAction(
                            label="➕",
                            data=f"action=increase_quantity&item_id={item['id']}"
                        )
                    ),
                    ButtonComponent(
                        style="primary",
                        color="#ff6b6b",
                        height="sm",
                        action=PostbackAction(
                            label="➖",
                            data=f"action=decrease_quantity&item_id={item['id']}"
                        )
                    ),
                    ButtonComponent(
                        style="primary",
                        color="#1a1a2e",
                        height="sm",
                        action=PostbackAction(
                            label="🗑️ 刪除",
                            data=f"action=remove_item&item_id={item['id']}"
                        )
                    )
                ]
            )
        )
        bubbles.append(bubble)
    
    # 添加返回按鈕
    back_bubble = BubbleContainer(
        size="micro",
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="編輯購物車",
                    weight="bold",
                    size="md",
                    color="#ff6b6b",
                    margin="md"
                )
            ]
        ),
        footer=BoxComponent(
            layout="vertical",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#ff6b6b",
                    action=PostbackAction(
                        label="⬅️ 返回購物車",
                        data="action=view_cart"
                    )
                )
            ]
        )
    )
    bubbles.append(back_bubble)
    
    flex_message = FlexSendMessage(
        alt_text="編輯購物車",
        contents={
            "type": "carousel",
            "contents": bubbles
        }
    )
    
    return flex_message

# 增加購物車商品數量
def increase_quantity(user_id, item_id):
    conn = get_db_connection()
    cart = conn.execute(
        'SELECT * FROM user_carts WHERE user_id = ?',
        (user_id,)
    ).fetchone()
    
    if cart:
        conn.execute(
            'UPDATE cart_items SET quantity = quantity + 1 WHERE cart_id = ? AND id = ?',
            (cart['id'], item_id)
        )
        conn.commit()
    
    conn.close()
    return edit_cart(user_id)

# 減少購物車商品數量
def decrease_quantity(user_id, item_id):
    conn = get_db_connection()
    cart = conn.execute(
        'SELECT * FROM user_carts WHERE user_id = ?',
        (user_id,)
    ).fetchone()
    
    if cart:
        # 獲取當前數量
        item = conn.execute(
            'SELECT * FROM cart_items WHERE cart_id = ? AND id = ?',
            (cart['id'], item_id)
        ).fetchone()
        
        if item and item['quantity'] > 1:
            conn.execute(
                'UPDATE cart_items SET quantity = quantity - 1 WHERE cart_id = ? AND id = ?',
                (cart['id'], item_id)
            )
        else:
            # 如果數量為1，直接刪除
            conn.execute(
                'DELETE FROM cart_items WHERE cart_id = ? AND id = ?',
                (cart['id'], item_id)
            )
        
        conn.commit()
    
    conn.close()
    return edit_cart(user_id)

# 刪除購物車商品
def remove_item(user_id, item_id):
    conn = get_db_connection()
    cart = conn.execute(
        'SELECT * FROM user_carts WHERE user_id = ?',
        (user_id,)
    ).fetchone()
    
    if cart:
        conn.execute(
            'DELETE FROM cart_items WHERE cart_id = ? AND id = ?',
            (cart['id'], item_id)
        )
        conn.commit()
    
    conn.close()
    return edit_cart(user_id)

# 確認訂單模板 - 改進設計
def create_order_confirmation(user_id):
    cart_data = get_user_cart(user_id)
    
    if not cart_data or not cart_data['items']:
        return None
        
    total = 0
    items_text = ""
    
    for item in cart_data['items']:
        item_total = item['price'] * item['quantity']
        total += item_total
        items_text += f"• {item['name']} x{item['quantity']} - ${item_total}\n"
    
    order_number = generate_order_number()
    
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="✅ 訂單確認",
                    weight="bold",
                    size="xl",
                    color="#ff6b6b",
                    margin="md"
                ),
                SeparatorComponent(margin="md"),
                BoxComponent(
                    layout="vertical",
                    margin="md",
                    spacing="sm",
                    contents=[
                        TextComponent(
                            text=f"訂單編號: {order_number}",
                            size="md",  # 增大字體
                            color="#555555"
                        ),
                        TextComponent(
                            text="\n訂單內容:",
                            size="md",  # 增大字體
                            weight="bold"
                        ),
                        TextComponent(
                            text=items_text,
                            wrap=True,
                            size="md"  # 增大字體
                        ),
                        SeparatorComponent(margin="md"),
                        BoxComponent(
                            layout="baseline",
                            spacing="sm",
                            margin="md",
                            contents=[
                                TextComponent(
                                    text="總金額:",
                                    color="#aaaaaa",
                                    size="md",  # 增大字體
                                    flex=2
                                ),
                                TextComponent(
                                    text=f"${total}",
                                    size="md",  # 增大字體
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
                        data=f"action=checkout&order_number={order_number}"
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

# 餐廳資訊模板 - 改進設計
def create_restaurant_info():
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="🍔 美味漢堡餐廳",
                    weight="bold",
                    size="xl",
                    color="#ff6b6b",
                    margin="md"
                ),
                SeparatorComponent(margin="md"),
                BoxComponent(
                    layout="vertical",
                    margin="md",
                    spacing="md",  # 增加間距
                    contents=[
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                IconComponent(
                                    size="md",
                                    url="https://scdn.line-apps.com/n/channel_devcenter/img/fx/review_gold_star_28.png"
                                ),
                                TextComponent(
                                    text="4.8 (1,234則評論)",
                                    size="md",  # 增大字體
                                    color="#666666",
                                    margin="md"
                                )
                            ]
                        ),
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                IconComponent(
                                    size="md",
                                    url="https://scdn.line-apps.com/n/channel_devcenter/img/fx/restaurant_32.png"
                                ),
                                TextComponent(
                                    text="美式餐廳 • 漢堡 • 快餐",
                                    size="md",  # 增大字體
                                    color="#666666",
                                    margin="md"
                                )
                            ]
                        ),
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                IconComponent(
                                    size="md",
                                    url="https://scdn.line-apps.com/n/channel_devcenter/img/fx/clock_32.png"
                                ),
                                TextComponent(
                                    text="營業時間: 11:00 - 21:00",
                                    size="md",  # 增大字體
                                    color="#666666",
                                    margin="md"
                                )
                            ]
                        ),
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                IconComponent(
                                    size="md",
                                    url="https://scdn.line-apps.com/n/channel_devcenter/img/fx/location_32.png"
                                ),
                                TextComponent(
                                    text="台北市大安區忠孝東路四段123號",
                                    size="md",  # 增大字體
                                    color="#666666",
                                    margin="md",
                                    wrap=True
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
                    action=URIAction(
                        label="📞 撥打電話",
                        uri="tel:+886212345678"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    action=URIAction(
                        label="🗺️ 查看地圖",
                        uri="https://goo.gl/maps/example"
                    )
                )
            ]
        )
    )
    
    return FlexSendMessage(
        alt_text="餐廳資訊",
        contents=bubble
    )

# 聯絡我們模板 - 改進設計
def create_contact_info():
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="📞 聯絡我們",
                    weight="bold",
                    size="xl",
                    color="#ff6b6b",
                    margin="md"
                ),
                SeparatorComponent(margin="md"),
                BoxComponent(
                    layout="vertical",
                    margin="md",
                    spacing="md",  # 增加間距
                    contents=[
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                IconComponent(
                                    size="md",
                                    url="https://scdn.line-apps.com/n/channel_devcenter/img/fx/phone_32.png"
                                ),
                                TextComponent(
                                    text="電話: 02-1234-5678",
                                    size="md",  # 增大字體
                                    color="#666666",
                                    margin="md"
                                )
                            ]
                        ),
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                IconComponent(
                                    size="md",
                                    url="https://scdn.line-apps.com/n/channel_devcenter/img/fx/email_32.png"
                                ),
                                TextComponent(
                                    text="Email: contact@burger.com",
                                    size="md",  # 增大字體
                                    color="#666666",
                                    margin="md"
                                )
                            ]
                        ),
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                IconComponent(
                                    size="md",
                                    url="https://scdn.line-apps.com/n/channel_devcenter/img/fx/clock_32.png"
                                ),
                                TextComponent(
                                    text="服務時間: 09:00 - 18:00",
                                    size="md",  # 增大字體
                                    color="#666666",
                                    margin="md"
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
                    action=URIAction(
                        label="📞 撥打電話",
                        uri="tel:+886212345678"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    action=URIAction(
                        label="📧 發送郵件",
                        uri="mailto:contact@burger.com"
                    )
                )
            ]
        )
    )
    
    return FlexSendMessage(
        alt_text="聯絡資訊",
        contents=bubble
    )

# 首頁
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
    
    if text == "點餐" or text == "menu":
        reply_message = create_categories_menu()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text == "購物車" or text == "cart":
        reply_message = view_cart(user_id)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text == "訂單" or text == "orders":
        view_orders(event, user_id)
        
    elif text == "推薦" or text == "recommended":
        menu_messages = create_recommended_menu()
        if menu_messages:
            line_bot_api.reply_message(event.reply_token, menu_messages[0])
            for msg in menu_messages[1:]:
                line_bot_api.push_message(user_id, msg)
        
    elif text == "餐廳" or text == "info":
        reply_message = create_restaurant_info()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text == "幫助" or text == "help":
        help_message = TextSendMessage(
            text="""歡迎使用美味漢堡餐廳點餐系統！
            
常用指令：
- 點餐：查看菜單分類
- 推薦：查看推薦餐點
- 購物車：查看購物車
- 訂單：查看我的訂單
- 餐廳：查看餐廳資訊
            
您也可以使用下方的快速按鈕進行操作。""",
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, help_message)
        
    else:
        welcome_message = TextSendMessage(
            text="歡迎使用美味漢堡餐廳點餐系統！請選擇您需要的服務：",
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
        category_id = data_dict.get('category_id', '')
        menu_messages = create_category_menu(category_id)
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
        add_to_cart(event, user_id, item_id)
        
    elif action == 'view_cart':
        reply_message = view_cart(user_id)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'edit_cart':
        reply_message = edit_cart(user_id)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'increase_quantity':
        item_id = data_dict.get('item_id', '')
        reply_message = increase_quantity(user_id, item_id)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'decrease_quantity':
        item_id = data_dict.get('item_id', '')
        reply_message = decrease_quantity(user_id, item_id)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'remove_item':
        item_id = data_dict.get('item_id', '')
        reply_message = remove_item(user_id, item_id)
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
        
    elif action == 'restaurant_info':
        reply_message = create_restaurant_info()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'contact_us':
        reply_message = create_contact_info()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'go_home':
        welcome_message = TextSendMessage(
            text="歡迎使用美味漢堡餐廳點餐系統！請選擇您需要的服務：",
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, welcome_message)

# 添加到購物車 - 修復問題
def add_to_cart(event, user_id, item_id):
    conn = get_db_connection()
    item = conn.execute(
        'SELECT * FROM menu_items WHERE id = ? AND is_available = 1',
        (item_id,)
    ).fetchone()
    
    if not item:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="找不到該商品或商品已暫停供應")
        )
        conn.close()
        return
    
    # 檢查用戶是否有購物車
    cart = conn.execute(
        'SELECT * FROM user_carts WHERE user_id = ?',
        (user_id,)
    ).fetchone()
    
    if not cart:
        # 創建新購物車
        conn.execute(
            'INSERT INTO user_carts (user_id) VALUES (?)',
            (user_id,)
        )
        cart_id = conn.lastrowid
    else:
        cart_id = cart['id']
    
    # 檢查商品是否已在購物車中
    cart_item = conn.execute(
        'SELECT * FROM cart_items WHERE cart_id = ? AND item_id = ?',
        (cart_id, item_id)
    ).fetchone()
    
    if cart_item:
        # 更新數量
        conn.execute(
            'UPDATE cart_items SET quantity = quantity + 1 WHERE id = ?',
            (cart_item['id'],)
        )
    else:
        # 添加新商品
        conn.execute(
            'INSERT INTO cart_items (cart_id, item_id, quantity, price) VALUES (?, ?, 1, ?)',
            (cart_id, item_id, item['price'])
        )
    
    conn.commit()
    conn.close()
    
    # 回覆添加成功訊息
    confirm_template = ConfirmTemplate(
        text=f"已將 {item['name']} 加入購物車！",
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
def checkout_order(event, user_id, order_number):
    cart_data = get_user_cart(user_id)
    
    if not cart_data or not cart_data['items']:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="您目前沒有訂單可以結帳",
                quick_reply=create_quick_reply()
            )
        )
        return
    
    # 創建訂單
    conn = get_db_connection()
    total = sum(item['price'] * item['quantity'] for item in cart_data['items'])
    
    # 創建訂單
    conn.execute(
        'INSERT INTO orders (order_number, user_id, total_amount) VALUES (?, ?, ?)',
        (order_number, user_id, total)
    )
    order_id = conn.lastrowid
    
    # 添加訂單項目
    for item in cart_data['items']:
        conn.execute(
            'INSERT INTO order_items (order_id, item_id, quantity, price) VALUES (?, ?, ?, ?)',
            (order_id, item['item_id'], item['quantity'], item['price'])
        )
    
    # 清空購物車
    conn.execute(
        'DELETE FROM cart_items WHERE cart_id = ?',
        (cart_data['cart']['id'],)
    )
    
    conn.commit()
    conn.close()
    
    # 回覆結帳成功訊息
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
        created_time = datetime.strptime(order['created_at'], '%Y-%m-%d %H:%M:%S').strftime("%m/%d %H:%M")
        status_text = {
            'pending': '待確認',
            'confirmed': '已確認',
            'preparing': '準備中',
            'ready': '已完成',
            'cancelled': '已取消'
        }.get(order['status'], '未知狀態')
        
        bubble = BubbleContainer(
            size="kilo",
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text=f"訂單 #{order['order_number']}",
                        weight="bold",
                        size="md",
                        color="#ff6b6b",
                        margin="md"
                    ),
                    TextComponent(
                        text=f"狀態: {status_text}",
                        size="md",  # 增大字體
                        color="#666666",
                        margin="sm"
                    ),
                    TextComponent(
                        text=f"時間: {created_time}",
                        size="sm",
                        color="#999999",
                        margin="sm"
                    ),
                    SeparatorComponent(margin="md"),
                    TextComponent(
                        text=order['items_summary'],
                        size="md",  # 增大字體
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
                                size="md",  # 增大字體
                                flex=2
                            ),
                            TextComponent(
                                text=f"${order['total_amount']}",
                                size="md",  # 增大字體
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

# 管理後台登入
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM admin_users WHERE username = ?', 
            (username,)
        ).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['admin_role'] = user['role']
            return redirect(url_for('admin_dashboard'))
        
        return render_template('admin_login.html', error='帳號或密碼錯誤')
    
    return render_template('admin_login.html')

# 管理後台儀表板
@app.route('/admin')
@login_required
def admin_dashboard():
    conn = get_db_connection()
    
    # 獲取訂單統計
    orders_count = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
    today_orders = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = DATE('now')"
    ).fetchone()[0]
    pending_orders = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE status = 'pending'"
    ).fetchone()[0]
    
    # 獲取最近訂單
    recent_orders = conn.execute('''
        SELECT o.*, u.name as user_name 
        FROM orders o 
        LEFT JOIN users u ON o.user_id = u.line_user_id 
        ORDER BY o.created_at DESC 
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         orders_count=orders_count,
                         today_orders=today_orders,
                         pending_orders=pending_orders,
                         recent_orders=recent_orders)

# 管理後台訂單管理
@app.route('/admin/orders')
@login_required
def admin_orders():
    conn = get_db_connection()
    orders = conn.execute('''
        SELECT o.*, u.name as user_name 
        FROM orders o 
        LEFT JOIN users u ON o.user_id = u.line_user_id 
        ORDER BY o.created_at DESC
    ''').fetchall()
    conn.close()
    
    return render_template('admin_orders.html', orders=orders)

# 管理後台菜單管理
@app.route('/admin/menu')
@login_required
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

# 管理後台登出
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    session.pop('admin_role', None)
    return redirect(url_for('admin_login'))

if __name__ == "__main__":
    app.run(debug=True, port=5001)
