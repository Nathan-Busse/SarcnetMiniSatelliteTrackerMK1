from GeoDude import GeoDude
import os

print(f"Looking for database in: {os.getcwd()}")
if os.path.exists("geonames.db"):
    print("Database file found.")
    try:
        g = GeoDude()
        print("✅ GeoDude loaded successfully!")
    except Exception as e:
        print(f"❌ GeoDude failed to load: {e}")
else:
    print("❌ Database file not found.")