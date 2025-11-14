import sqlite3
import random
import csv
from pathlib import Path


DB_NAME = "hackfest.db"
DB_PATH = Path(__file__).parent.parent.parent / DB_NAME


def get_db_connection():
    """Get a connection to the SQLite database"""
    return sqlite3.connect(str(DB_PATH))


def create_users_table():
    """Create the users table if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone_number TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("Users table initialized")


def create_chat_histories_table():
    """Create the chat_histories table if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_histories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT 'New Conversation',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()
    print("Chat histories table initialized")


def create_messages_table():
    """Create the messages table if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_history_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_history_id) REFERENCES chat_histories(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()
    print("Messages table initialized")


def generate_random_conversation_name() -> str:
    """Generate a random but meaningful conversation name"""
    adjectives = [
        "Curious", "Creative", "Thoughtful", "Innovative", "Dynamic",
        "Engaging", "Inspiring", "Reflective", "Exploratory", "Analytical",
        "Strategic", "Collaborative", "Insightful", "Productive", "Focused",
        "Open", "Deep", "Wide", "Bright", "Clear", "Fresh", "New", "Evolving"
    ]
    
    nouns = [
        "Exploration", "Discussion", "Inquiry", "Chat", "Conversation",
        "Dialogue", "Exchange", "Session", "Journey", "Adventure",
        "Discovery", "Insight", "Reflection", "Brainstorm", "Workshop",
        "Meeting", "Talk", "Debate", "Analysis", "Review"
    ]
    
    return f"{random.choice(adjectives)} {random.choice(nouns)}"


def create_default_chat_history(user_id: int):
    """Create default chat history with welcome message for a new user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Generate a random but meaningful conversation name
        conversation_name = generate_random_conversation_name()
        
        # Create a new chat history for the user
        cursor.execute("""
            INSERT INTO chat_histories (user_id, title)
            VALUES (?, ?)
        """, (user_id, conversation_name))
        
        chat_history_id = cursor.lastrowid
        
        # Add welcome message from assistant
        cursor.execute("""
            INSERT INTO messages (chat_history_id, role, content)
            VALUES (?, 'assistant', 'Welcome! How can I help you today?')
        """, (chat_history_id,))
        
        conn.commit()
        print(f"Default chat history created for user {user_id}")
        return chat_history_id
    except Exception as e:
        conn.rollback()
        print(f"Error creating default chat history: {e}")
        raise
    finally:
        conn.close()


def create_test_user():
    """Create a permanent test user for testing purposes"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Test user credentials
        test_name = "Test User"
        test_email = "test@example.com"
        test_phone = "9999999999"
        
        # Check if test user already exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (test_email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            print(f"Test user already exists with ID: {existing_user[0]}")
            return existing_user[0]
        
        # Create test user
        cursor.execute("""
            INSERT INTO users (name, email, phone_number)
            VALUES (?, ?, ?)
        """, (test_name, test_email, test_phone))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        # Create default chat history for test user
        try:
            create_default_chat_history(user_id)
        except Exception as e:
            print(f"Warning: Failed to create default chat history for test user: {e}")
        
        print(f"Test user created with ID: {user_id}")
        print(f"Test credentials - Name: {test_name}, Email: {test_email}, Phone: {test_phone}")
        return user_id
    except Exception as e:
        conn.rollback()
        print(f"Error creating test user: {e}")
        raise
    finally:
        conn.close()


def load_personalised_agent_csv_data():
    """
    Load CSV files from data/personalised_agent directory into SQLite tables.
    Avoids duplication by checking if tables already exist and have data.
    """
    data_dir = Path(__file__).parent.parent.parent / "data" / "personalised_agent"
    
    if not data_dir.exists():
        print(f"Warning: Personalised agent data directory not found at {data_dir}")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Map of table names to CSV filenames
    csv_files = {
        "user_info": "user_info.csv",
        "orders": "orders.csv",
        "order_items": "order_items.csv",
        "transactions": "transactions.csv",
        "cart": "cart.csv",
        "addresses": "addresses.csv",
        "returns": "returns.csv"
    }
    
    loaded_count = 0
    skipped_count = 0
    
    for table_name, csv_file in csv_files.items():
        csv_path = data_dir / csv_file
        
        if not csv_path.exists():
            print(f"Warning: CSV file not found: {csv_file}")
            continue
        
        try:
            # Check if table exists and has data
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            table_exists = cursor.fetchone() is not None
            
            if table_exists:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                
                if row_count > 0:
                    print(f"Skipping {table_name} - already has {row_count} rows")
                    skipped_count += 1
                    continue
            
            # Read CSV and create/load table
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                if not headers:
                    print(f"Warning: {csv_file} has no headers, skipping")
                    continue
                
                # Drop table if exists (to reload fresh data)
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                
                # Create table with all columns as TEXT for simplicity
                columns = ", ".join([f'"{col}" TEXT' for col in headers])
                cursor.execute(f"CREATE TABLE {table_name} ({columns})")
                
                # Insert data
                placeholders = ", ".join(["?" for _ in headers])
                insert_count = 0
                
                for row in reader:
                    values = [row.get(col, '') for col in headers]
                    cursor.execute(
                        f"INSERT INTO {table_name} VALUES ({placeholders})",
                        values
                    )
                    insert_count += 1
                
                conn.commit()
                print(f"Loaded {table_name} from {csv_file} - {insert_count} rows")
                loaded_count += 1
        
        except Exception as e:
            conn.rollback()
            print(f"Error loading {table_name} from {csv_file}: {e}")
    
    conn.close()
    print(f"CSV data ingestion complete: {loaded_count} tables loaded, {skipped_count} tables skipped")


def initialize_database():
    """Initialize the database if it doesn't exist"""
    if not DB_PATH.exists():
        # Create the database file by establishing a connection
        conn = get_db_connection()
        conn.close()
        print(f"Database created at {DB_PATH}")
    else:
        print(f"Database already exists at {DB_PATH}")
    
    # Initialize all tables
    create_users_table()
    create_chat_histories_table()
    create_messages_table()
    
    # Create test user
    create_test_user()
    
    # Load personalised agent CSV data
    load_personalised_agent_csv_data()

