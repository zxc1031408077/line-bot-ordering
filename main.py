from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import os
import json
import requests
import hmac
import hashlib
import base64

app = FastAPI()

# LINE Bot Token 與 Secret
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# 簽名驗證
def validate_signature(body, signature):
    hash = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256
    ).digest()
    return hmac.compare_digest(signature, base64.b64encode(hash).decode())

# 訂單存放（簡單存記憶體，重啟就清掉）
orders = {}

# 餐點選單
menu = {
    "1": "牛肉麵",
    "2": "雞排飯",
    "3": "炸豬排套餐",
    "4": "珍珠奶茶"
}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()
    body_text = body.decode("utf-8")

    if LINE_CHANNEL_SECRET:
        if not validate_signature(body_text, signature):
            raise HTTPException(status_code=400, detail="Invalid signature")

    data = json.loads(body_text)

    for event in data.get("events", []):
        if event["type"] == "message" and event["message"]["type"] == "text":
            user_id = event["source"]["userId"]
            text = event["message"]["text"]

            reply_text = handle_order(user_id, text)
            
            reply = {
                "replyToken": event["replyToken"],
                "messages": [{"type": "text", "text": reply_text}]
            }
            requests.post(
                "https://api.line.me/v2/bot/message/reply",
                headers=HEADERS,
                data=json.dumps(reply)
            )
    return JSONResponse(content={"status": "ok"})

def handle_order(user_id, text):
    global orders
    # 顯示菜單
    if text == "菜單":
        return "\n".join([f"{k}. {v}" for k, v in menu.items()]) + "\n請輸入編號下單。"

    # 下單
    elif text in menu:
        if user_id not in orders:
            orders[user_id] = []
        orders[user_id].append(menu[text])
        return f"已加入購物車：{menu[text]}\n輸入「結帳」查看訂單。"

    # 結帳
    elif text == "結帳":
        if user_id in orders and orders[user_id]:
            items = "\n".join(orders[user_id])
            orders[user_id] = []
            return f"你的訂單：\n{items}\n已完成結帳，謝謝！"
        else:
            return "你的購物車是空的。"

    # 其他訊息
    else:
        return "請輸入「菜單」查看餐點。"
