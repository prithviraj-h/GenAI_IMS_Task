import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.chroma import chroma_client
from db.mongo import mongo_client

def check_kb_entries():
    print("🔍 Checking KB Entries...")
    
    # Initialize database connections
    try:
        print("📡 Initializing database connections...")
        mongo_client.connect()
        
        # Try different initialization methods for ChromaDB
        if hasattr(chroma_client, 'initialize'):
            chroma_client.initialize()
        elif hasattr(chroma_client, 'client'):
            # Client might already be initialized
            print("✅ ChromaDB client already exists")
        else:
            # Try to access collection which might trigger initialization
            try:
                _ = chroma_client.collection
                print("✅ ChromaDB collection accessed")
            except:
                print("⚠️ ChromaDB might need manual initialization")
        
        print("✅ Database connections established")
    except Exception as e:
        print(f"❌ Error connecting to databases: {e}")
        return
    
    # Check ChromaDB
    print("\n📚 ChromaDB Entries:")
    try:
        if hasattr(chroma_client, 'get_all_entries'):
            chroma_entries = chroma_client.get_all_entries()
        else:
            print("❌ get_all_entries method not found")
            chroma_entries = []
            
        if chroma_entries:
            print(f"Found {len(chroma_entries)} entries:")
            for entry in chroma_entries:
                print(f"KB ID: {entry.get('id', 'N/A')}")
                print(f"Use Case: {entry.get('metadata', {}).get('use_case', 'N/A')}")
                solution = entry.get('metadata', {}).get('solution_steps', 'N/A')
                print(f"Solution: {solution[:100]}{'...' if len(solution) > 100 else ''}")
                print("-" * 50)
        else:
            print("No entries found in ChromaDB")
    except Exception as e:
        print(f"Error getting ChromaDB entries: {e}")
    
    # Check MongoDB
    print("\n🗄️ MongoDB Entries:")
    try:
        mongo_entries = mongo_client.get_all_kb_entries()
        if mongo_entries:
            print(f"Found {len(mongo_entries)} entries:")
            for entry in mongo_entries:
                print(f"KB ID: {entry.get('kb_id', 'N/A')}")
                print(f"Use Case: {entry.get('use_case', 'N/A')}")
                solution = entry.get('solution_steps', 'N/A')
                print(f"Solution: {solution[:100]}{'...' if len(solution) > 100 else ''}")
                print("-" * 50)
        else:
            print("No entries found in MongoDB")
    except Exception as e:
        print(f"Error getting MongoDB entries: {e}")
    
    print(f"\n📊 Summary:")
    chroma_count = len(chroma_entries) if 'chroma_entries' in locals() else 0
    mongo_count = len(mongo_entries) if 'mongo_entries' in locals() else 0
    print(f"ChromaDB: {chroma_count} entries")
    print(f"MongoDB: {mongo_count} entries")
    
    # Clean up
    try:
        mongo_client.disconnect()
        print("✅ Database connections closed")
    except:
        pass

if __name__ == "__main__":
    check_kb_entries()