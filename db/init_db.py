from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, Account, EC2Instance
from utils.logger import logger

DATABASE_URL = "postgresql+psycopg2://devops:P%40ssw0rd%40123@172.22.191.151/awsdb"

engine = create_engine(DATABASE_URL, echo=True)
Session = sessionmaker(bind=engine)

def initialize_db():
    Base.metadata.create_all(engine)
    print("Database initialized and tables created.")
    logger.info("Database initialized and tables created.")
    
    
if __name__ == "__main__":
    initialize_db()