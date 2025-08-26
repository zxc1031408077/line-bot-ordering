import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Menu, Order, OrderItem
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, PushMessageRequest
)
from linebot.v3.webhooks import WebhookParser
from linebot.v3.webhooks.models import MessageEvent, TextMessageContent
import uvicorn

# ===== LINE Bot 設定 =====
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
SHOP_OWNER_ID = os.getenv("SHOP_OWNER_ID")  # 老闆 LINE User ID (可改成群組ID)

config = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(CHANNEL_SECRET)

# ===== Database 設定 =====
DATABASE_URL = "sqlite:///./orders.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)

# ===== FastAPI =====
app = FastAPI()


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature")

    try:
        events = parser.parse(body.decode("utf-8"), signature)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    with ApiClient(config) as api_client:
        line_bot_api = MessagingApi(api_client)

        for event in events:
            if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
                user_id = event.source.user_id
                text = event.message.text.strip()

                if text == "/menu":
                    reply_text = "🍔 今日菜單：\n1. 牛肉漢堡 $100\n2. 雞腿漢堡 $90\n3. 薯條 $50\n\n請輸入: add 1 2 (代表點2份牛肉漢堡)"
                elif text.startswith("add "):
                    db = SessionLocal()
                    _, menu_id, qty = text.split()
                    menu_id, qty = int(menu_id), int(qty)

                    order = db.query(Order).filter_by(user_id=user_id, status="cart").first()
                    if not order:
                        order = Order(user_id=user_id, status="cart")
                        db.add(order)
                        db.commit()
                        db.refresh(order)

                    db.add(OrderItem(order_id=order.id, menu_id=menu_id, qty=qty, price=100))  # 簡單假設單價100
                    db.commit()
                    reply_text = f"✅ 已加入購物車：餐點 {menu_id} x {qty}"
                    db.close()
                elif text == "/cart":
                    db = SessionLocal()
                    order = db.query(Order).filter_by(user_id=user_id, status="cart").first()
                    if order and order.items:
                        reply_text = "🛒 你的購物車：\n"
                        for item in order.items:
                            reply_text += f"- {item.menu_id} x {item.qty}\n"
                    else:
                        reply_text = "🛒 購物車是空的"
                    db.close()
                elif text == "/checkout":
                    db = SessionLocal()
                    order = db.query(Order).filter_by(user_id=user_id, status="cart").first()
                    if order and order.items:
                        order.status = "submitted"
                        db.commit()
                        reply_text = "📦 訂單已送出！感謝下單 🙏"

                        # 🔔 推播通知店家
                        order_text = f"🍔 有新訂單！\nUser: {user_id}\n"
                        for item in order.items:
                            order_text += f"- {item.menu_id} x {item.qty}\n"

                        line_bot_api.push_message(
                            PushMessageRequest(
                                to=SHOP_OWNER_ID,
                                messages=[TextMessage(text=order_text)]
                            )
                        )
                    else:
                        reply_text = "⚠️ 購物車是空的，無法結帳"
                    db.close()
                else:
                    reply_text = "請輸入 /menu 查看菜單"

                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)]
                    )
                )

    return JSONResponse(status_code=200, content={"message": "ok"})


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
