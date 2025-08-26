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
    ImageCarouselColumn, ConfirmTemplate, MessageAction, ImageComponent
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

# 完整菜單數據 - 使用更好看的圖片
MENU = {
    "recommended": {
        "id": "recommended",
        "name": "🔥 推薦餐點",
        "items": {
            "1號餐": {"name": "1號餐", "price": 120, "desc": "漢堡+薯條+可樂", "image": "https://images.unsplash.com/photo-1571091718767-18b5b1457add?w=400&h=300&fit=crop"},
            "2號餐": {"name": "2號餐", "price": 150, "desc": "雙層漢堡+薯條+紅茶", "image": "https://images.unsplash.com/photo-1553979459-d2229ba7433a?w=400&h=300&fit=crop"},
            "3號餐": {"name": "3號餐", "price": 180, "desc": "雞腿堡+雞塊+雪碧", "image": "https://images.unsplash.com/photo-1594212699903-ec8a3eca50f5?w=400&h=300&fit=crop"}
        }
    },
    "main": {
        "id": "main",
        "name": "🍔 主餐",
        "items": {
            "經典漢堡": {"name": "經典漢堡", "price": 70, "desc": "100%純牛肉漢堡", "image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=400&h=300&fit=crop"},
            "雙層起司堡": {"name": "雙層起司堡", "price": 90, "desc": "雙倍起司雙倍滿足", "image": "https://images.unsplash.com/photo-1572802419224-296b0aeee0d9?w=400&h=300&fit=crop"},
            "照燒雞腿堡": {"name": "照燒雞腿堡", "price": 85, "desc": "鮮嫩多汁的雞腿肉", "image": "https://images.unsplash.com/photo-1606755962773-d324e503c3ea?w=400&h=300&fit=crop"},
            "素食蔬菜堡": {"name": "素食蔬菜堡", "price": 75, "desc": "健康素食選擇", "image": "https://images.unsplash.com/photo-1520072959219-c595dc870360?w=400&h=300&fit=crop"}
        }
    },
    "side": {
        "id": "side",
        "name": "🍟 副餐",
        "items": {
            "薯條": {"name": "薯條", "price": 50, "desc": "金黃酥脆薯條", "image": "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=400&h=300&fit=crop"},
            "洋蔥圈": {"name": "洋蔥圈", "price": 60, "desc": "香脆可口洋蔥圈", "image": "https://images.unsplash.com/photo-1639024471283-03518883512d?w=400&h=300&fit=crop"},
            "雞塊": {"name": "雞塊", "price": 65, "desc": "6塊裝雞塊", "image": "https://images.unsplash.com/photo-1562967914-608f82629710?w=400&h=300&fit=crop"},
            "沙拉": {"name": "沙拉", "price": 70, "desc": "新鮮蔬菜沙拉", "image": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400&h=300&fit=crop"}
        }
    },
    "drink": {
        "id": "drink",
        "name": "🥤 飲料",
        "items": {
            "可樂": {"name": "可樂", "price": 30, "desc": "冰涼暢快可樂", "image": "https://images.unsplash.com/photo-1629203851122-3726ecdf080e?w=400&h=300&fit=crop"},
            "雪碧": {"name": "雪碧", "price": 30, "desc": "清爽解渴雪碧", "image": "https://images.unsplash.com/photo-1581636625402-29b2a704ef13?w=400&h=300&fit=crop"},
            "紅茶": {"name": "紅茶", "price": 25, "desc": "香醇濃郁紅茶", "image": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&h=300&fit=crop"},
            "咖啡": {"name": "咖啡", "price": 40, "desc": "現煮香醇咖啡", "image": "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=400&h=300&fit=crop"}
        }
    }
}

# 訂單狀態
ORDER_STATUS = {
    "cart": "🛒 購物車",
    "pending": "⏳ 待確認",
    "confirmed": "✅ 已確認",
    "preparing": "👨‍🍳 準備中",
    "ready": "🍽️ 已完成",
    "cancelled": "❌ 已取消"
}

# 用戶數據存儲 (實際應用中應使用數據庫)
user_carts = {}
user_orders = {}

# 生成唯一訂單ID
def generate_order_id():
    return datetime.now().strftime("%Y%m%d") + str(uuid.uuid4().int)[:6]

# 創建快速回覆按鈕 - 優化版
def create_quick_reply():
    items = [
        QuickReplyButton(action=PostbackAction(label="📋 查看菜單", data="action=view_categories")),
        QuickReplyButton(action=PostbackAction(label="🛒 我的購物車", data="action=view_cart")),
        QuickReplyButton(action=PostbackAction(label="📦 我的訂單", data="action=view_orders")),
        QuickReplyButton(action=PostbackAction(label="🏠 回到主頁", data="action=go_home"))
    ]
    return QuickReply(items=items)

# 創建分類選單 - 優化版
def create_categories_menu():
    columns = []
    
    categories = [
        {"id": "recommended", "name": "🔥 推薦餐點", "image": "https://images.unsplash.com/photo-1514933651103-005eec06c04b?w=1024&h=1024&fit=crop"},
        {"id": "main", "name": "🍔 主餐", "image": "https://images.unsplash.com/photo-1571091718767-18b5b1457add?w=1024&h=1024&fit=crop"},
        {"id": "side", "name": "🍟 副餐", "image": "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=1024&h=1024&fit=crop"},
        {"id": "drink", "name": "🥤 飲料", "image": "https://images.unsplash.com/photo-1544145945-f90425340c7e?w=1024&h=1024&fit=crop"}
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
        alt_text="📋 菜單分類",
        template=ImageCarouselTemplate(columns=columns)
    )

# 創建分類菜單 - 大幅優化UI版本
def create_menu_template(category_id):
    if category_id not in MENU:
        return None
        
    category = MENU[category_id]
    bubbles = []
    
    for item_name, item_data in category["items"].items():
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
                        size="xl",
                        wrap=True,
                        color="#2c3e50",
                        margin="md"
                    ),
                    TextComponent(
                        text=item_data["desc"],
                        size="md",
                        color="#7f8c8d",
                        wrap=True,
                        margin="sm"
                    ),
                    BoxComponent(
                        layout="baseline",
                        margin="lg",
                        contents=[
                            TextComponent(
                                text="NT$",
                                size="md",
                                color="#e74c3c",
                                flex=0
                            ),
                            TextComponent(
                                text=str(item_data['price']),
                                size="xxl",
                                weight="bold",
                                color="#e74c3c",
                                flex=0,
                                margin="sm"
                            )
                        ]
                    )
                ],
                spacing="sm",
                paddingAll="20px"
            ),
            footer=BoxComponent(
                layout="vertical",
                contents=[
                    ButtonComponent(
                        style="primary",
                        color="#e74c3c",
                        height="md",
                        action=PostbackAction(
                            label="🛒 加入購物車",
                            data=f"action=add_to_cart&category={category_id}&item={item_name}"
                        )
                    )
                ],
                paddingAll="20px"
            ),
            styles={
                "body": {
                    "backgroundColor": "#ffffff"
                },
                "footer": {
                    "backgroundColor": #f8f9fa
                }
            }
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
            alt_text=f"{category['name']} 菜單",
            contents=carousel
        )
        flex_messages.append(flex_message)
    
    return flex_messages

# 查看購物車 - 優化版
def view_cart(user_id):
    if user_id not in user_carts or not user_carts[user_id]["items"]:
        return TextSendMessage(
            text="🛒 您的購物車是空的\n快去選購美味的餐點吧！",
            quick_reply=create_quick_reply()
        )
    
    cart = user_carts[user_id]
    total = 0
    item_components = []
    
    for idx, item in enumerate(cart["items"], 1):
        item_total = item["price"] * item["quantity"]
        total += item_total
        
        item_box = BoxComponent(
            layout="vertical",
            contents=[
                BoxComponent(
                    layout="baseline",
                    contents=[
                        TextComponent(
                            text=f"{idx}. {item['name']}",
                            size="lg",
                            weight="bold",
                            color="#2c3e50",
                            flex=4
                        ),
                        TextComponent(
                            text=f"x{item['quantity']}",
                            size="md",
                            color="#7f8c8d",
                            flex=1,
                            align="end"
                        )
                    ]
                ),
                BoxComponent(
                    layout="baseline",
                    contents=[
                        TextComponent(
                            text=f"單價 ${item['price']}",
                            size="sm",
                            color="#95a5a6",
                            flex=3
                        ),
                        TextComponent(
                            text=f"${item_total}",
                            size="md",
                            weight="bold",
                            color="#e74c3c",
                            flex=1,
                            align="end"
                        )
                    ],
                    margin="xs"
                )
            ],
            margin="md",
            paddingAll="12px",
            backgroundColor="#f8f9fa",
            cornerRadius="8px"
        )
        item_components.append(item_box)
    
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                # 標題
                TextComponent(
                    text="🛒 購物車",
                    weight="bold",
                    size="xxl",
                    color="#e74c3c",
                    align="center"
                ),
                SeparatorComponent(margin="xl", color="#ecf0f1"),
                
                # 商品列表
                BoxComponent(
                    layout="vertical",
                    margin="xl",
                    spacing="md",
                    contents=item_components
                ),
                
                # 總計
                SeparatorComponent(margin="xl", color="#ecf0f1"),
                BoxComponent(
                    layout="baseline",
                    margin="xl",
                    contents=[
                        TextComponent(
                            text="總金額",
                            size="xl",
                            color="#2c3e50",
                            weight="bold",
                            flex=2
                        ),
                        TextComponent(
                            text=f"NT$ {total}",
                            size="xxl",
                            color="#e74c3c",
                            weight="bold",
                            flex=2,
                            align="end"
                        )
                    ]
                )
            ],
            paddingAll="20px"
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="md",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#27ae60",
                    height="md",
                    action=PostbackAction(
                        label="✅ 確認訂單",
                        data="action=confirm_order"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    height="md",
                    action=PostbackAction(
                        label="✏️ 編輯購物車",
                        data="action=edit_cart"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    height="md",
                    action=PostbackAction(
                        label="⬅️ 繼續點餐",
                        data="action=view_categories"
                    )
                )
            ],
            paddingAll="20px"
        )
    )
    
    return FlexSendMessage(
        alt_text="🛒 購物車內容",
        contents=bubble
    )

def create_edit_cart_menu(user_id):
    """創建編輯購物車選單"""
    if user_id not in user_carts or not user_carts[user_id]["items"]:
        return TextSendMessage(
            text="🛒 您的購物車是空的\n快去選購美味的餐點吧！",
            quick_reply=create_quick_reply()
        )
    
    cart = user_carts[user_id]
    bubbles = []
    
    for idx, item in enumerate(cart["items"]):
        item_total = item["price"] * item["quantity"]
        
        bubble = BubbleContainer(
            size="kilo",
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text=item["name"],
                        weight="bold",
                        size="lg",
                        color="#2c3e50"
                    ),
                    BoxComponent(
                        layout="baseline",
                        margin="md",
                        contents=[
                            TextComponent(
                                text=f"數量: {item['quantity']}",
                                size="md",
                                color="#7f8c8d",
                                flex=2
                            ),
                            TextComponent(
                                text=f"${item_total}",
                                size="lg",
                                weight="bold",
                                color="#e74c3c",
                                flex=1,
                                align="end"
                            )
                        ]
                    )
                ],
                paddingAll="20px"
            ),
            footer=BoxComponent(
                layout="vertical",
                spacing="sm",
                contents=[
                    BoxComponent(
                        layout="horizontal",
                        spacing="sm",
                        contents=[
                            ButtonComponent(
                                style="secondary",
                                height="sm",
                                action=PostbackAction(
                                    label="➖",
                                    data=f"action=decrease_item&item_index={idx}"
                                ),
                                flex=1
                            ),
                            ButtonComponent(
                                style="secondary",
                                height="sm",
                                action=PostbackAction(
                                    label="➕",
                                    data=f"action=increase_item&item_index={idx}"
                                ),
                                flex=1
                            )
                        ]
                    ),
                    ButtonComponent(
                        style="secondary",
                        color="#e74c3c",
                        height="sm",
                        action=PostbackAction(
                            label="🗑️ 移除",
                            data=f"action=remove_item&item_index={idx}"
                        )
                    )
                ],
                paddingAll="20px"
            )
        )
        bubbles.append(bubble)
    
    # 添加完成編輯按鈕
    finish_bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="✅ 編輯完成",
                    weight="bold",
                    size="xl",
                    color="#27ae60",
                    align="center"
                ),
                TextComponent(
                    text="點擊下方按鈕完成編輯",
                    size="md",
                    color="#7f8c8d",
                    align="center",
                    margin="md"
                )
            ],
            paddingAll="20px"
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="md",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#3498db",
                    height="md",
                    action=PostbackAction(
                        label="🛒 查看購物車",
                        data="action=view_cart"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    height="md",
                    action=PostbackAction(
                        label="⬅️ 繼續點餐",
                        data="action=view_categories"
                    )
                )
            ],
            paddingAll="20px"
        )
    )
    bubbles.append(finish_bubble)
    
    return FlexSendMessage(
        alt_text="✏️ 編輯購物車",
        contents={
            "type": "carousel",
            "contents": bubbles
        }
    )

def modify_cart_item(user_id, item_index, action_type):
    """修改購物車商品數量或移除商品"""
    if user_id not in user_carts or not user_carts[user_id]["items"]:
        return None, "購物車是空的"
    
    cart = user_carts[user_id]
    
    try:
        item_index = int(item_index)
        if item_index < 0 or item_index >= len(cart["items"]):
            return None, "找不到該商品"
        
        item = cart["items"][item_index]
        item_name = item["name"]
        
        if action_type == "increase":
            item["quantity"] += 1
            cart["updated_at"] = datetime.now().isoformat()
            return "success", f"✅ {item_name} 數量已增加到 {item['quantity']}"
            
        elif action_type == "decrease":
            if item["quantity"] > 1:
                item["quantity"] -= 1
                cart["updated_at"] = datetime.now().isoformat()
                return "success", f"✅ {item_name} 數量已減少到 {item['quantity']}"
            else:
                # 數量為1時，直接移除
                cart["items"].pop(item_index)
                cart["updated_at"] = datetime.now().isoformat()
                return "removed", f"🗑️ {item_name} 已從購物車移除"
                
        elif action_type == "remove":
            cart["items"].pop(item_index)
            cart["updated_at"] = datetime.now().isoformat()
            return "removed", f"🗑️ {item_name} 已從購物車移除"
            
    except (ValueError, IndexError):
        return None, "操作失敗，請重試"

def create_clear_cart_confirmation():
    """創建清空購物車確認對話框"""
    confirm_template = ConfirmTemplate(
        text="確定要清空購物車嗎？\n此操作無法復原",
        actions=[
            PostbackAction(
                label="✅ 確定清空",
                data="action=clear_cart_confirm"
            ),
            PostbackAction(
                label="❌ 取消",
                data="action=view_cart"
            )
        ]
    )
    
    return TemplateSendMessage(
        alt_text="清空購物車確認",
        template=confirm_template
    )

def handle_cart_editing_actions(event, user_id, data_dict):
    """處理購物車編輯相關動作"""
    action = data_dict.get('action', '')
    
    if action == 'edit_cart':
        reply_message = create_edit_cart_menu(user_id)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'increase_item':
        item_index = data_dict.get('item_index', '')
        result, message = modify_cart_item(user_id, item_index, "increase")
        
        if result == "success":
            # 重新顯示編輯選單
            reply_message = create_edit_cart_menu(user_id)
            line_bot_api.reply_message(event.reply_token, reply_message)
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"❌ {message}")
            )
            
    elif action == 'decrease_item':
        item_index = data_dict.get('item_index', '')
        result, message = modify_cart_item(user_id, item_index, "decrease")
        
        if result in ["success", "removed"]:
            # 重新顯示編輯選單
            reply_message = create_edit_cart_menu(user_id)
            line_bot_api.reply_message(event.reply_token, reply_message)
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"❌ {message}")
            )
            
    elif action == 'remove_item':
        item_index = data_dict.get('item_index', '')
        result, message = modify_cart_item(user_id, item_index, "remove")
        
        if result == "removed":
            # 重新顯示編輯選單
            reply_message = create_edit_cart_menu(user_id)
            line_bot_api.reply_message(event.reply_token, reply_message)
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"❌ {message}")
            )
            
    elif action == 'clear_cart':
        reply_message = create_clear_cart_confirmation()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'clear_cart_confirm':
        if user_id in user_carts:
            user_carts[user_id]["items"] = []
            user_carts[user_id]["updated_at"] = datetime.now().isoformat()
        
        success_message = TextSendMessage(
            text="🗑️ 購物車已清空\n快去選購美味的餐點吧！",
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, success_message)

# 確認訂單模板 - 優化版
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
            layout="baseline",
            contents=[
                TextComponent(
                    text=f"{item['name']} x{item['quantity']}",
                    size="md",
                    color="#2c3e50",
                    flex=3
                ),
                TextComponent(
                    text=f"${item_total}",
                    size="md",
                    weight="bold",
                    color="#e74c3c",
                    flex=1,
                    align="end"
                )
            ],
            margin="sm"
        )
        item_components.append(item_box)
    
    order_id = generate_order_id()
    
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                # 標題
                TextComponent(
                    text="✅ 訂單確認",
                    weight="bold",
                    size="xxl",
                    color="#27ae60",
                    align="center"
                ),
                
                # 訂單編號
                BoxComponent(
                    layout="vertical",
                    margin="xl",
                    contents=[
                        TextComponent(
                            text="訂單編號",
                            size="sm",
                            color="#7f8c8d"
                        ),
                        TextComponent(
                            text=order_id,
                            size="lg",
                            weight="bold",
                            color="#2c3e50",
                            margin="xs"
                        )
                    ],
                    paddingAll="12px",
                    backgroundColor="#e8f5e8",
                    cornerRadius="8px"
                ),
                
                SeparatorComponent(margin="xl", color="#ecf0f1"),
                
                # 商品列表標題
                TextComponent(
                    text="📋 訂單內容",
                    size="lg",
                    weight="bold",
                    color="#2c3e50",
                    margin="xl"
                ),
                
                # 商品列表
                BoxComponent(
                    layout="vertical",
                    margin="md",
                    spacing="sm",
                    contents=item_components
                ),
                
                # 總計
                SeparatorComponent(margin="xl", color="#ecf0f1"),
                BoxComponent(
                    layout="baseline",
                    margin="xl",
                    contents=[
                        TextComponent(
                            text="總金額",
                            size="xl",
                            color="#2c3e50",
                            weight="bold",
                            flex=2
                        ),
                        TextComponent(
                            text=f"NT$ {total}",
                            size="xxl",
                            color="#e74c3c",
                            weight="bold",
                            flex=2,
                            align="end"
                        )
                    ],
                    paddingAll="12px",
                    backgroundColor="#fff5f5",
                    cornerRadius="8px"
                )
            ],
            paddingAll="20px"
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="md",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#27ae60",
                    height="md",
                    action=PostbackAction(
                        label="💳 確認付款",
                        data=f"action=checkout&order_id={order_id}"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    height="md",
                    action=PostbackAction(
                        label="✏️ 修改訂單",
                        data="action=edit_cart"
                    )
                )
            ],
            paddingAll="20px"
        )
    )
    
    return FlexSendMessage(
        alt_text="✅ 訂單確認",
        contents=bubble
    )

# 首頁
@app.route("/")
def index():
    return render_template("index.html", menu=MENU)

# 管理後台
@app.route("/admin")
def admin():
    # 計算訂單統計數據
    orders_count = sum(len(orders) for orders in user_orders.values())
    
    # 計算今日訂單
    today = datetime.now().date()
    today_orders = 0
    for user_id, orders in user_orders.items():
        for order in orders:
            order_date = datetime.fromisoformat(order["created_at"]).date()
            if order_date == today:
                today_orders += 1
    
    # 計算待處理訂單
    pending_orders = 0
    for user_id, orders in user_orders.items():
        for order in orders:
            if order["status"] in ["pending", "confirmed"]:
                pending_orders += 1
    
    # 獲取最近5筆訂單
    all_orders = []
    for user_id, orders in user_orders.items():
        for order in orders:
            all_orders.append({
                "id": order["id"],
                "user_id": user_id,
                "total": order["total"],
                "status": order["status"],
                "created_at": order["created_at"]
            })
    
    # 按創建時間排序
    all_orders.sort(key=lambda x: x["created_at"], reverse=True)
    recent_orders = all_orders[:5]
    
    return render_template(
        "admin_dashboard.html", 
        orders_count=orders_count,
        today_orders=today_orders,
        pending_orders=pending_orders,
        recent_orders=recent_orders
    )

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

# 處理文字訊息 - 優化版
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
        help_bubble = BubbleContainer(
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text="🎯 使用說明",
                        weight="bold",
                        size="xxl",
                        color="#3498db",
                        align="center"
                    ),
                    SeparatorComponent(margin="xl", color="#ecf0f1"),
                    BoxComponent(
                        layout="vertical",
                        margin="xl",
                        spacing="lg",
                        contents=[
                            BoxComponent(
                                layout="baseline",
                                contents=[
                                    TextComponent(
                                        text="📋",
                                        size="lg",
                                        flex=1
                                    ),
                                    TextComponent(
                                        text="點餐 - 查看完整菜單",
                                        size="md",
                                        color="#2c3e50",
                                        flex=4,
                                        wrap=True
                                    )
                                ]
                            ),
                            BoxComponent(
                                layout="baseline",
                                contents=[
                                    TextComponent(
                                        text="🛒",
                                        size="lg",
                                        flex=1
                                    ),
                                    TextComponent(
                                        text="購物車 - 查看已選商品",
                                        size="md",
                                        color="#2c3e50",
                                        flex=4,
                                        wrap=True
                                    )
                                ]
                            ),
                            BoxComponent(
                                layout="baseline",
                                contents=[
                                    TextComponent(
                                        text="📦",
                                        size="lg",
                                        flex=1
                                    ),
                                    TextComponent(
                                        text="訂單 - 查看訂單狀態",
                                        size="md",
                                        color="#2c3e50",
                                        flex=4,
                                        wrap=True
                                    )
                                ]
                            ),
                            BoxComponent(
                                layout="baseline",
                                contents=[
                                    TextComponent(
                                        text="❓",
                                        size="lg",
                                        flex=1
                                    ),
                                    TextComponent(
                                        text="幫助 - 顯示使用說明",
                                        size="md",
                                        color="#2c3e50",
                                        flex=4,
                                        wrap=True
                                    )
                                ]
                            )
                        ]
                    ),
                    SeparatorComponent(margin="xl", color="#ecf0f1"),
                    TextComponent(
                        text="💡 您也可以使用下方的快速按鈕",
                        size="sm",
                        color="#7f8c8d",
                        align="center",
                        margin="xl"
                    )
                ],
                paddingAll="20px"
            )
        )
        
        help_message = FlexSendMessage(
            alt_text="🎯 使用說明",
            contents=help_bubble,
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, help_message)
        
    else:
        # 預設回覆 - 優化版
        welcome_bubble = BubbleContainer(
            hero=ImageComponent(
                url="https://images.unsplash.com/photo-1513475382585-d06e58bcb0e0?w=1024&h=400&fit=crop",
                size="full",
                aspect_mode="cover",
                aspect_ratio="5:2"
            ),
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text="🍽️ 美食點餐系統",
                        weight="bold",
                        size="xxl",
                        color="#e74c3c",
                        align="center"
                    ),
                    TextComponent(
                        text="歡迎使用線上點餐服務",
                        size="lg",
                        color="#2c3e50",
                        align="center",
                        margin="md"
                    ),
                    SeparatorComponent(margin="xl", color="#ecf0f1"),
                    TextComponent(
                        text="請選擇您需要的服務：",
                        size="md",
                        color="#7f8c8d",
                        align="center",
                        margin="xl"
                    )
                ],
                paddingAll="20px"
            ),
            footer=BoxComponent(
                layout="vertical",
                spacing="md",
                contents=[
                    ButtonComponent(
                        style="primary",
                        color="#e74c3c",
                        height="md",
                        action=PostbackAction(
                            label="📋 開始點餐",
                            data="action=view_categories"
                        )
                    ),
                    ButtonComponent(
                        style="secondary",
                        height="md",
                        action=PostbackAction(
                            label="🛒 查看購物車",
                            data="action=view_cart"
                        )
                    )
                ],
                paddingAll="20px"
            )
        )
        
        welcome_message = FlexSendMessage(
            alt_text="🍽️ 歡迎使用美食點餐系統",
            contents=welcome_bubble,
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, welcome_message)

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
    
    # 購物車編輯相關動作
    if action in ['edit_cart', 'increase_item', 'decrease_item', 'remove_item', 'clear_cart', 'clear_cart_confirm']:
        handle_cart_editing_actions(event, user_id, data_dict)
        return
    
    if action == 'view_categories':
        reply_message = create_categories_menu()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'view_menu':
        category_id = data_dict.get('category', '')
        menu_messages = create_menu_template(category_id)
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
                TextSendMessage(text="❌ 找不到該菜單分類")
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
                    text="🛒 您的購物車是空的，無法建立訂單\n快去選購美味的餐點吧！",
                    quick_reply=create_quick_reply()
                )
            )
            
    elif action == 'checkout':
        order_id = data_dict.get('order_id', '')
        checkout_order(event, user_id, order_id)
        
    elif action == 'view_orders':
        view_orders(event, user_id)
        
    elif action == 'go_home':
        # 優化版歡迎訊息
        welcome_bubble = BubbleContainer(
            hero=ImageComponent(
                url="https://images.unsplash.com/photo-1513475382585-d06e58bcb0e0?w=1024&h=400&fit=crop",
                size="full",
                aspect_mode="cover",
                aspect_ratio="5:2"
            ),
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text="🍽️ 美食點餐系統",
                        weight="bold",
                        size="xxl",
                        color="#e74c3c",
                        align="center"
                    ),
                    TextComponent(
                        text="歡迎使用線上點餐服務",
                        size="lg",
                        color="#2c3e50",
                        align="center",
                        margin="md"
                    ),
                    SeparatorComponent(margin="xl", color="#ecf0f1"),
                    TextComponent(
                        text="請選擇您需要的服務：",
                        size="md",
                        color="#7f8c8d",
                        align="center",
                        margin="xl"
                    )
                ],
                paddingAll="20px"
            ),
            footer=BoxComponent(
                layout="vertical",
                spacing="md",
                contents=[
                    ButtonComponent(
                        style="primary",
                        color="#e74c3c",
                        height="md",
                        action=PostbackAction(
                            label="📋 開始點餐",
                            data="action=view_categories"
                        )
                    ),
                    ButtonComponent(
                        style="secondary",
                        height="md",
                        action=PostbackAction(
                            label="🛒 查看購物車",
                            data="action=view_cart"
                        )
                    )
                ],
                paddingAll="20px"
            )
        )
        
        welcome_message = FlexSendMessage(
            alt_text="🍽️ 歡迎使用美食點餐系統",
            contents=welcome_bubble,
            quick_reply=create_quick_reply()
        )
        line_bot_api.reply_message(event.reply_token, welcome_message)

# 添加到購物車 - 優化版
def add_to_cart(event, user_id, category_id, item_name):
    if category_id not in MENU or item_name not in MENU[category_id]["items"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="❌ 找不到該商品")
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
    
    # 優化版確認訊息
    confirm_bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="✅ 加入成功！",
                    weight="bold",
                    size="xl",
                    color="#27ae60",
                    align="center"
                ),
                SeparatorComponent(margin="lg", color="#ecf0f1"),
                BoxComponent(
                    layout="vertical",
                    margin="lg",
                    contents=[
                        TextComponent(
                            text=f"🍽️ {item_name}",
                            size="lg",
                            weight="bold",
                            color="#2c3e50",
                            align="center"
                        ),
                        TextComponent(
                            text="已成功加入購物車",
                            size="md",
                            color="#7f8c8d",
                            align="center",
                            margin="sm"
                        )
                    ]
                )
            ],
            paddingAll="20px"
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="md",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#3498db",
                    height="md",
                    action=PostbackAction(
                        label="🛒 查看購物車",
                        data="action=view_cart"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    height="md",
                    action=PostbackAction(
                        label="⬅️ 繼續點餐",
                        data="action=view_categories"
                    )
                )
            ],
            paddingAll="20px"
        )
    )
    
    template_message = FlexSendMessage(
        alt_text="✅ 已加入購物車",
        contents=confirm_bubble
    )
    
    line_bot_api.reply_message(event.reply_token, template_message)

# 結帳 - 優化版
def checkout_order(event, user_id, order_id):
    if user_id not in user_carts or not user_carts[user_id]["items"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="🛒 您目前沒有訂單可以結帳\n快去選購美味的餐點吧！",
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
    
    # 優化版成功訊息
    success_bubble = BubbleContainer(
        hero=ImageComponent(
            url="https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1024&h=400&fit=crop",
            size="full",
            aspect_mode="cover",
            aspect_ratio="5:2"
        ),
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="🎉 訂單成功！",
                    weight="bold",
                    size="xxl",
                    color="#27ae60",
                    align="center"
                ),
                SeparatorComponent(margin="xl", color="#ecf0f1"),
                BoxComponent(
                    layout="vertical",
                    margin="xl",
                    spacing="lg",
                    contents=[
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                TextComponent(
                                    text="📋 訂單編號",
                                    size="md",
                                    color="#7f8c8d",
                                    flex=2
                                ),
                                TextComponent(
                                    text=order_id,
                                    size="md",
                                    weight="bold",
                                    color="#2c3e50",
                                    flex=3,
                                    align="end"
                                )
                            ]
                        ),
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                TextComponent(
                                    text="💰 總金額",
                                    size="md",
                                    color="#7f8c8d",
                                    flex=2
                                ),
                                TextComponent(
                                    text=f"NT$ {total}",
                                    size="lg",
                                    weight="bold",
                                    color="#e74c3c",
                                    flex=3,
                                    align="end"
                                )
                            ]
                        )
                    ]
                ),
                SeparatorComponent(margin="xl", color="#ecf0f1"),
                TextComponent(
                    text="👨‍🍳 我們將開始準備您的餐點\n請稍候，感謝您的訂購！",
                    size="md",
                    color="#2c3e50",
                    align="center",
                    margin="xl",
                    wrap=True
                )
            ],
            paddingAll="20px"
        ),
        footer=BoxComponent(
            layout="vertical",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#3498db",
                    height="md",
                    action=PostbackAction(
                        label="📦 查看我的訂單",
                        data="action=view_orders"
                    )
                )
            ],
            paddingAll="20px"
        )
    )
    
    line_bot_api.reply_message(
        event.reply_token,
        FlexSendMessage(
            alt_text="🎉 訂單成功",
            contents=success_bubble,
            quick_reply=create_quick_reply()
        )
    )

# 查看訂單 - 優化版
def view_orders(event, user_id):
    if user_id not in user_orders or not user_orders[user_id]:
        empty_bubble = BubbleContainer(
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text="📦 我的訂單",
                        weight="bold",
                        size="xxl",
                        color="#3498db",
                        align="center"
                    ),
                    SeparatorComponent(margin="xl", color="#ecf0f1"),
                    BoxComponent(
                        layout="vertical",
                        margin="xl",
                        contents=[
                            TextComponent(
                                text="📋",
                                size="xxl",
                                align="center",
                                color="#bdc3c7"
                            ),
                            TextComponent(
                                text="您目前沒有訂單",
                                size="lg",
                                color="#7f8c8d",
                                align="center",
                                margin="md"
                            ),
                            TextComponent(
                                text="快去點些美味的餐點吧！",
                                size="md",
                                color="#95a5a6",
                                align="center",
                                margin="sm"
                            )
                        ]
                    )
                ],
                paddingAll="20px"
            ),
            footer=BoxComponent(
                layout="vertical",
                contents=[
                    ButtonComponent(
                        style="primary",
                        color="#e74c3c",
                        height="md",
                        action=PostbackAction(
                            label="📋 開始點餐",
                            data="action=view_categories"
                        )
                    )
                ],
                paddingAll="20px"
            )
        )
        
        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(
                alt_text="📦 我的訂單",
                contents=empty_bubble,
                quick_reply=create_quick_reply()
            )
        )
        return
    
    orders = user_orders[user_id]
    bubbles = []
    
    for order in orders[-5:]:  # 顯示最近5筆訂單
        item_components = []
        for item in order["items"]:
            item_box = BoxComponent(
                layout="baseline",
                contents=[
                    TextComponent(
                        text=f"{item['name']} x{item['quantity']}",
                        size="sm",
                        color="#2c3e50",
                        flex=3
                    ),
                    TextComponent(
                        text=f"${item['price'] * item['quantity']}",
                        size="sm",
                        color="#e74c3c",
                        flex=1,
                        align="end"
                    )
                ]
            )
            item_components.append(item_box)
        
        status_text = ORDER_STATUS.get(order["status"], "❓ 未知狀態")
        created_time = datetime.fromisoformat(order["created_at"]).strftime("%m/%d %H:%M")
        
        # 狀態顏色對應
        status_colors = {
            "pending": "#f39c12",
            "confirmed": "#27ae60",
            "preparing": "#3498db",
            "ready": "#2ecc71",
            "cancelled": "#e74c3c"
        }
        status_color = status_colors.get(order["status"], "#95a5a6")
        
        bubble = BubbleContainer(
            size="kilo",
            body=BoxComponent(
                layout="vertical",
                contents=[
                    # 訂單標題
                    BoxComponent(
                        layout="baseline",
                        contents=[
                            TextComponent(
                                text=f"📋 #{order['id']}",
                                weight="bold",
                                size="lg",
                                color="#2c3e50",
                                flex=3
                            ),
                            TextComponent(
                                text=created_time,
                                size="xs",
                                color="#95a5a6",
                                flex=2,
                                align="end"
                            )
                        ]
                    ),
                    
                    # 狀態
                    BoxComponent(
                        layout="vertical",
                        margin="md",
                        contents=[
                            TextComponent(
                                text=status_text,
                                size="md",
                                weight="bold",
                                color=status_color
                            )
                        ],
                        paddingAll="8px",
                        backgroundColor="#f8f9fa",
                        cornerRadius="6px"
                    ),
                    
                    SeparatorComponent(margin="md", color="#ecf0f1"),
                    
                    # 商品列表
                    BoxComponent(
                        layout="vertical",
                        margin="md",
                        spacing="xs",
                        contents=item_components
                    ),
                    
                    SeparatorComponent(margin="md", color="#ecf0f1"),
                    
                    # 總計
                    BoxComponent(
                        layout="baseline",
                        margin="md",
                        contents=[
                            TextComponent(
                                text="總金額",
                                color="#7f8c8d",
                                size="md",
                                flex=2
                            ),
                            TextComponent(
                                text=f"NT$ {order['total']}",
                                size="lg",
                                color="#e74c3c",
                                weight="bold",
                                flex=2,
                                align="end"
                            )
                        ]
                    )
                ],
                paddingAll="20px"
            )
        )
        bubbles.append(bubble)
    
    flex_message = FlexSendMessage(
        alt_text="📦 我的訂單",
        contents={
            "type": "carousel",
            "contents": bubbles
        }
    )
    
    line_bot_api.reply_message(event.reply_token, flex_message)

if __name__ == "__main__":
    app.run(debug=True)
