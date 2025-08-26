from __future__ import annotations
)
finally:
db.close()




# ---------- Admin API（簡易，請自行加上認證） ----------
@app.get("/admin/menu")
def admin_list_menu():
db = SessionLocal()
try:
items = db.query(MenuItem).order_by(MenuItem.category, MenuItem.id).all()
return jsonify([
{
"id": m.id, "name": m.name, "price": m.price,
"category": m.category, "available": m.available, "photo": m.photo
} for m in items
])
finally:
db.close()


@app.post("/admin/menu")
def admin_create_menu():
data = request.json or {}
body = AdminMenuUpsert(**data)
db = SessionLocal()
try:
item = MenuItem(**body.model_dump())
db.add(item)
db.commit()
db.refresh(item)
return jsonify({"ok": True, "id": item.id})
finally:
db.close()


@app.patch("/admin/menu")
def admin_patch_menu():
data = request.json or {}
body = AdminMenuPatch(**data)
db = SessionLocal()
try:
m = db.query(MenuItem).filter_by(id=body.id).first()
if not m:
return jsonify({"ok": False, "error": "not_found"}), 404
for k, v in body.model_dump(exclude_none=True).items():
if k == 'id':
continue
setattr(m, k, v)
db.commit()
return jsonify({"ok": True})
finally:
db.close()


@app.delete("/admin/menu/<int:item_id>")
def admin_delete_menu(item_id: int):
db = SessionLocal()
try:
m = db.query(MenuItem).filter_by(id=item_id).first()
if not m:
return jsonify({"ok": False, "error": "not_found"}), 404
db.delete(m)
db.commit()
return jsonify({"ok": True})
finally:
db.close()



# ---------- 健康檢查 ----------
@app.get("/healthz")
def healthz():
return jsonify({"ok": True, "ts": int(time.time())})



# ---------- 本地啟動 ----------
if __name__ == "__main__":
# 允許 Heroku/Render 類平臺綁定 0.0.0.0
app.run(host="0.0.0.0", port=PORT, debug=True)