import sqlite3
import os
from datetime import datetime

DB_PATH = "engine_performance.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            niche TEXT,
            success INTEGER,
            topic TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_generation(niche, topic, success=1):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO generations (timestamp, niche, topic, success)
        VALUES (?, ?, ?, ?)
    ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), niche, topic, int(success)))
    conn.commit()
    conn.close()

def get_performance_stats():
    """Returns total generated and data points for chart."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Total count
    cursor.execute('SELECT COUNT(*) FROM generations WHERE success = 1')
    total = cursor.fetchone()[0]
    
    # Last 10 points for the chart (simplified)
    cursor.execute('''
        SELECT timestamp, COUNT(*) 
        FROM generations 
        WHERE success = 1 
        GROUP BY strftime('%Y-%m-%d %H', timestamp) 
        ORDER BY timestamp DESC 
        LIMIT 10
    ''')
    chart_data = cursor.fetchall()
    
    conn.close()
    return total, chart_data[::-1]

init_db()
