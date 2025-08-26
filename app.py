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
    ImageCarouselColumn, ConfirmTemplate, MessageAction, ImageComponent,
    SpacerComponent, FillerComponent
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

# 完整菜單數據 - 使用更高質量的圖片
MENU = {
    "recommended": {
        "id": "recommended",
        "name": "🌟 推薦餐點",
        "emoji": "⭐",
        "color": "#FF6B6B",
        "items": {
            "1號餐": {"name": "1號餐", "price": 120, "desc": "🍔 經典漢堡 + 🍟 薯條 + 🥤 可樂", "image": "https://images.unsplash.com/photo-1571091718767-18b5b1457add?w=800&h=600&fit=crop", "tag": "熱賣"},
            "2號餐": {"name": "2號餐", "price": 150, "desc": "🍔 雙層漢堡 + 🍟 薯條 + 🧋 紅茶", "image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=800&h=600&fit=crop", "tag": "推薦"},
            "3號餐": {"name": "3號餐", "price": 180, "desc": "🍗 雞腿堡 + 🍗 雞塊 + 🥤 雪碧", "image": "https://images.unsplash.com/photo-1606755962773-d324e9a13086?w=800&h=600&fit=crop", "tag": "新品"}
        }
    },
    "main": {
        "id": "main",
        "name": "🍔 主餐",
        "emoji": "🍔",
        "color": "#4ECDC4",
        "items": {
            "經典漢堡": {"name": "經典漢堡", "price": 70, "desc": "🥩 100%純牛肉餅", "image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=800&h=600&fit=crop"},
            "雙層起司堡": {"name": "雙層起司堡", "price": 90, "desc": "🧀 雙倍起司雙倍滿足", "image": "https://images.unsplash.com/photo-1571091718767-18b5b1457add?w=800&h=600&fit=crop"},
            "照燒雞腿堡": {"name": "照燒雞腿堡", "price": 85, "desc": "🍗 鮮嫩多汁的雞腿肉", "image": "https://images.unsplash.com/photo-1606755962773-d324e9a13086?w=800&h=600&fit=crop"},
            "素食蔬菜堡": {"name": "素食蔬菜堡", "price": 75, "desc": "🥬 健康素食選擇", "image": "https://images.unsplash.com/photo-1525059696034-4967a729002e?w=800&h=600&fit=crop"}
        }
    },
    "side": {
        "id": "side",
        "name": "🍟 副餐",
        "emoji": "🍟",
        "color": "#45B7D1",
        "items": {
            "薯條": {"name": "薯條", "price": 50, "desc": "✨ 金黃酥脆", "image": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800&h=600&fit=crop"},
            "洋蔥圈": {"name": "洋蔥圈", "price": 60, "desc": "🧅 香脆可口", "image": "https://images.unsplash.com/photo-1639744211804-c58bc2ec7530?w=800&h=600&fit=crop"},
            "雞塊": {"name": "雞塊", "price": 65, "desc": "🍗 6塊裝", "image": "https://images.unsplash.com/photo-1562967914-608f82629710?w=800&h=600&fit=crop"},
            "沙拉": {"name": "沙拉", "price": 70, "desc": "🥗 新鮮蔬菜", "image": "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=800&h=600&fit=crop"}
        }
    },
    "drink": {
        "id": "drink",
        "name": "🥤 飲料",
        "emoji": "🥤",
        "color": "#96CEB4",
        "items": {
            "可樂": {"name": "可樂", "price": 30, "desc": "🧊 冰涼暢快", "image": "https://images.unsplash.com/photo-1581636625402-29b2a704ef13?w=800&h=600&fit=crop"},
            "雪碧": {"name": "雪碧", "price": 30, "desc": "🍋 清爽解渴", "image": "https://images.unsplash.com/photo-1625772452859-1c03d5bf1137?w=800&h=600&fit=crop"},
            "紅茶": {"name": "紅茶", "price": 25, "desc": "🧋 香醇濃郁", "image": "https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=800&h=600&fit=crop"},
            "咖啡": {"name": "咖啡", "price": 40, "desc": "☕ 現煮咖啡", "image": "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=800&h=600&fit=crop"}
        }
    }
}

# 訂單狀態
ORDER_STATUS = {
    "cart": "🛒 購物車",
    "pending": "⏳ 待確認",
    "confirmed": "✅ 已確認",
    "preparing": "👨‍🍳 準備中",
    "ready": "🎉 已完成",
    "cancelled": "❌ 已取消"
}

# 用戶數據存儲
user_carts = {}
user_orders = {}

def generate_order_id():
    return datetime.now().strftime("%Y%m%d") + str(uuid.uuid4().int)[:6]

# 創建現代化快速回覆按鈕
def create_quick_reply():
    items = [
        QuickReplyButton(action=PostbackAction(label="🍽️ 查看菜單", data="action=view_categories")),
        QuickReplyButton(action=PostbackAction(label="🛒 購物車", data="action=view_cart")),
        QuickReplyButton(action=PostbackAction(label="📦 訂單", data="action=view_orders")),
        QuickReplyButton(action=PostbackAction(label="🏠 首頁", data="action=go_home"))
    ]
    return QuickReply(items=items)

# 創建美觀的歡迎訊息
def create_welcome_message():
    bubble = BubbleContainer(
        size="giga",
        hero=ImageComponent(
            url="https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=1200&h=400&fit=crop",
            size="full",
            aspect_ratio="3:1",
            aspect_mode="cover"
        ),
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="🍽️ 美食點餐系統",
                    weight="bold",
                    size="xl",
                    color="#2C3E50",
                    align="center"
                ),
                TextComponent(
                    text="歡迎來到我們的餐廳！",
                    size="md",
                    color="#7F8C8D",
                    align="center",
                    margin="sm"
                ),
                SeparatorComponent(margin="lg"),
                BoxComponent(
                    layout="vertical",
                    margin="lg",
                    spacing="md",
                    contents=[
                        BoxComponent(
                            layout="horizontal",
                            contents=[
                                IconComponent(url="https://cdn-icons-png.flaticon.com/512/562/562678.png", size="sm"),
                                TextComponent(
                                    text="精選美味餐點",
                                    size="sm",
                                    color="#34495E",
                                    margin="sm",
                                    flex=0
                                )
                            ]
                        ),
                        BoxComponent(
                            layout="horizontal",
                            contents=[
                                IconComponent(url="https://cdn-icons-png.flaticon.com/512/3081/3081559.png", size="sm"),
                                TextComponent(
                                    text="快速便捷點餐",
                                    size="sm",
                                    color="#34495E",
                                    margin="sm",
                                    flex=0
                                )
                            ]
                        ),
                        BoxComponent(
                            layout="horizontal",
                            contents=[
                                IconComponent(url="https://cdn-icons-png.flaticon.com/512/2343/2343627.png", size="sm"),
                                TextComponent(
                                    text="新鮮食材製作",
                                    size="sm",
                                    color="#34495E",
                                    margin="sm",
                                    flex=0
                                )
                            ]
                        )
                    ]
                )
            ]
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="md",
            contents=[
                ButtonComponent(
                    style="primary",
                    height="md",
                    color="#E74C3C",
                    action=PostbackAction(
                        label="🍽️ 開始點餐",
                        data="action=view_categories"
                    )
                ),
                BoxComponent(
                    layout="horizontal",
                    spacing="sm",
                    contents=[
                        ButtonComponent(
                            style="secondary",
                            height="sm",
                            flex=1,
                            action=PostbackAction(
                                label="🛒 購物車",
                                data="action=view_cart"
                            )
                        ),
                        ButtonComponent(
                            style="secondary",
                            height="sm",
                            flex=1,
                            action=PostbackAction(
                                label="📦 訂單",
                                data="action=view_orders"
                            )
                        )
                    ]
                )
            ]
        )
    )
    
    return FlexSendMessage(alt_text="歡迎使用美食點餐系統", contents=bubble)

# 創建現代化分類選單
def create_categories_menu():
    bubbles = []
    
    for category_id, category in MENU.items():
        gradient_colors = {
            "recommended": ["#FF6B6B", "#FF5252"],
            "main": ["#4ECDC4", "#26A69A"],
            "side": ["#45B7D1", "#1976D2"],
            "drink": ["#96CEB4", "#4CAF50"]
        }
        
        bubble = BubbleContainer(
            size="kilo",
            body=BoxComponent(
                layout="vertical",
                contents=[
                    BoxComponent(
                        layout="vertical",
                        contents=[
                            TextComponent(
                                text=category["emoji"],
                                size="4xl",
                                align="center"
                            ),
                            TextComponent(
                                text=category["name"],
                                weight="bold",
                                size="lg",
                                color="#FFFFFF",
                                align="center",
                                margin="sm"
                            ),
                            TextComponent(
                                text=f"{len(category['items'])} 項商品",
                                size="sm",
                                color="#FFFFFF",
                                align="center",
                                margin="xs",
                                opacity=0.8
                            )
                        ],
                        background_color=gradient_colors[category_id][0],
                        padding_all="20px",
                        corner_radius="15px"
                    )
                ]
            ),
            action=PostbackAction(
                data=f"action=view_menu&category={category_id}"
            )
        )
        bubbles.append(bubble)
    
    flex_message = FlexSendMessage(
        alt_text="菜單分類",
        contents={
            "type": "carousel",
            "contents": bubbles
        }
    )
    
    return flex_message

# 創建美觀的菜單模板
def create_menu_template(category_id):
    if category_id not in MENU:
        return None
        
    category = MENU[category_id]
    bubbles = []
    
    for item_name, item_data in category["items"].items():
        # 添加標籤元素（如果有的話）
        tag_element = None
        if "tag" in item_data:
            tag_element = BoxComponent(
                layout="baseline",
                contents=[
                    TextComponent(
                        text=item_data["tag"],
                        color="#FFFFFF",
                        size="xs",
                        weight="bold"
                    )
                ],
                background_color="#FF5722",
                corner_radius="10px",
                padding_all="5px",
                position="absolute",
                offset_top="10px",
                offset_end="10px"
            )
        
        bubble = BubbleContainer(
            size="kilo",
            hero=ImageComponent(
                url=item_data["image"],
                size="full",
                aspect_mode="cover",
                aspect_ratio="4:3"
            ),
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text=item_data["name"],
                        weight="bold",
                        size="lg",
                        color="#2C3E50"
                    ),
                    TextComponent(
                        text=item_data["desc"],
                        size="sm",
                        color="#7F8C8D",
                        wrap=True,
                        margin="sm"
                    ),
                    SeparatorComponent(margin="md"),
                    BoxComponent(
                        layout="baseline",
                        contents=[
                            TextComponent(
                                text="NT$",
                                color="#E74C3C",
                                size="sm",
                                weight="bold"
                            ),
                            TextComponent(
                                text=str(item_data["price"]),
                                color="#E74C3C",
                                size="xl",
                                weight="bold",
                                margin="sm"
                            )
                        ],
                        margin="md"
                    )
                ],
                spacing="sm",
                padding_all="15px"
            ),
            footer=BoxComponent(
                layout="vertical",
                contents=[
                    ButtonComponent(
                        style="primary",
                        height="md",
                        color=category["color"],
                        action=PostbackAction(
                            label="🛒 加入購物車",
                            data=f"action=add_to_cart&category={category_id}&item={item_name}"
                        )
                    )
                ]
            )
        )
        
        # 如果有標籤，添加到bubble中
        if tag_element:
            bubble.body.contents.insert(0, tag_element)
            
        bubbles.append(bubble)
    
    # 將商品分組
    flex_messages = []
    for i in range(0, len(bubbles), 10):
        carousel = {
            "type": "carousel",
            "contents": bubbles[i:i+10]
        }
        
        flex_message = FlexSendMessage(
            alt_text=f"{category['name']} 菜單",
            contents=carousel
        )
        flex_messages.append(flex_message)
    
    return flex_messages

# 優化購物車顯示
def view_cart(user_id):
    if user_id not in user_carts or not user_carts[user_id]["items"]:
        empty_cart_bubble = BubbleContainer(
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text="🛒",
                        size="5xl",
                        align="center",
                        color="#BDC3C7"
                    ),
                    TextComponent(
                        text="購物車是空的",
                        weight="bold",
                        size="xl",
                        color="#7F8C8D",
                        align="center",
                        margin="md"
                    ),
                    TextComponent(
                        text="快來挑選美味餐點吧！",
                        size="md",
                        color="#95A5A6",
                        align="center",
                        margin="sm"
                    )
                ],
                padding_all="40px"
            ),
            footer=BoxComponent(
                layout="vertical",
                contents=[
                    ButtonComponent(
                        style="primary",
                        height="md",
                        color="#E74C3C",
                        action=PostbackAction(
                            label="🍽️ 開始點餐",
                            data="action=view_categories"
                        )
                    )
                ]
            )
        )
        
        return FlexSendMessage(alt_text="空的購物車", contents=empty_cart_bubble)
    
    cart = user_carts[user_id]
    total = 0
    item_components = []
    
    for idx, item in enumerate(cart["items"]):
        item_total = item["price"] * item["quantity"]
        total += item_total
        
        item_box = BoxComponent(
            layout="horizontal",
            contents=[
                BoxComponent(
                    layout="vertical",
                    contents=[
                        TextComponent(
                            text=item["name"],
                            weight="bold",
                            size="md",
                            color="#2C3E50"
                        ),
                        TextComponent(
                            text=f"NT${item['price']} × {item['quantity']}",
                            size="sm",
                            color="#7F8C8D",
                            margin="xs"
                        )
                    ],
                    flex=3
                ),
                TextComponent(
                    text=f"NT${item_total}",
                    size="md",
                    weight="bold",
                    color="#E74C3C",
                    align="end",
                    flex=1
                )
            ],
            margin="md"
        )
        item_components.append(item_box)
        
        if idx < len(cart["items"]) - 1:
            item_components.append(SeparatorComponent(margin="md"))
    
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                BoxComponent(
                    layout="horizontal",
                    contents=[
                        TextComponent(
                            text="🛒 購物車",
                            weight="bold",
                            size="xl",
                            color="#2C3E50"
                        ),
                        TextComponent(
                            text=f"{len(cart['items'])} 項商品",
                            size="sm",
                            color="#7F8C8D",
                            align="end"
                        )
                    ]
                ),
                SeparatorComponent(margin="lg"),
                *item_components,
                SeparatorComponent(margin="lg"),
                BoxComponent(
                    layout="horizontal",
                    contents=[
                        TextComponent(
                            text="總計",
                            weight="bold",
                            size="lg",
                            color="#2C3E50"
                        ),
                        TextComponent(
                            text=f"NT${total}",
                            weight="bold",
                            size="xl",
                            color="#E74C3C",
                            align="end"
                        )
                    ]
                )
            ]
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="md",
            contents=[
                ButtonComponent(
                    style="primary",
                    height="md",
                    color="#27AE60",
                    action=PostbackAction(
                        label="💳 確認訂單",
                        data="action=confirm_order"
                    )
                ),
                BoxComponent(
                    layout="horizontal",
                    spacing="sm",
                    contents=[
                        ButtonComponent(
                            style="secondary",
                            height="sm",
                            flex=1,
                            action=PostbackAction(
                                label="✏️ 編輯",
                                data="action=edit_cart"
                            )
                        ),
                        ButtonComponent(
                            style="secondary",
                            height="sm",
                            flex=1,
                            action=PostbackAction(
                                label="🍽️ 繼續點餐",
                                data="action=view_categories"
                            )
                        )
                    ]
                )
            ]
        )
    )
    
    return FlexSendMessage(alt_text="購物車內容", contents=bubble)

# 創建美觀的訂單確認模板
def create_order_confirmation(user_id):
    if user_id not in user_carts or not user_carts[user_id]["items"]:
        return None
        
    cart = user_carts[user_id]
    total = 0
    item_components = []
    
    for item in cart["items"]:
        item_total = item["price"] * item["quantity"]
        total += item_total
        
        item_box = BoxComponent(
            layout="horizontal",
            contents=[
                TextComponent(
                    text=item["name"],
                    size="sm",
                    color="#2C3E50",
                    flex=2
                ),
                TextComponent(
                    text=f"x{item['quantity']}",
                    size="sm",
                    color="#7F8C8D",
                    align="center",
                    flex=1
                ),
                TextComponent(
                    text=f"NT${item_total}",
                    size="sm",
                    color="#E74C3C",
                    weight="bold",
                    align="end",
                    flex=1
                )
            ],
            margin="sm"
        )
        item_components.append(item_box)
    
    order_id = generate_order_id()
    
    bubble = BubbleContainer(
        hero=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="✅",
                    size="4xl",
                    align="center",
                    color="#27AE60"
                ),
                TextComponent(
                    text="訂單確認",
                    weight="bold",
                    size="xl",
                    color="#FFFFFF",
                    align="center",
                    margin="sm"
                )
            ],
            background_color="#27AE60",
            padding_all="20px"
        ),
        body=BoxComponent(
            layout="vertical",
            contents=[
                BoxComponent(
                    layout="horizontal",
                    contents=[
                        TextComponent(
                            text="訂單編號",
                            size="sm",
                            color="#7F8C8D"
                        ),
                        TextComponent(
                            text=f"#{order_id}",
                            size="sm",
                            color="#2C3E50",
                            weight="bold",
                            align="end"
                        )
                    ]
                ),
                SeparatorComponent(margin="lg"),
                TextComponent(
                    text="訂單明細",
                    weight="bold",
                    size="md",
                    color="#2C3E50"
                ),
                *item_components,
                SeparatorComponent(margin="lg"),
                BoxComponent(
                    layout="horizontal",
                    contents=[
                        TextComponent(
                            text="總金額",
                            weight="bold",
                            size="lg",
                            color="#2C3E50"
                        ),
                        TextComponent(
                            text=f"NT${total}",
                            weight="bold",
                            size="xl",
                            color="#E74C3C",
                            align="end"
                        )
                    ]
                )
            ]
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="md",
            contents=[
                ButtonComponent(
                    style="primary",
                    height="md",
                    color="#F39C12",
                    action=PostbackAction(
                        label="💳 確認付款",
                        data=f"action=checkout&order_id={order_id}"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    height="sm",
                    action=PostbackAction(
                        label="✏️ 修改訂單",
                        data="action=edit_cart"
                    )
                )
            ]
        )
    )
    
    return FlexSendMessage(alt_text="訂單確認", contents=bubble)

# 首頁
@app.route("/")
def index():
    return render_template("index.html", menu=MENU)

# 管理後台
@app.route("/admin")
def admin():
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
    
    if text in ["點餐", "menu", "菜單"]:
        reply_message = create_categories_menu()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text in ["購物車", "cart", "🛒"]:
        reply_message = view_cart(user_id)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text in ["訂單", "orders", "📦"]:
        view_orders(event, user_id)
        
    elif text in ["幫助", "help", "?"]:
        help_bubble = BubbleContainer(
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text="📋 使用說明",
                        weight="bold",
                        size="xl",
                        color="#2C3E50"
                    ),
                    SeparatorComponent(margin="md"),
                    BoxComponent(
                        layout="vertical",
                        margin="md",
                        spacing="md",
                        contents=[
                            BoxComponent(
                                layout="horizontal",
                                contents=[
                                    TextComponent(text="🍽️", size="lg"),
                                    TextComponent(text="點餐 - 查看完整菜單", size="sm", color="#34495E", margin="sm")
                                ]
                            ),
                            BoxComponent(
                                layout="horizontal",
                                contents=[
                                    TextComponent(text="🛒", size="lg"),
                                    TextComponent(text="購物車 - 查看已選商品", size="sm", color="#34495E", margin="sm")
                                ]
                            ),
                            BoxComponent(
                                layout="horizontal",
                                contents=[
                                    TextComponent(text="📦", size="lg"),
                                    TextComponent(text="訂單 - 查看歷史訂單", size="sm", color="#34495E", margin="sm")
                                ]
                            )
                        ]
                    )
                ]
            )
        )
        
        help_message = FlexSendMessage(
            alt_text="使用說明",
            contents=help_bubble
        )
        line_bot_api.reply_message(event.reply_token, help_message)
        
    else:
        reply_message = create_welcome_message()
        line_bot_api.reply_message(event.reply_token, reply_message)

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
        reply_message = create_welcome_message()
        line_bot_api.reply_message(event.reply_token, reply_message)

# 優化添加到購物車功能
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
    
    # 創建美觀的確認訊息
    success_bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="🎉",
                    size="3xl",
                    align="center",
                    color="#27AE60"
                ),
                TextComponent(
                    text="已加入購物車！",
                    weight="bold",
                    size="lg",
                    color="#27AE60",
                    align="center",
                    margin="sm"
                ),
                SeparatorComponent(margin="md"),
                BoxComponent(
                    layout="horizontal",
                    contents=[
                        BoxComponent(
                            layout="vertical",
                            contents=[
                                TextComponent(
                                    text=item_name,
                                    weight="bold",
                                    size="md",
                                    color="#2C3E50"
                                ),
                                TextComponent(
                                    text=f"NT${item_data['price']}",
                                    size="sm",
                                    color="#E74C3C",
                                    margin="xs"
                                )
                            ],
                            flex=2
                        ),
                        TextComponent(
                            text=f"數量: {sum(item['quantity'] for item in cart['items'] if item['name'] == item_name)}",
                            size="sm",
                            color="#7F8C8D",
                            align="end",
                            flex=1
                        )
                    ],
                    margin="md"
                )
            ]
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="sm",
            contents=[
                ButtonComponent(
                    style="primary",
                    height="md",
                    color="#3498DB",
                    action=PostbackAction(
                        label="🛒 查看購物車",
                        data="action=view_cart"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    height="sm",
                    action=PostbackAction(
                        label="🍽️ 繼續點餐",
                        data="action=view_categories"
                    )
                )
            ]
        )
    )
    
    template_message = FlexSendMessage(
        alt_text="已加入購物車",
        contents=success_bubble
    )
    
    line_bot_api.reply_message(event.reply_token, template_message)

# 優化結帳功能
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
    
    # 創建美觀的成功訊息
    success_bubble = BubbleContainer(
        hero=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="🎉",
                    size="5xl",
                    align="center",
                    color="#FFFFFF"
                ),
                TextComponent(
                    text="訂單完成！",
                    weight="bold",
                    size="xl",
                    color="#FFFFFF",
                    align="center",
                    margin="sm"
                )
            ],
            background_color="#27AE60",
            padding_all="25px"
        ),
        body=BoxComponent(
            layout="vertical",
            contents=[
                BoxComponent(
                    layout="horizontal",
                    contents=[
                        TextComponent(
                            text="訂單編號",
                            size="md",
                            color="#7F8C8D"
                        ),
                        TextComponent(
                            text=f"#{order_id}",
                            size="md",
                            color="#2C3E50",
                            weight="bold",
                            align="end"
                        )
                    ]
                ),
                BoxComponent(
                    layout="horizontal",
                    contents=[
                        TextComponent(
                            text="總金額",
                            size="md",
                            color="#7F8C8D"
                        ),
                        TextComponent(
                            text=f"NT${total}",
                            size="lg",
                            color="#E74C3C",
                            weight="bold",
                            align="end"
                        )
                    ],
                    margin="sm"
                ),
                SeparatorComponent(margin="lg"),
                BoxComponent(
                    layout="vertical",
                    contents=[
                        TextComponent(
                            text="🍳 我們正在為您準備餐點",
                            size="md",
                            color="#F39C12",
                            weight="bold",
                            align="center"
                        ),
                        TextComponent(
                            text="預計準備時間：15-20分鐘",
                            size="sm",
                            color="#7F8C8D",
                            align="center",
                            margin="sm"
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
                    height="md",
                    color="#3498DB",
                    action=PostbackAction(
                        label="📦 查看訂單狀態",
                        data="action=view_orders"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    height="sm",
                    action=PostbackAction(
                        label="🍽️ 再次點餐",
                        data="action=view_categories"
                    )
                )
            ]
        )
    )
    
    line_bot_api.reply_message(
        event.reply_token,
        FlexSendMessage(alt_text="訂單完成", contents=success_bubble)
    )

# 優化查看訂單功能
def view_orders(event, user_id):
    if user_id not in user_orders or not user_orders[user_id]:
        empty_orders_bubble = BubbleContainer(
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text="📦",
                        size="5xl",
                        align="center",
                        color="#BDC3C7"
                    ),
                    TextComponent(
                        text="暫無訂單記錄",
                        weight="bold",
                        size="xl",
                        color="#7F8C8D",
                        align="center",
                        margin="md"
                    ),
                    TextComponent(
                        text="快來點餐建立您的第一筆訂單吧！",
                        size="md",
                        color="#95A5A6",
                        align="center",
                        margin="sm"
                    )
                ],
                padding_all="40px"
            ),
            footer=BoxComponent(
                layout="vertical",
                contents=[
                    ButtonComponent(
                        style="primary",
                        height="md",
                        color="#E74C3C",
                        action=PostbackAction(
                            label="🍽️ 開始點餐",
                            data="action=view_categories"
                        )
                    )
                ]
            )
        )
        
        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(alt_text="暫無訂單", contents=empty_orders_bubble)
        )
        return
    
    orders = user_orders[user_id]
    bubbles = []
    
    # 狀態顏色映射
    status_colors = {
        "confirmed": "#27AE60",
        "preparing": "#F39C12", 
        "ready": "#3498DB",
        "cancelled": "#E74C3C"
    }
    
    for order in reversed(orders[-5:]):  # 顯示最近5筆訂單，最新的在前
        items_text = ""
        for item in order["items"][:3]:  # 最多顯示3項商品
            items_text += f"• {item['name']} x{item['quantity']}\n"
        
        if len(order["items"]) > 3:
            items_text += f"• 等 {len(order['items'])} 項商品"
        
        status_text = ORDER_STATUS.get(order["status"], "未知狀態")
        status_color = status_colors.get(order["status"], "#7F8C8D")
        created_time = datetime.fromisoformat(order["created_at"]).strftime("%m/%d %H:%M")
        
        bubble = BubbleContainer(
            body=BoxComponent(
                layout="vertical",
                contents=[
                    BoxComponent(
                        layout="horizontal",
                        contents=[
                            TextComponent(
                                text=f"#{order['id']}",
                                weight="bold",
                                size="lg",
                                color="#2C3E50"
                            ),
                            BoxComponent(
                                layout="baseline",
                                contents=[
                                    TextComponent(
                                        text=status_text,
                                        color="#FFFFFF",
                                        size="xs",
                                        weight="bold"
                                    )
                                ],
                                background_color=status_color,
                                corner_radius="10px",
                                padding_all="5px"
                            )
                        ]
                    ),
                    TextComponent(
                        text=created_time,
                        size="sm",
                        color="#95A5A6",
                        margin="sm"
                    ),
                    SeparatorComponent(margin="md"),
                    TextComponent(
                        text=items_text,
                        size="sm",
                        color="#34495E",
                        wrap=True,
                        margin="md"
                    ),
                    SeparatorComponent(margin="md"),
                    BoxComponent(
                        layout="horizontal",
                        contents=[
                            TextComponent(
                                text="總金額",
                                color="#7F8C8D",
                                size="sm"
                            ),
                            TextComponent(
                                text=f"NT${order['total']}",
                                size="md",
                                color="#E74C3C",
                                weight="bold",
                                align="end"
                            )
                        ]
                    )
                ]
            )
        )
        bubbles.append(bubble)
    
    if bubbles:
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
