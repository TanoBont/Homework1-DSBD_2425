from sqlalchemy import ForeignKey, create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
import os

# Connessione al database MySQL
DATABASE_URL = f"mysql+mysqlconnector://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"

engine = create_engine(DATABASE_URL,isolation_level="READ COMMITTED")

# Creazione di una sessione Scoped per supportare l'uso in più thread
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()

# Definizione delle tabelle
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)  # Lunghezza massima a 255
    ticker = Column(String(10), nullable=False)                           # Lunghezza massima a 10 per i ticker

class StockData(Base):
    __tablename__ = "stock_data"
    data_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ticker = Column(String(10), nullable=False)
    value = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)

class RegistrationMessage(Base): 
    __tablename__ = "registration_messages"
    message_id = Column(String(255),primary_key=True, unique=True, nullable=False)

class UpdateMessage(Base): 
    __tablename__ = "update_messages"
    message_id = Column(String(255),primary_key=True, unique=True, nullable=False)

# Creazione delle tabelle nel database
Base.metadata.create_all(bind=engine)
