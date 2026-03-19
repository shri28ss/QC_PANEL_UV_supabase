import psycopg2
import traceback

urls = [
    # IPv6 Original
    "postgresql://postgres:ledgerAI%40uve@db.ivbrlminlzhpitiyczze.supabase.co:5432/postgres",
    # My Guessed IPv4 Pooler
    "postgresql://postgres.ivbrlminlzhpitiyczze:ledgerAI%40uve@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
]

for url in urls:
    print(f"\nTesting: {url.split('@')[-1]}")
    try:
        conn = psycopg2.connect(url, connect_timeout=5)
        print("SUCCESS! Connected.")
        conn.close()
    except Exception as e:
        print("FAILED!")
        print(traceback.format_exc())
