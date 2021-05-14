import os

# from dotenv import load_dotenv

# load_dotenv()
proxy = os.getenv("proxy").split(";")
PGUSER = str(os.getenv("PGUSER"))
PGPASSWORD = str(os.getenv("PGPASSWORD"))
DATABASE = str(os.getenv("DATABASE"))

PG_IP = str(os.getenv("PG_IP"))
REDIS_IP = str(os.getenv("REDIS_IP"))
IP = str(os.getenv("IP"))
PORT = str(os.getenv("PORT"))

POSTGRES_URI = f"postgres://{PGUSER}:{PGPASSWORD}@{PG_IP}:{PORT}/{DATABASE}"
