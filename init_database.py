import sqlite3

def init_db():
    conn = sqlite3.connect('restaurant.db')
    c = conn.cursor()
    
    # 創建購物車表
    c.execute('''CREATE TABLE IF NOT EXISTS cart_items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT NOT NULL,
                  item_id INTEGER NOT NULL,
                  quantity INTEGER DEFAULT 1,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(user_id, item_id))''')
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("數據庫初始化完成！")
