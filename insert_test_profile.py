import sqlite3

conn = sqlite3.connect('data/automation.db')
c = conn.cursor()
c.execute("INSERT OR IGNORE INTO profiles (account_id, name, email, phone, birthday, location) VALUES (?, ?, ?, ?, ?, ?)", (
    'karthikeyan_mani5',
    'Karthikeyan Mani',
    'karthik@example.com',
    '1234567890',
    '1990-01-01',
    'Chennai'
))
conn.commit()
conn.close()
print('Test profile inserted.')
