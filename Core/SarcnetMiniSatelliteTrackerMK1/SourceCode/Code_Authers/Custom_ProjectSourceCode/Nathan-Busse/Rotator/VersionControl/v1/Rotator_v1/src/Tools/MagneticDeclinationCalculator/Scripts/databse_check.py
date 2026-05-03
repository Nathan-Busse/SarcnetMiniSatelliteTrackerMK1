from gazetteer import Gazetteer
import os

print(f"Looking for database in: {os.getcwd()}")
if os.path.exists("geonames.db"):
    print("Database file found.")
    try:
        g = Gazetteer()
        print("✅ Gazetteer loaded successfully!")
    except Exception as e:
        print(f"❌ Gazetteer failed to load: {e}")
else:
    print("❌ Database file not found.")