import sqlite3
from werkzeug.security import generate_password_hash

def init_database():
    conn = sqlite3.connect('restaurant.db')
    c = conn.cursor()
    
    # 創建菜單分類
    categories = [
        ('推薦餐點', '最受歡迎的餐點組合', 'https://via.placeholder.com/300x200/FF6B6B/FFFFFF?text=推薦餐點', 1),
        ('主餐', '美味主餐', 'https://via.placeholder.com/300x200/4ECDC4/FFFFFF?text=主餐', 2),
        ('副餐', '精選副餐', 'https://via.placeholder.com/300x200/45B7D1/FFFFFF?text=副餐', 3),
        ('飲料', '清涼飲品', 'https://via.placeholder.com/300x200/96CEB4/FFFFFF?text=飲料', 4)
    ]
    
    c.executemany(
        'INSERT INTO menu_categories (name, description, image_url, display_order) VALUES (?, ?, ?, ?)',
        categories
    )
    
    # 獲取分類ID
    c.execute("SELECT id, name FROM menu_categories")
    category_map = {name: id for id, name in c.fetchall()}
    
    # 創建菜單項目
    menu_items = [
        # 推薦餐點
        (category_map['推薦餐點'], '1號餐', '漢堡+薯條+可樂', 120, 'https://via.placeholder.com/300x200/FF6B6B/FFFFFF?text=1號餐', 1, 1, 1),
        (category_map['推薦餐點'], '2號餐', '雙層漢堡+薯條+紅茶', 150, 'https://via.placeholder.com/300x200/4ECDC4/FFFFFF?text=2號餐', 1, 1, 2),
        (category_map['推薦餐點'], '3號餐', '雞腿堡+雞塊+雪碧', 180, 'https://via.placeholder.com/300x200/45B7D1/FFFFFF?text=3號餐', 1, 1, 3),
        
        # 主餐
        (category_map['主餐'], '經典漢堡', '100%純牛肉', 70, 'https://via.placeholder.com/300x200/FF6B6B/FFFFFF?text=經典漢堡', 1, 0, 1),
        (category_map['主餐'], '雙層起司堡', '雙倍起司雙倍滿足', 90, 'https://via.placeholder.com/300x200/4ECDC4/FFFFFF?text=雙層起司堡', 1, 0, 2),
        (category_map['主餐'], '照燒雞腿堡', '鮮嫩多汁的雞腿肉', 85, 'https://via.placeholder.com/300x200/45B7D1/FFFFFF?text=照燒雞腿堡', 1, 0, 3),
        (category_map['主餐'], '素食蔬菜堡', '健康素食選擇', 75, 'https://via.placeholder.com/300x200/96CEB4/FFFFFF?text=素食蔬菜堡', 1, 0, 4),
        
        # 副餐
        (category_map['副餐'], '薯條', '金黃酥脆', 50, 'https://via.placeholder.com/300x200/FF6B6B/FFFFFF?text=薯條', 1, 0, 1),
        (category_map['副餐'], '洋蔥圈', '香脆可口', 60, 'https://via.placeholder.com/300x200/4ECDC4/FFFFFF?text=洋蔥圈', 1, 0, 2),
        (category_map['副餐'], '雞塊', '6塊裝', 65, 'https://via.placeholder.com/300x200/45B7D1/FFFFFF?text=雞塊', 1, 0, 3),
        (category_map['副餐'], '沙拉', '新鮮蔬菜', 70, 'https://via.placeholder.com/300x200/96CEB4/FFFFFF?text=沙拉', 1, 0, 4),
        
        # 飲料
        (category_map['飲料'], '可樂', '冰涼暢快', 30, 'https://via.placeholder.com/300x200/FF6B6B/FFFFFF?text=可樂', 1, 0, 1),
        (category_map['飲料'], '雪碧', '清爽解渴', 30, 'https://via.placeholder.com/300x200/4ECDC4/FFFFFF?text=雪碧', 1, 0, 2),
        (category_map['飲料'], '紅茶', '香醇濃郁', 25, 'https://via.placeholder.com/300x200/45B7D1/FFFFFF?text=紅茶', 1, 0, 3),
        (category_map['飲料'], '咖啡', '現煮咖啡', 40, 'https://via.placeholder.com/300x200/96CEB4/FFFFFF?text=咖啡', 1, 0, 4)
    ]
    
    c.executemany(
        '''INSERT INTO menu_items 
           (category_id, name, description, price, image_url, is_available, is_recommended, display_order) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        menu_items
    )
    
    # 創建管理員帳號
    try:
        c.execute("INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
                  ('admin', generate_password_hash('admin123'), 'admin'))
        c.execute("INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
                  ('staff', generate_password_hash('staff123'), 'staff'))
    except sqlite3.IntegrityError:
        pass  # 用戶已存在
    
    conn.commit()
    conn.close()
    print("數據庫初始化完成！")

if __name__ == "__main__":
    init_database()
