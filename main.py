from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from passlib.context import CryptContext

# ---------- Конфигурация базы данных ----------
SQLALCHEMY_DATABASE_URL = "sqlite:///./moodfriends.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Хеширование паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------- Модели SQLAlchemy ----------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    mood = Column(Integer, default=50)  # текущее настроение 0-100

    # Друзья: пользователь, на которого указывает friend_id
    friends = relationship(
        "FriendLink",
        foreign_keys="FriendLink.user_id",
        back_populates="user",
        cascade="all, delete-orphan"
    )

class FriendLink(Base):
    __tablename__ = "friends"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    friend_id = Column(Integer, ForeignKey("users.id"), primary_key=True)

    user = relationship("User", foreign_keys=[user_id], back_populates="friends")
    friend = relationship("User", foreign_keys=[friend_id])

# Создание таблиц
Base.metadata.create_all(bind=engine)

# ---------- Pydantic схемы ----------
class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class MoodUpdate(BaseModel):
    mood: int = Field(..., ge=0, le=100)

class FriendResponse(BaseModel):
    id: int
    username: str
    mood: int
    # avatar: можно передать URL позже, пока используем заглушку

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    mood: int

# ---------- Зависимости ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# ---------- FastAPI приложение ----------
app = FastAPI(title="Mood Friends API", version="1.0")

# Разрешаем CORS для доступа из Android (и любых клиентов)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Эндпоинты ----------
@app.post("/api/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserRegister, db: Session = Depends(get_db)):
    # Проверка уникальности
    existing = db.query(User).filter(
        (User.username == user.username) | (User.email == user.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already exists")
    
    hashed = get_password_hash(user.password)
    db_user = User(username=user.username, email=user.email, hashed_password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/api/auth/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Возвращаем user_id для использования в заголовках
    return {"user_id": db_user.id, "username": db_user.username, "mood": db_user.mood}

@app.get("/api/user/mood")
def get_mood(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user.id, "mood": user.mood}

@app.post("/api/user/mood")
def update_mood(user_id: int, mood_data: MoodUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.mood = mood_data.mood
    db.commit()
    return {"user_id": user.id, "mood": user.mood}

@app.get("/api/friends", response_model=List[FriendResponse])
def get_friends(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Получаем список друзей через таблицу связи
    friends = []
    for link in user.friends:
        friend = link.friend
        friends.append(FriendResponse(
            id=friend.id,
            username=friend.username,
            mood=friend.mood
        ))
    return friends

# ---------- Заполнение тестовыми данными (для демонстрации) ----------
def init_test_data():
    db = SessionLocal()
    # Проверяем, есть ли уже данные
    if db.query(User).count() == 0:
        # Создаём пользователей
        user1 = User(username="Серега", email="serega@example.com", hashed_password=get_password_hash("pass123"), mood=40)
        user2 = User(username="Денчик", email="den@example.com", hashed_password=get_password_hash("pass123"), mood=85)
        user3 = User(username="Мария", email="maria@example.com", hashed_password=get_password_hash("pass123"), mood=60)
        db.add_all([user1, user2, user3])
        db.commit()
        
        # Добавляем дружеские связи (user1 дружит с user2 и user3)
        db.add(FriendLink(user_id=user1.id, friend_id=user2.id))
        db.add(FriendLink(user_id=user1.id, friend_id=user3.id))
        # user2 дружит с user1
        db.add(FriendLink(user_id=user2.id, friend_id=user1.id))
        # user3 дружит с user1
        db.add(FriendLink(user_id=user3.id, friend_id=user1.id))
        db.commit()
    db.close()

# Вызовем при старте (только один раз при запуске контейнера)
@app.on_event("startup")
def on_startup():
    init_test_data()

# Точка входа для uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)