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
import random

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

# 完整菜單數據 - 更豐富的內容
MENU = {
    "recommended": {
        "id": "recommended",
        "name": "⭐ 推薦餐點",
        "emoji": "⭐",
        "color": "#FF6B6B",
        "items": {
            "招牌套餐": {
                "name": "招牌套餐", 
                "price": 199, 
                "desc": "雙層牛肉堡+薯條+可樂+沙拉", 
                "image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=400&h=300&fit=crop",
                "calories": 850,
                "discount": 20,
                "is_popular": True
            },
            "海陸套餐": {
                "name": "海陸套餐", 
                "price": 289, 
                "desc": "炸雞腿堡+魚排+薯條+紅茶", 
                "image": "https://images.unsplash.com/photo-1551782450-17144efb9c50?w=400&h=300&fit=crop",
                "calories": 1120,
                "discount": 15,
                "is_popular": True
            },
            "素食套餐": {
                "name": "素食套餐", 
                "price": 149, 
                "desc": "素食堡+地瓜薯條+豆漿", 
                "image": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400&h=300&fit=crop",
                "calories": 650,
                "is_vegetarian": True
            }
        }
    },
    "main": {
        "id": "main",
        "name": "🍔 主餐",
        "emoji": "🍔",
        "color": "#4ECDC4",
        "items": {
            "經典牛肉堡": {
                "name": "經典牛肉堡", 
                "price": 89, 
                "desc": "100%純牛肉餅+生菜+番茄", 
                "image": "https://images.unsplash.com/photo-1551615593-ef5fe247e8f7?w=400&h=300&fit=crop",
                "calories": 520,
                "spicy_level": 0
            },
            "辣味雞腿堡": {
                "name": "辣味雞腿堡", 
                "price": 99, 
                "desc": "香辣炸雞腿+生菜+特製辣醬", 
                "image": "https://images.unsplash.com/photo-1606755962773-d324e9a13086?w=400&h=300&fit=crop",
                "calories": 680,
                "spicy_level": 3
            },
            "雙層起司堡": {
                "name": "雙層起司堡", 
                "price": 129, 
                "desc": "雙倍起司+雙倍牛肉+洋蔥", 
                "image": "https://images.unsplash.com/photo-1572802419224-296b0aeee0d9?w=400&h=300&fit=crop",
                "calories": 890,
                "is_popular": True
            },
            "魚排堡": {
                "name": "魚排堡", 
                "price": 79, 
                "desc": "酥炸魚排+塔塔醬+生菜", 
                "image": "https://images.unsplash.com/photo-1594212699903-ec8a3eca50f5?w=400&h=300&fit=crop",
                "calories": 450,
                "spicy_level": 0
            }
        }
    },
    "side": {
        "id": "side",
        "name": "🍟 副餐",
        "emoji": "🍟",
        "color": "#45B7D1",
        "items": {
            "經典薯條": {
                "name": "經典薯條", 
                "price": 49, 
                "desc": "金黃酥脆薯條", 
                "image": "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=400&h=300&fit=crop",
                "calories": 365,
                "size_options": ["小", "中", "大"]
            },
            "地瓜薯條": {
                "name": "地瓜薯條", 
                "price": 59, 
                "desc": "香甜地瓜薯條", 
                "image": "https://images.unsplash.com/photo-1541592106381-b31e9677c0e5?w=400&h=300&fit=crop",
                "calories": 290,
                "is_healthy": True
            },
            "洋蔥圈": {
                "name": "洋蔥圈", 
                "price": 69, 
                "desc": "酥脆洋蔥圈 8個", 
                "image": "https://images.unsplash.com/photo-1639024471283-03518883512d?w=400&h=300&fit=crop",
                "calories": 410
            },
            "雞塊套餐": {
                "name": "雞塊套餐", 
                "price": 89, 
                "desc": "香嫩雞塊6塊+醬料", 
                "image": "https://images.unsplash.com/photo-1562967914-608f82629710?w=400&h=300&fit=crop",
                "calories": 480,
                "is_popular": True
            },
            "凱撒沙拉": {
                "name": "凱撒沙拉", 
                "price": 79, 
                "desc": "新鮮蔬菜+凱撒醬", 
                "image": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400&h=300&fit=crop",
                "calories": 180,
                "is_healthy": True
            }
        }
    },
    "drink": {
        "id": "drink",
        "name": "🥤 飲料",
        "emoji": "🥤",
        "color": "#96CEB4",
        "items": {
            "經典可樂": {
                "name": "經典可樂", 
                "price": 35, 
                "desc": "冰涼暢快可樂", 
                "image": "https://images.unsplash.com/photo-1629203851122-3726ecdf080e?w=400&h=300&fit=crop",
                "calories": 139,
                "size_options": ["小", "中", "大"]
            },
            "檸檬汽水": {
                "name": "檸檬汽水", 
                "price": 35, 
                "desc": "清爽檸檬汽水", 
                "image": "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=400&h=300&fit=crop",
                "calories": 120
            },
            "紅茶": {
                "name": "紅茶", 
                "price": 29, 
                "desc": "香醇紅茶", 
                "image": "https://images.unsplash.com/photo-1556881286-3e4765c6c20d?w=400&h=300&fit=crop",
                "calories": 70
            },
            "美式咖啡": {
                "name": "美式咖啡", 
                "price": 49, 
                "desc": "現煮美式咖啡", 
                "image": "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=400&h=300&fit=crop",
                "calories": 10,
                "caffeine": "高"
            },
            "鮮榨柳橙汁": {
                "name": "鮮榨柳橙汁", 
                "price": 59, 
                "desc": "100%純果汁", 
                "image": "https://images.unsplash.com/photo-1613478223719-2ab802602423?w=400&h=300&fit=crop",
                "calories": 112,
                "is_healthy": True
            },
            "奶昔": {
                "name": "奶昔", 
                "price": 69, 
                "desc": "香草奶昔", 
                "image": "https://images.unsplash.com/photo-1541544181051-e46607bc22b4?w=400&h=300&fit=crop",
                "calories": 350,
                "flavor_options": ["香草", "草莓", "巧克力"]
            }
        }
    },
    "dessert": {
        "id": "dessert",
        "name": "🍰 甜點",
        "emoji": "🍰",
        "color": "#DDA0DD",
        "items": {
            "蘋果派": {
                "name": "蘋果派", 
                "price": 59, 
                "desc": "香甜蘋果派", 
                "image": "https://images.unsplash.com/photo-1621743478914-cc8a86d7e7b5?w=400&h=300&fit=crop",
                "calories": 280
            },
            "巧克力聖代": {
                "name": "巧克力聖代", 
                "price": 89, 
                "desc": "濃郁巧克力聖代", 
                "image": "https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=400&h=300&fit=crop",
                "calories": 420
            },
            "起司蛋糕": {
                "name": "起司蛋糕", 
                "price": 79, 
                "desc": "濃郁起司蛋糕", 
                "image": "https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445?w=400&h=300&fit=crop",
                "calories": 340
            }
        }
    }
}

# 訂單狀態
ORDER_STATUS = {
    "cart": {"name": "購物車", "emoji": "🛒", "color": "#999999"},
    "pending": {"name": "待確認", "emoji": "⏳", "color": "#FFA500"},
    "confirmed": {"name": "已確認", "emoji": "✅", "color": "#32CD32"},
    "preparing": {"name": "準備中", "emoji": "👨‍🍳", "color": "#FF6B6B"},
    "ready": {"name": "已完成", "emoji": "🎉", "color": "#4ECDC4"},
    "delivered": {"name": "已送達", "emoji": "🚚", "color": "#90EE90"},
    "cancelled": {"name": "已取消", "emoji": "❌", "color": "#FF0000"}
}

# 用戶數據存儲 (實際應用中應使用數據庫)
user_carts = {}
user_orders = {}
user_preferences = {}
store_info = {
    "name": "🍔 美味餐廳",
    "address": "台北市信義區美食街123號",
    "phone": "02-1234-5678",
    "hours": "09:00 - 22:00",
    "delivery_fee": 30,
    "min_order": 100
}

# 生成唯一訂單ID
def generate_order_id():
    return datetime.now().strftime("%Y%m%d") + str(uuid.uuid4().int)[:6]

# 獲取問候語
def get_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "🌅 早安"
    elif 12 <= hour < 17:
        return "🌞 午安"
    elif 17 <= hour < 21:
        return "🌆 晚安"
    else:
        return "🌙 夜安"

# 創建豐富的快速回覆按鈕
def create_enhanced_quick_reply():
    items = [
        QuickReplyButton(action=PostbackAction(label="📋 瀏覽菜單", data="action=view_categories")),
        QuickReplyButton(action=PostbackAction(label="🛒 購物車", data="action=view_cart")),
        QuickReplyButton(action=PostbackAction(label="📦 我的訂單", data="action=view_orders")),
        QuickReplyButton(action=PostbackAction(label="⭐ 今日推薦", data="action=daily_special")),
        QuickReplyButton(action=PostbackAction(label="ℹ️ 店家資訊", data="action=store_info")),
        QuickReplyButton(action=PostbackAction(label="🎯 客服", data="action=customer_service"))
    ]
    return QuickReply(items=items)

# 創建精美的歡迎訊息
def create_welcome_message():
    greeting = get_greeting()
    bubble = BubbleContainer(
        hero=ImageComponent(
            url="https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800&h=400&fit=crop",
            size="full",
            aspect_ratio="20:13",
            aspect_mode="cover"
        ),
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text=f"{greeting}，歡迎光臨！",
                    weight="bold",
                    size="xl",
                    color="#FF6B6B"
                ),
                TextComponent(
                    text=store_info["name"],
                    size="lg",
                    color="#333333",
                    margin="md"
                ),
                SeparatorComponent(margin="lg"),
                BoxComponent(
                    layout="vertical",
                    margin="lg",
                    spacing="sm",
                    contents=[
                        BoxComponent(
                            layout="baseline",
                            spacing="sm",
                            contents=[
                                IconComponent(
                                    url="https://cdn-icons-png.flaticon.com/512/684/684908.png",
                                    size="sm"
                                ),
                                TextComponent(
                                    text="營業時間：" + store_info["hours"],
                                    size="sm",
                                    color="#666666",
                                    flex=4
                                )
                            ]
                        ),
                        BoxComponent(
                            layout="baseline",
                            spacing="sm",
                            contents=[
                                IconComponent(
                                    url="https://cdn-icons-png.flaticon.com/512/732/732200.png",
                                    size="sm"
                                ),
                                TextComponent(
                                    text=f"最低消費：${store_info['min_order']}",
                                    size="sm",
                                    color="#666666",
                                    flex=4
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
                    height="sm",
                    color="#FF6B6B",
                    action=PostbackAction(
                        label="🍽️ 立即點餐",
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
                                label="⭐ 推薦",
                                data="action=daily_special"
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
    
    return FlexSendMessage(
        alt_text="歡迎訊息",
        contents=bubble
    )

# 創建精美的分類選單
def create_enhanced_categories_menu():
    bubbles = []
    
    for category_id, category in MENU.items():
        # 計算分類商品數量
        item_count = len(category["items"])
        
        # 獲取分類中的熱門商品
        popular_items = [item for item in category["items"].values() if item.get("is_popular", False)]
        popular_count = len(popular_items)
        
        bubble = BubbleContainer(
            size="kilo",
            hero=BoxComponent(
                layout="vertical",
                contents=[
                    BoxComponent(
                        layout="vertical",
                        contents=[
                            TextComponent(
                                text=category["emoji"],
                                size="4xl",
                                align="center",
                                color=category["color"]
                            ),
                            TextComponent(
                                text=category["name"],
                                size="lg",
                                weight="bold",
                                align="center",
                                color="#333333",
                                margin="md"
                            )
                        ],
                        backgroundColor=f"{category['color']}20",
                        paddingAll="20px",
                        cornerRadius="10px"
                    )
                ]
            ),
            body=BoxComponent(
                layout="vertical",
                contents=[
                    BoxComponent(
                        layout="baseline",
                        spacing="sm",
                        contents=[
                            TextComponent(
                                text="商品數量：",
                                size="sm",
                                color="#666666",
                                flex=2
                            ),
                            TextComponent(
                                text=f"{item_count} 項",
                                size="sm",
                                color="#333333",
                                weight="bold",
                                flex=1
                            )
                        ]
                    ),
                    BoxComponent(
                        layout="baseline",
                        spacing="sm",
                        contents=[
                            TextComponent(
                                text="熱門商品：",
                                size="sm",
                                color="#666666",
                                flex=2
                            ),
                            TextComponent(
                                text=f"{popular_count} 項",
                                size="sm",
                                color="#FF6B6B",
                                weight="bold",
                                flex=1
                            )
                        ]
                    ) if popular_count > 0 else SpacerComponent(size="sm")
                ],
                spacing="sm",
                paddingAll="15px"
            ),
            footer=BoxComponent(
                layout="vertical",
                contents=[
                    ButtonComponent(
                        style="primary",
                        color=category["color"],
                        action=PostbackAction(
                            label=f"瀏覽 {category['name']}",
                            data=f"action=view_menu&category={category_id}"
                        )
                    )
                ]
            )
        )
        bubbles.append(bubble)
    
    return FlexSendMessage(
        alt_text="菜單分類",
        contents={
            "type": "carousel",
            "contents": bubbles
        }
    )

# 創建精美的商品卡片
def create_enhanced_menu_template(category_id):
    if category_id not in MENU:
        return None
        
    category = MENU[category_id]
    bubbles = []
    
    for item_name, item_data in category["items"].items():
        # 創建標籤
        tags = []
        if item_data.get("is_popular"):
            tags.append({"text": "🔥 熱門", "color": "#FF6B6B"})
        if item_data.get("is_healthy"):
            tags.append({"text": "🥗 健康", "color": "#32CD32"})
        if item_data.get("is_vegetarian"):
            tags.append({"text": "🌱 素食", "color": "#90EE90"})
        if item_data.get("discount", 0) > 0:
            tags.append({"text": f"💰 -{item_data['discount']}%", "color": "#FFA500"})
        
        # 計算折扣後價格
        original_price = item_data["price"]
        discount = item_data.get("discount", 0)
        final_price = original_price * (100 - discount) // 100 if discount > 0 else original_price
        
        # 創建標籤內容
        tag_contents = []
        for tag in tags[:2]:  # 最多顯示2個標籤
            tag_contents.append(
                BoxComponent(
                    layout="vertical",
                    contents=[
                        TextComponent(
                            text=tag["text"],
                            size="xxs",
                            color="white",
                            weight="bold"
                        )
                    ],
                    backgroundColor=tag["color"],
                    cornerRadius="2px",
                    paddingAll="4px"
                )
            )
        
        # 建構商品詳細資訊
        details = []
        if "calories" in item_data:
            details.append(f"🔥 {item_data['calories']} 大卡")
        if "spicy_level" in item_data and item_data["spicy_level"] > 0:
            spicy = "🌶️" * min(item_data["spicy_level"], 3)
            details.append(f"{spicy} 辣度")
        if "caffeine" in item_data:
            details.append(f"☕ 咖啡因{item_data['caffeine']}")
            
        detail_text = " • ".join(details) if details else ""
        
        bubble = BubbleContainer(
            size="kilo",
            hero=BoxComponent(
                layout="vertical",
                contents=[
                    ImageComponent(
                        url=item_data["image"],
                        size="full",
                        aspectMode="cover",
                        aspectRatio="4:3"
                    ),
                    BoxComponent(
                        layout="horizontal",
                        contents=tag_contents,
                        spacing="xs",
                        position="absolute",
                        offsetTop="8px",
                        offsetStart="8px"
                    ) if tag_contents else SpacerComponent(size="none")
                ]
            ),
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text=item_data["name"],
                        weight="bold",
                        size="lg",
                        color="#333333"
                    ),
                    TextComponent(
                        text=item_data["desc"],
                        size="sm",
                        color="#666666",
                        wrap=True,
                        margin="xs"
                    ),
                    TextComponent(
                        text=detail_text,
                        size="xs",
                        color="#999999",
                        wrap=True,
                        margin="sm"
                    ) if detail_text else SpacerComponent(size="none"),
                    SeparatorComponent(margin="md"),
                    BoxComponent(
                        layout="baseline",
                        contents=[
                            BoxComponent(
                                layout="vertical",
                                contents=[
                                    TextComponent(
                                        text=f"NT$ {original_price}",
                                        size="sm",
                                        color="#999999",
                                        decoration="line-through" if discount > 0 else "none"
                                    ) if discount > 0 else SpacerComponent(size="none"),
                                    TextComponent(
                                        text=f"NT$ {final_price}",
                                        size="lg",
                                        weight="bold",
                                        color="#FF6B6B"
                                    )
                                ],
                                flex=3
                            ),
                            ButtonComponent(
                                style="primary",
                                color="#FF6B6B",
                                height="sm",
                                flex=2,
                                action=PostbackAction(
                                    label="加入購物車",
                                    data=f"action=add_to_cart&category={category_id}&item={item_name}"
                                )
                            )
                        ],
                        spacing="sm"
                    )
                ],
                spacing="sm",
                paddingAll="15px"
            )
        )
        bubbles.append(bubble)
    
    # 將商品分組，每組最多10個
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

# 查看增強版購物車
def view_enhanced_cart(user_id):
    if user_id not in user_carts or not user_carts[user_id]["items"]:
        empty_cart_bubble = BubbleContainer(
            body=BoxComponent(
                layout="vertical",
                contents=[
                    BoxComponent(
                        layout="vertical",
                        contents=[
                            TextComponent(
                                text="🛒",
                                size="4xl",
                                align="center",
                                color="#CCCCCC"
                            ),
                            TextComponent(
                                text="購物車是空的",
                                size="xl",
                                weight="bold",
                                align="center",
                                color="#666666",
                                margin="md"
                            ),
                            TextComponent(
                                text="快去選購美味餐點吧！",
                                size="md",
                                align="center",
                                color="#999999",
                                margin="md"
                            )
                        ],
                        spacing="md",
                        paddingAll="40px"
                    )
                ]
            ),
            footer=BoxComponent(
                layout="vertical",
                contents=[
                    ButtonComponent(
                        style="primary",
                        color="#FF6B6B",
                        action=PostbackAction(
                            label="🍽️ 開始點餐",
                            data="action=view_categories"
                        )
                    )
                ]
            )
        )
        
        return FlexSendMessage(
            alt_text="空購物車",
            contents=empty_cart_bubble
        )
    
    cart = user_carts[user_id]
    total = 0
    total_items = 0
    item_contents = []
    
    for idx, item in enumerate(cart["items"]):
        # 計算折扣
        original_price = item["price"]
        discount = 0
        
        # 查找商品詳細資訊獲取折扣
        for category in MENU.values():
            if item["name"] in category["items"]:
                discount = category["items"][item["name"]].get("discount", 0)
                break
        
        final_price = original_price * (100 - discount) // 100 if discount > 0 else original_price
        item_total = final_price * item["quantity"]
        total += item_total
        total_items += item["quantity"]
        
        # 創建商品行
        item_row = BoxComponent(
            layout="horizontal",
            contents=[
                BoxComponent(
                    layout="vertical",
                    contents=[
                        TextComponent(
                            text=item["name"],
                            size="sm",
                            weight="bold",
                            color="#333333"
                        ),
                        TextComponent(
                            text=f"NT$ {final_price} × {item['quantity']}",
                            size="xs",
                            color="#666666"
                        )
                    ],
                    flex=4
                ),
                TextComponent(
                    text=f"NT$ {item_total}",
                    size="sm",
                    weight="bold",
                    color="#FF6B6B",
                    align="end",
                    flex=1
                )
            ],
            paddingAll="8px",
            backgroundColor="#F8F8F8",
            cornerRadius="5px",
            spacing="md"
        )
        item_contents.append(item_row)
    
    # 計算運費
    delivery_fee = store_info["delivery_fee"] if total >= store_info["min_order"] else store_info["delivery_fee"]
    free_delivery = total >= store_info["min_order"]
    final_total = total + (0 if free_delivery else delivery_fee)
    
    bubble = BubbleContainer(
        header=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="🛒 購物車",
                    weight="bold",
                    size="xl",
                    color="white"
                ),
                TextComponent(
                    text=f"{total_items} 項商品",
                    size="sm",
                    color="white",
                    margin="xs"
                )
            ],
            backgroundColor="#FF6B6B",
            paddingAll="20px"
        ),
        body=BoxComponent(
            layout="vertical",
            contents=[
                BoxComponent(
                    layout="vertical",
                    contents=item_contents,
                    spacing="sm"
                ),
                SeparatorComponent(margin="lg"),
                BoxComponent(
                    layout="vertical",
                    contents=[
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                TextComponent(
                                    text="小計",
                                    size="sm",
                                    color="#666666",
                                    flex=3
                                ),
                                TextComponent(
                                    text=f"NT$ {total}",
                                    size="sm",
                                    color="#333333",
                                    align="end",
                                    flex=1
                                )
                            ]
                        ),
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                TextComponent(
                                    text="運費",
                                    size="sm",
                                    color="#666666",
                                    flex=3
                                ),
                                TextComponent(
                                    text="免運費" if free_delivery else f"NT$ {delivery_fee}",
                                    size="sm",
                                    color="#32CD32" if free_delivery else "#333333",
                                    align="end",
                                    flex=1
                                )
                            ]
                        ),
                        SeparatorComponent(margin="md"),
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                TextComponent(
                                    text="總計",
                                    size="lg",
                                    weight="bold",
                                    color="#333333",
                                    flex=3
                                ),
                                TextComponent(
                                    text=f"NT$ {final_total}",
                                    size="lg",
                                    weight="bold",
                                    color="#FF6B6B",
                                    align="end",
                                    flex=1
                                )
                            ]
                        )
                    ],
                    spacing="sm",
                    margin="lg"
                ),
                BoxComponent(
                    layout="vertical",
                    contents=[
                        TextComponent(
                            text=f"💡 再消費 NT$ {max(0, store_info['min_order'] - total)} 即可免運費！",
                            size="xs",
                            color="#FFA500",
                            wrap=True,
                            align="center"
                        )
                    ],
                    margin="lg",
                    backgroundColor="#FFF8E1",
                    cornerRadius="5px",
                    paddingAll="10px"
                ) if not free_delivery and total > 0 else SpacerComponent(size="none")
            ],
            spacing="none",
            paddingAll="20px"
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="sm",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#FF6B6B",
                    action=PostbackAction(
                        label="✅ 確認訂單",
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
    
    return FlexSendMessage(
        alt_text="購物車內容",
        contents=bubble
    )

# 創建訂單確認模板
def create_enhanced_order_confirmation(user_id):
    if user_id not in user_carts or not user_carts[user_id]["items"]:
        return None
        
    cart = user_carts[user_id]
    total = 0
    total_items = 0
    
    for item in cart["items"]:
        # 計算折扣後價格
        original_price = item["price"]
        discount = 0
        
        for category in MENU.values():
            if item["name"] in category["items"]:
                discount = category["items"][item["name"]].get("discount", 0)
                break
        
        final_price = original_price * (100 - discount) // 100 if discount > 0 else original_price
        total += final_price * item["quantity"]
        total_items += item["quantity"]
    
    delivery_fee = 0 if total >= store_info["min_order"] else store_info["delivery_fee"]
    final_total = total + delivery_fee
    order_id = generate_order_id()
    
    # 預估準備時間
    prep_time = max(15, total_items * 3)  # 基礎15分鐘 + 每項商品3分鐘
    estimated_time = (datetime.now() + timedelta(minutes=prep_time)).strftime("%H:%M")
    
    bubble = BubbleContainer(
        header=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="✅ 訂單確認",
                    weight="bold",
                    size="xl",
                    color="white"
                ),
                TextComponent(
                    text=f"訂單編號：{order_id}",
                    size="sm",
                    color="white",
                    margin="xs"
                )
            ],
            backgroundColor="#32CD32",
            paddingAll="20px"
        ),
        body=BoxComponent(
            layout="vertical",
            contents=[
                BoxComponent(
                    layout="horizontal",
                    contents=[
                        BoxComponent(
                            layout="vertical",
                            contents=[
                                TextComponent(
                                    text="📍 取餐地址",
                                    size="sm",
                                    weight="bold",
                                    color="#333333"
                                ),
                                TextComponent(
                                    text=store_info["address"],
                                    size="xs",
                                    color="#666666",
                                    wrap=True
                                )
                            ],
                            flex=3
                        ),
                        BoxComponent(
                            layout="vertical",
                            contents=[
                                TextComponent(
                                    text="⏰ 預估時間",
                                    size="sm",
                                    weight="bold",
                                    color="#333333"
                                ),
                                TextComponent(
                                    text=f"{estimated_time}",
                                    size="sm",
                                    color="#FF6B6B",
                                    weight="bold"
                                )
                            ],
                            flex=2
                        )
                    ],
                    spacing="md",
                    backgroundColor="#F8F8F8",
                    cornerRadius="8px",
                    paddingAll="15px"
                ),
                SeparatorComponent(margin="lg"),
                BoxComponent(
                    layout="vertical",
                    contents=[
                        TextComponent(
                            text="📋 訂單明細",
                            size="md",
                            weight="bold",
                            color="#333333"
                        )
                    ] + [
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                TextComponent(
                                    text=f"{item['name']} × {item['quantity']}",
                                    size="sm",
                                    color="#666666",
                                    flex=3
                                ),
                                TextComponent(
                                    text=f"NT$ {item['price'] * item['quantity']}",
                                    size="sm",
                                    color="#333333",
                                    align="end",
                                    flex=1
                                )
                            ],
                            spacing="sm"
                        ) for item in cart["items"]
                    ],
                    spacing="sm",
                    margin="md"
                ),
                SeparatorComponent(margin="lg"),
                BoxComponent(
                    layout="baseline",
                    contents=[
                        TextComponent(
                            text="💰 總金額",
                            size="lg",
                            weight="bold",
                            color="#333333",
                            flex=3
                        ),
                        TextComponent(
                            text=f"NT$ {final_total}",
                            size="lg",
                            weight="bold",
                            color="#FF6B6B",
                            align="end",
                            flex=1
                        )
                    ]
                )
            ],
            spacing="none",
            paddingAll="20px"
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="sm",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#32CD32",
                    action=PostbackAction(
                        label="💳 確認付款",
                        data=f"action=checkout&order_id={order_id}"
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
                                label="✏️ 修改訂單",
                                data="action=edit_cart"
                            )
                        ),
                        ButtonComponent(
                            style="secondary",
                            height="sm",
                            flex=1,
                            action=PostbackAction(
                                label="❌ 取消訂單",
                                data="action=cancel_order"
                            )
                        )
                    ]
                )
            ]
        )
    )
    
    return FlexSendMessage(
        alt_text="訂單確認",
        contents=bubble
    )

# 查看今日推薦
def create_daily_special():
    # 隨機選擇推薦商品
    all_popular_items = []
    for category_id, category in MENU.items():
        for item_name, item_data in category["items"].items():
            if item_data.get("is_popular", False) or item_data.get("discount", 0) > 0:
                all_popular_items.append({
                    "category_id": category_id,
                    "name": item_name,
                    "data": item_data
                })
    
    selected_items = random.sample(all_popular_items, min(3, len(all_popular_items)))
    
    bubbles = []
    for item in selected_items:
        discount = item["data"].get("discount", 0)
        original_price = item["data"]["price"]
        final_price = original_price * (100 - discount) // 100 if discount > 0 else original_price
        
        bubble = BubbleContainer(
            size="kilo",
            hero=ImageComponent(
                url=item["data"]["image"],
                size="full",
                aspectMode="cover",
                aspectRatio="4:3"
            ),
            body=BoxComponent(
                layout="vertical",
                contents=[
                    BoxComponent(
                        layout="horizontal",
                        contents=[
                            TextComponent(
                                text="⭐ 今日推薦",
                                size="xs",
                                color="white",
                                weight="bold"
                            )
                        ],
                        backgroundColor="#FF6B6B",
                        cornerRadius="2px",
                        paddingAll="4px"
                    ),
                    TextComponent(
                        text=item["data"]["name"],
                        weight="bold",
                        size="md",
                        color="#333333",
                        margin="md"
                    ),
                    TextComponent(
                        text=item["data"]["desc"],
                        size="sm",
                        color="#666666",
                        wrap=True
                    ),
                    BoxComponent(
                        layout="baseline",
                        contents=[
                            TextComponent(
                                text=f"特價 NT$ {final_price}",
                                size="lg",
                                weight="bold",
                                color="#FF6B6B",
                                flex=3
                            ),
                            TextComponent(
                                text=f"NT$ {original_price}",
                                size="sm",
                                color="#999999",
                                decoration="line-through",
                                align="end",
                                flex=1
                            ) if discount > 0 else SpacerComponent(size="none")
                        ],
                        spacing="sm",
                        margin="md"
                    )
                ],
                spacing="sm",
                paddingAll="15px"
            ),
            footer=BoxComponent(
                layout="vertical",
                contents=[
                    ButtonComponent(
                        style="primary",
                        color="#FF6B6B",
                        action=PostbackAction(
                            label="立即訂購",
                            data=f"action=add_to_cart&category={item['category_id']}&item={item['name']}"
                        )
                    )
                ]
            )
        )
        bubbles.append(bubble)
    
    return FlexSendMessage(
        alt_text="今日推薦",
        contents={
            "type": "carousel",
            "contents": bubbles
        }
    )

# 店家資訊
def create_store_info():
    bubble = BubbleContainer(
        hero=ImageComponent(
            url="https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800&h=400&fit=crop",
            size="full",
            aspectRatio="20:13",
            aspectMode="cover"
        ),
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text=store_info["name"],
                    weight="bold",
                    size="xl",
                    color="#FF6B6B"
                ),
                SeparatorComponent(margin="md"),
                BoxComponent(
                    layout="vertical",
                    contents=[
                        BoxComponent(
                            layout="baseline",
                            spacing="sm",
                            contents=[
                                IconComponent(
                                    url="https://cdn-icons-png.flaticon.com/512/684/684908.png",
                                    size="sm"
                                ),
                                TextComponent(
                                    text=f"營業時間：{store_info['hours']}",
                                    size="sm",
                                    color="#666666",
                                    flex=4
                                )
                            ]
                        ),
                        BoxComponent(
                            layout="baseline",
                            spacing="sm",
                            contents=[
                                IconComponent(
                                    url="https://cdn-icons-png.flaticon.com/512/535/535239.png",
                                    size="sm"
                                ),
                                TextComponent(
                                    text=f"電話：{store_info['phone']}",
                                    size="sm",
                                    color="#666666",
                                    flex=4
                                )
                            ]
                        ),
                        BoxComponent(
                            layout="baseline",
                            spacing="sm",
                            contents=[
                                IconComponent(
                                    url="https://cdn-icons-png.flaticon.com/512/484/484167.png",
                                    size="sm"
                                ),
                                TextComponent(
                                    text=f"地址：{store_info['address']}",
                                    size="sm",
                                    color="#666666",
                                    wrap=True,
                                    flex=4
                                )
                            ]
                        ),
                        BoxComponent(
                            layout="baseline",
                            spacing="sm",
                            contents=[
                                IconComponent(
                                    url="https://cdn-icons-png.flaticon.com/512/732/732200.png",
                                    size="sm"
                                ),
                                TextComponent(
                                    text=f"外送費：NT$ {store_info['delivery_fee']} (滿 ${store_info['min_order']} 免運)",
                                    size="sm",
                                    color="#666666",
                                    wrap=True,
                                    flex=4
                                )
                            ]
                        )
                    ],
                    spacing="md",
                    margin="lg"
                )
            ]
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="sm",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#FF6B6B",
                    action=PostbackAction(
                        label="📞 聯絡我們",
                        data="action=contact_us"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    action=PostbackAction(
                        label="🍽️ 開始點餐",
                        data="action=view_categories"
                    )
                )
            ]
        )
    )
    
    return FlexSendMessage(
        alt_text="店家資訊",
        contents=bubble
    )

# 首頁
@app.route("/")
def index():
    return render_template("index.html", menu=MENU)

# 管理後台
@app.route("/admin")
def admin():
    return render_template("admin.html", orders=user_orders, store_info=store_info)

# API 端點 - 更新訂單狀態
@app.route("/api/update_order_status", methods=['POST'])
def update_order_status():
    data = request.json
    user_id = data.get('user_id')
    order_id = data.get('order_id')
    new_status = data.get('status')
    
    if user_id in user_orders:
        for order in user_orders[user_id]:
            if order['id'] == order_id:
                order['status'] = new_status
                order['updated_at'] = datetime.now().isoformat()
                
                # 推送狀態更新通知給用戶
                status_info = ORDER_STATUS.get(new_status, {"name": "未知", "emoji": "❓"})
                notification_text = f"{status_info['emoji']} 您的訂單 #{order_id} 狀態已更新為：{status_info['name']}"
                
                line_bot_api.push_message(
                    user_id,
                    TextSendMessage(
                        text=notification_text,
                        quick_reply=create_enhanced_quick_reply()
                    )
                )
                
                return jsonify({"success": True})
    
    return jsonify({"success": False})

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
    
    if text in ["點餐", "menu", "菜單", "開始"]:
        reply_message = create_enhanced_categories_menu()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text in ["購物車", "cart", "我的購物車"]:
        reply_message = view_enhanced_cart(user_id)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text in ["訂單", "orders", "我的訂單"]:
        view_enhanced_orders(event, user_id)
        
    elif text in ["推薦", "today", "今日推薦", "特價"]:
        reply_message = create_daily_special()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text in ["店家", "資訊", "info", "店家資訊"]:
        reply_message = create_store_info()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif text in ["幫助", "help", "客服"]:
        help_message = create_help_message()
        line_bot_api.reply_message(event.reply_token, help_message)
        
    else:
        # 智能回覆 - 根據關鍵詞推薦
        if any(keyword in text for keyword in ["漢堡", "堡", "burger"]):
            reply_message = create_category_suggestion("main")
        elif any(keyword in text for keyword in ["飲料", "喝", "drink", "可樂", "咖啡"]):
            reply_message = create_category_suggestion("drink")
        elif any(keyword in text for keyword in ["薯條", "雞塊", "副餐", "side"]):
            reply_message = create_category_suggestion("side")
        elif any(keyword in text for keyword in ["甜點", "dessert", "蛋糕"]):
            reply_message = create_category_suggestion("dessert")
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
        reply_message = create_enhanced_categories_menu()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'view_menu':
        category_id = data_dict.get('category', '')
        menu_messages = create_enhanced_menu_template(category_id)
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
        add_to_enhanced_cart(event, user_id, category_id, item_name)
        
    elif action == 'view_cart':
        reply_message = view_enhanced_cart(user_id)
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'confirm_order':
        reply_message = create_enhanced_order_confirmation(user_id)
        if reply_message:
            line_bot_api.reply_message(event.reply_token, reply_message)
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="您的購物車是空的，無法建立訂單",
                    quick_reply=create_enhanced_quick_reply()
                )
            )
            
    elif action == 'checkout':
        order_id = data_dict.get('order_id', '')
        enhanced_checkout_order(event, user_id, order_id)
        
    elif action == 'view_orders':
        view_enhanced_orders(event, user_id)
        
    elif action == 'daily_special':
        reply_message = create_daily_special()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'store_info':
        reply_message = create_store_info()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'customer_service':
        reply_message = create_customer_service()
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    elif action == 'go_home':
        welcome_message = create_welcome_message()
        line_bot_api.reply_message(event.reply_token, welcome_message)

# 新增功能函數

# 創建分類建議
def create_category_suggestion(category_id):
    if category_id not in MENU:
        return create_welcome_message()
    
    category = MENU[category_id]
    popular_items = [(name, data) for name, data in category["items"].items() if data.get("is_popular", False)]
    
    if not popular_items:
        popular_items = list(category["items"].items())[:3]
    
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text=f"為您推薦 {category['name']}",
                    weight="bold",
                    size="lg",
                    color="#FF6B6B"
                ),
                SeparatorComponent(margin="md")
            ] + [
                BoxComponent(
                    layout="baseline",
                    contents=[
                        TextComponent(
                            text=f"• {item[1]['name']}",
                            size="sm",
                            color="#333333",
                            flex=3
                        ),
                        TextComponent(
                            text=f"NT$ {item[1]['price']}",
                            size="sm",
                            color="#666666",
                            align="end",
                            flex=1
                        )
                    ]
                ) for item in popular_items[:3]
            ],
            spacing="sm"
        ),
        footer=BoxComponent(
            layout="vertical",
            contents=[
                ButtonComponent(
                    style="primary",
                    color=category["color"],
                    action=PostbackAction(
                        label=f"瀏覽所有{category['name']}",
                        data=f"action=view_menu&category={category_id}"
                    )
                )
            ]
        )
    )
    
    return FlexSendMessage(
        alt_text=f"{category['name']} 推薦",
        contents=bubble
    )

# 創建客服訊息
def create_customer_service():
    bubble = BubbleContainer(
        header=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="🎯 客服中心",
                    weight="bold",
                    size="xl",
                    color="white"
                ),
                TextComponent(
                    text="我們很樂意為您服務！",
                    size="sm",
                    color="white",
                    margin="xs"
                )
            ],
            backgroundColor="#4ECDC4",
            paddingAll="20px"
        ),
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="聯絡方式",
                    weight="bold",
                    size="md",
                    color="#333333"
                ),
                SeparatorComponent(margin="md"),
                BoxComponent(
                    layout="baseline",
                    contents=[
                        TextComponent(
                            text="📞 客服專線",
                            size="sm",
                            color="#666666",
                            flex=2
                        ),
                        TextComponent(
                            text=store_info["phone"],
                            size="sm",
                            color="#333333",
                            flex=3
                        )
                    ],
                    spacing="sm"
                ),
                BoxComponent(
                    layout="baseline",
                    contents=[
                        TextComponent(
                            text="⏰ 服務時間",
                            size="sm",
                            color="#666666",
                            flex=2
                        ),
                        TextComponent(
                            text=store_info["hours"],
                            size="sm",
                            color="#333333",
                            flex=3
                        )
                    ],
                    spacing="sm",
                    margin="md"
                ),
                SeparatorComponent(margin="lg"),
                TextComponent(
                    text="常見問題",
                    weight="bold",
                    size="md",
                    color="#333333",
                    margin="lg"
                ),
                TextComponent(
                    text="• 如何修改訂單？\n• 外送時間多久？\n• 如何取消訂單？\n• 付款方式說明",
                    size="sm",
                    color="#666666",
                    wrap=True,
                    margin="sm"
                )
            ],
            spacing="sm",
            paddingAll="20px"
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="sm",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#4ECDC4",
                    action=PostbackAction(
                        label="📞 立即聯絡",
                        data="action=contact_us"
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    action=PostbackAction(
                        label="❓ 常見問題",
                        data="action=faq"
                    )
                )
            ]
        )
    )
    
    return FlexSendMessage(
        alt_text="客服中心",
        contents=bubble
    )

# 創建幫助訊息
def create_help_message():
    bubble = BubbleContainer(
        header=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="📚 使用說明",
                    weight="bold",
                    size="xl",
                    color="white"
                ),
                TextComponent(
                    text="讓我們教您如何使用！",
                    size="sm",
                    color="white",
                    margin="xs"
                )
            ],
            backgroundColor="#9B59B6",
            paddingAll="20px"
        ),
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="🎮 基本操作",
                    weight="bold",
                    size="md",
                    color="#333333"
                ),
                SeparatorComponent(margin="md"),
                TextComponent(
                    text="• 輸入「點餐」或「菜單」開始點餐\n• 輸入「購物車」查看已選商品\n• 輸入「訂單」查看訂單狀態\n• 輸入「推薦」查看今日特價",
                    size="sm",
                    color="#666666",
                    wrap=True,
                    margin="sm"
                ),
                SeparatorComponent(margin="lg"),
                TextComponent(
                    text="⚡ 快速功能",
                    weight="bold",
                    size="md",
                    color="#333333",
                    margin="lg"
                ),
                TextComponent(
                    text="使用下方快速按鈕可以更方便地操作：",
                    size="sm",
                    color="#666666",
                    margin="sm"
                ),
                BoxComponent(
                    layout="vertical",
                    contents=[
                        TextComponent(text="📋 瀏覽菜單 - 查看所有商品分類", size="xs", color="#999999"),
                        TextComponent(text="🛒 購物車 - 管理已選商品", size="xs", color="#999999"),
                        TextComponent(text="📦 我的訂單 - 追蹤訂單狀態", size="xs", color="#999999"),
                        TextComponent(text="⭐ 今日推薦 - 查看特價商品", size="xs", color="#999999"),
                        TextComponent(text="ℹ️ 店家資訊 - 聯絡方式與營業時間", size="xs", color="#999999"),
                        TextComponent(text="🎯 客服 - 獲得協助", size="xs", color="#999999")
                    ],
                    spacing="xs",
                    margin="sm"
                ),
                SeparatorComponent(margin="lg"),
                TextComponent(
                    text="💡 小貼士",
                    weight="bold",
                    size="md",
                    color="#333333",
                    margin="lg"
                ),
                BoxComponent(
                    layout="vertical",
                    contents=[
                        TextComponent(
                            text="• 滿 $100 免外送費",
                            size="sm",
                            color="#32CD32"
                        ),
                        TextComponent(
                            text="• 注意營業時間：" + store_info["hours"],
                            size="sm",
                            color="#666666"
                        ),
                        TextComponent(
                            text="• 訂單完成後會自動通知",
                            size="sm",
                            color="#666666"
                        )
                    ],
                    spacing="sm",
                    margin="sm"
                )
            ],
            spacing="none",
            paddingAll="20px"
        ),
        footer=BoxComponent(
            layout="vertical",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#9B59B6",
                    action=PostbackAction(
                        label="🍽️ 開始點餐",
                        data="action=view_categories"
                    )
                )
            ]
        )
    )
    
    return FlexSendMessage(
        alt_text="使用說明",
        contents=bubble
    )

# 增強版添加到購物車
def add_to_enhanced_cart(event, user_id, category_id, item_name):
    if category_id not in MENU or item_name not in MENU[category_id]["items"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="抱歉，找不到該商品 😅")
        )
        return
    
    # 初始化用戶購物車
    if user_id not in user_carts:
        user_carts[user_id] = {
            "items": [],
            "updated_at": datetime.now().isoformat()
        }
    
    item_data = MENU[category_id]["items"][item_name]
    cart = user_carts[user_id]
    
    # 檢查商品是否已在購物車中
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
            "category": category_id,
            "image": item_data.get("image", "")
        })
    
    cart["updated_at"] = datetime.now().isoformat()
    
    # 計算購物車總數量
    total_items = sum(item["quantity"] for item in cart["items"])
    
    # 創建成功添加的回覆
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                BoxComponent(
                    layout="horizontal",
                    contents=[
                        TextComponent(
                            text="✅",
                            size="xl",
                            color="#32CD32"
                        ),
                        BoxComponent(
                            layout="vertical",
                            contents=[
                                TextComponent(
                                    text="已加入購物車！",
                                    weight="bold",
                                    size="md",
                                    color="#333333"
                                ),
                                TextComponent(
                                    text=f"{item_name} × 1",
                                    size="sm",
                                    color="#666666"
                                )
                            ],
                            flex=4
                        )
                    ],
                    spacing="md",
                    paddingAll="15px",
                    backgroundColor="#F0FFF0",
                    cornerRadius="8px"
                ),
                BoxComponent(
                    layout="baseline",
                    contents=[
                        TextComponent(
                            text=f"🛒 購物車共 {total_items} 件商品",
                            size="sm",
                            color="#666666",
                            flex=3
                        ),
                        TextComponent(
                            text="繼續購物 →",
                            size="sm",
                            color="#FF6B6B",
                            align="end",
                            flex=1
                        )
                    ],
                    spacing="sm",
                    margin="lg"
                )
            ],
            spacing="sm",
            paddingAll="20px"
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="sm",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#FF6B6B",
                    action=PostbackAction(
                        label="🛒 查看購物車",
                        data="action=view_cart"
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
                                label="🍽️ 繼續點餐",
                                data="action=view_categories"
                            )
                        ),
                        ButtonComponent(
                            style="secondary",
                            height="sm",
                            flex=1,
                            action=PostbackAction(
                                label="⭐ 查看推薦",
                                data="action=daily_special"
                            )
                        )
                    ]
                )
            ]
        )
    )
    
    template_message = FlexSendMessage(
        alt_text="已加入購物車",
        contents=bubble
    )
    
    line_bot_api.reply_message(event.reply_token, template_message)

# 增強版結帳
def enhanced_checkout_order(event, user_id, order_id):
    if user_id not in user_carts or not user_carts[user_id]["items"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="您目前沒有訂單可以結帳 🛒",
                quick_reply=create_enhanced_quick_reply()
            )
        )
        return
    
    cart = user_carts[user_id]
    total = 0
    total_items = 0
    
    # 計算總價（含折扣）
    for item in cart["items"]:
        original_price = item["price"]
        discount = 0
        
        # 查找折扣
        for category in MENU.values():
            if item["name"] in category["items"]:
                discount = category["items"][item["name"]].get("discount", 0)
                break
        
        final_price = original_price * (100 - discount) // 100 if discount > 0 else original_price
        total += final_price * item["quantity"]
        total_items += item["quantity"]
    
    delivery_fee = 0 if total >= store_info["min_order"] else store_info["delivery_fee"]
    final_total = total + delivery_fee
    
    # 創建訂單
    if user_id not in user_orders:
        user_orders[user_id] = []
    
    order = {
        "id": order_id,
        "user_id": user_id,
        "items": cart["items"].copy(),
        "subtotal": total,
        "delivery_fee": delivery_fee,
        "total": final_total,
        "status": "confirmed",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "estimated_time": (datetime.now() + timedelta(minutes=max(15, total_items * 3))).isoformat()
    }
    
    user_orders[user_id].append(order)
    
    # 清空購物車
    user_carts[user_id]["items"] = []
    
    # 創建成功訊息
    estimated_time = datetime.fromisoformat(order["estimated_time"]).strftime("%H:%M")
    
    success_bubble = BubbleContainer(
        header=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="🎉 訂單成功！",
                    weight="bold",
                    size="xl",
                    color="white"
                ),
                TextComponent(
                    text="感謝您的訂購",
                    size="sm",
                    color="white",
                    margin="xs"
                )
            ],
            backgroundColor="#32CD32",
            paddingAll="20px"
        ),
        hero=BoxComponent(
            layout="vertical",
            contents=[
                BoxComponent(
                    layout="horizontal",
                    contents=[
                        BoxComponent(
                            layout="vertical",
                            contents=[
                                TextComponent(
                                    text="訂單編號",
                                    size="sm",
                                    color="#666666"
                                ),
                                TextComponent(
                                    text=f"#{order_id}",
                                    size="lg",
                                    weight="bold",
                                    color="#333333"
                                )
                            ],
                            flex=2
                        ),
                        BoxComponent(
                            layout="vertical",
                            contents=[
                                TextComponent(
                                    text="預估完成",
                                    size="sm",
                                    color="#666666"
                                ),
                                TextComponent(
                                    text=estimated_time,
                                    size="lg",
                                    weight="bold",
                                    color="#FF6B6B"
                                )
                            ],
                            flex=2
                        ),
                        BoxComponent(
                            layout="vertical",
                            contents=[
                                TextComponent(
                                    text="總金額",
                                    size="sm",
                                    color="#666666"
                                ),
                                TextComponent(
                                    text=f"NT$ {final_total}",
                                    size="lg",
                                    weight="bold",
                                    color="#32CD32"
                                )
                            ],
                            flex=2
                        )
                    ],
                    spacing="md"
                )
            ],
            backgroundColor="#F8F9FA",
            paddingAll="20px"
        ),
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="📋 訂單狀態追蹤",
                    weight="bold",
                    size="md",
                    color="#333333"
                ),
                BoxComponent(
                    layout="vertical",
                    contents=[
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                TextComponent(text="✅", size="sm"),
                                TextComponent(text="訂單確認", size="sm", color="#32CD32", weight="bold")
                            ],
                            spacing="sm"
                        ),
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                TextComponent(text="⏳", size="sm"),
                                TextComponent(text="開始製作", size="sm", color="#999999")
                            ],
                            spacing="sm"
                        ),
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                TextComponent(text="🍳", size="sm"),
                                TextComponent(text="準備中", size="sm", color="#999999")
                            ],
                            spacing="sm"
                        ),
                        BoxComponent(
                            layout="baseline",
                            contents=[
                                TextComponent(text="🎉", size="sm"),
                                TextComponent(text="完成", size="sm", color="#999999")
                            ],
                            spacing="sm"
                        )
                    ],
                    spacing="sm",
                    margin="md",
                    backgroundColor="#F8F9FA",
                    paddingAll="15px",
                    cornerRadius="8px"
                ),
                TextComponent(
                    text="我們會在訂單狀態更新時通知您！",
                    size="sm",
                    color="#666666",
                    align="center",
                    margin="lg"
                )
            ],
            spacing="sm",
            paddingAll="20px"
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="sm",
            contents=[
                ButtonComponent(
                    style="primary",
                    color="#32CD32",
                    action=PostbackAction(
                        label="📦 追蹤訂單",
                        data="action=view_orders"
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
                                label="🍽️ 再次點餐",
                                data="action=view_categories"
                            )
                        ),
                        ButtonComponent(
                            style="secondary",
                            height="sm",
                            flex=1,
                            action=PostbackAction(
                                label="🏠 回首頁",
                                data="action=go_home"
                            )
                        )
                    ]
                )
            ]
        )
    )
    
    line_bot_api.reply_message(
        event.reply_token,
        FlexSendMessage(
            alt_text="訂單成功",
            contents=success_bubble
        )
    )

# 查看增強版訂單
def view_enhanced_orders(event, user_id):
    if user_id not in user_orders or not user_orders[user_id]:
        empty_orders_bubble = BubbleContainer(
            body=BoxComponent(
                layout="vertical",
                contents=[
                    BoxComponent(
                        layout="vertical",
                        contents=[
                            TextComponent(
                                text="📦",
                                size="4xl",
                                align="center",
                                color="#CCCCCC"
                            ),
                            TextComponent(
                                text="還沒有訂單",
                                size="xl",
                                weight="bold",
                                align="center",
                                color="#666666",
                                margin="md"
                            ),
                            TextComponent(
                                text="快來點些美味的餐點吧！",
                                size="md",
                                align="center",
                                color="#999999",
                                margin="md"
                            )
                        ],
                        spacing="md",
                        paddingAll="40px"
                    )
                ]
            ),
            footer=BoxComponent(
                layout="vertical",
                contents=[
                    ButtonComponent(
                        style="primary",
                        color="#FF6B6B",
                        action=PostbackAction(
                            label="🍽️ 立即點餐",
                            data="action=view_categories"
                        )
                    )
                ]
            )
        )
        
        line_bot_api.reply_message(
            event.reply_token,
            FlexSendMessage(
                alt_text="空訂單列表",
                contents=empty_orders_bubble
            )
        )
        return
    
    orders = user_orders[user_id]
    bubbles = []
    
    # 按時間排序，最新的在前
    sorted_orders = sorted(orders, key=lambda x: x["created_at"], reverse=True)
    
    for order in sorted_orders[:10]:  # 最多顯示10筆訂單
        status_info = ORDER_STATUS.get(order["status"], {"name": "未知狀態", "emoji": "❓", "color": "#999999"})
        created_time = datetime.fromisoformat(order["created_at"]).strftime("%m/%d %H:%M")
        
        # 計算進度條
        progress = {
            "pending": 25,
            "confirmed": 25,
            "preparing": 75,
            "ready": 100,
            "delivered": 100,
            "cancelled": 0
        }.get(order["status"], 25)
        
        # 建立商品列表
        items_text = []
        for item in order["items"][:3]:  # 最多顯示3個商品
            items_text.append(f"• {item['name']} × {item['quantity']}")
        
        if len(order["items"]) > 3:
            items_text.append(f"...等 {len(order['items'])} 項商品")
        
        bubble = BubbleContainer(
            size="kilo",
            header=BoxComponent(
                layout="horizontal",
                contents=[
                    BoxComponent(
                        layout="vertical",
                        contents=[
                            TextComponent(
                                text=f"訂單 #{order['id']}",
                                weight="bold",
                                size="sm",
                                color="white"
                            ),
                            TextComponent(
                                text=created_time,
                                size="xs",
                                color="white",
                                margin="xs"
                            )
                        ],
                        flex=3
                    ),
                    BoxComponent(
                        layout="vertical",
                        contents=[
                            TextComponent(
                                text=status_info["emoji"],
                                size="lg",
                                align="end"
                            ),
                            TextComponent(
                                text=status_info["name"],
                                size="xs",
                                color="white",
                                align="end"
                            )
                        ],
                        flex=1
                    )
                ],
                backgroundColor=status_info["color"],
                paddingAll="15px"
            ),
            body=BoxComponent(
                layout="vertical",
                contents=[
                    # 進度條
                    BoxComponent(
                        layout="vertical",
                        contents=[
                            BoxComponent(
                                layout="horizontal",
                                contents=[
                                    FillerComponent(flex=progress),
                                    FillerComponent(flex=100-progress)
                                ],
                                backgroundColor="#E0E0E0",
                                height="4px",
                                cornerRadius="2px"
                            )
                        ],
                        margin="sm"
                    ) if order["status"] != "cancelled" else SpacerComponent(size="none"),
                    
                    # 商品列表
                    BoxComponent(
                        layout="vertical",
                        contents=[
                            TextComponent(
                                text="\n".join(items_text),
                                size="sm",
                                color="#666666",
                                wrap=True
                            )
                        ],
                        margin="md"
                    ),
                    
                    # 金額資訊
                    SeparatorComponent(margin="md"),
                    BoxComponent(
                        layout="baseline",
                        contents=[
                            TextComponent(
                                text="總金額:",
                                color="#666666",
                                size="sm",
                                flex=2
                            ),
                            TextComponent(
                                text=f"NT$ {order['total']}",
                                size="sm",
                                color="#333333",
                                weight="bold",
                                align="end",
                                flex=1
                            )
                        ],
                        spacing="sm",
                        margin="sm"
                    )
                ],
                paddingAll="15px"
            ),
            footer=BoxComponent(
                layout="horizontal",
                spacing="sm",
                contents=[
                    ButtonComponent(
                        style="secondary",
                        height="sm",
                        flex=1,
                        action=PostbackAction(
                            label="📋 詳細",
                            data=f"action=order_detail&order_id={order['id']}"
                        )
                    ),
                    ButtonComponent(
                        style="primary",
                        color="#FF6B6B",
                        height="sm",
                        flex=1,
                        action=PostbackAction(
                            label="🔄 再次訂購",
                            data=f"action=reorder&order_id={order['id']}"
                        )
                    ) if order["status"] != "cancelled" else ButtonComponent(
                        style="secondary",
                        height="sm",
                        flex=1,
                        action=PostbackAction(
                            label="❌ 已取消",
                            data="action=none"
                        )
                    )
                ]
            ) if order["status"] in ["ready", "delivered", "cancelled"] else BoxComponent(
                layout="vertical",
                contents=[
                    ButtonComponent(
                        style="secondary",
                        height="sm",
                        action=PostbackAction(
                            label="📋 查看詳細資訊",
                            data=f"action=order_detail&order_id={order['id']}"
                        )
                    )
                ]
            )
        )
        bubbles.append(bubble)
    
    carousel_message = FlexSendMessage(
        alt_text="我的訂單",
        contents={
            "type": "carousel",
            "contents": bubbles
        }
    )
    
    line_bot_api.reply_message(event.reply_token, carousel_message)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
