import sqlite3, os

# Find the right db file
db_path = 'jobs.db'
if not os.path.exists(db_path):
    for f in os.listdir('.'):
        if f.endswith('.db'):
            db_path = f
            break

conn = sqlite3.connect(db_path)
c = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'")
schema = c.fetchone()
print('SCHEMA:', schema[0][:500] if schema else 'NO TABLE')

# Check for duplicate URLs
c = conn.execute("""
    SELECT url, title, company, COUNT(*) as cnt 
    FROM jobs 
    GROUP BY url 
    HAVING cnt > 1
    ORDER BY cnt DESC 
    LIMIT 20
""")
dupes_by_url = c.fetchall()
print(f'\n=== DUPLICATE URLS ({len(dupes_by_url)}) ===')
for d in dupes_by_url:
    print(f'  x{d[3]} | {d[1]} @ {d[2]} | {d[0][:80]}')

# Check for duplicate title+company (same job, different URLs)
c = conn.execute("""
    SELECT title, company, COUNT(*) as cnt, GROUP_CONCAT(url, ' | ') as urls
    FROM jobs 
    GROUP BY LOWER(TRIM(title)), LOWER(TRIM(company))
    HAVING cnt > 1
    ORDER BY cnt DESC 
    LIMIT 20
""")
dupes_by_tc = c.fetchall()
print(f'\n=== DUPLICATE TITLE+COMPANY ({len(dupes_by_tc)}) ===')
for d in dupes_by_tc:
    print(f'  x{d[2]} | {d[0]} @ {d[1]}')
    print(f'       URLs: {d[3][:150]}')

# Count total
c = conn.execute("SELECT COUNT(*) FROM jobs")
total = c.fetchone()[0]
print(f'\nTotal jobs in DB: {total}')
conn.close()
