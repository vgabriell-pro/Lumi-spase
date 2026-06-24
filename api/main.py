import os, json, datetime, smtplib, threading
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import bcrypt, jwt

# ---------- config ----------
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./lumi.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
SECRET = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# ---------- email ----------
SMTP_HOST  = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT  = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER  = os.environ.get("SMTP_USER", "")
SMTP_PASS  = os.environ.get("SMTP_PASS", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER)
FROM_NAME  = os.environ.get("FROM_NAME", "Lumi")
APP_URL    = os.environ.get("APP_URL", "https://vgabriell-pro.github.io/Lumi-spase/")
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "")
MAIN_NAME   = os.environ.get("VENUE_NAME", "Lumi Space")

def _send(to: str, subject: str, html: str):
    if not (SMTP_USER and SMTP_PASS and to):
        return  # email not configured — skip quietly
    try:
        msg = MIMEText(html, "html", "utf-8")
        msg["Subject"] = subject
        msg["From"] = formataddr((FROM_NAME, FROM_EMAIL))
        msg["To"] = to
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as srv:
            srv.starttls()
            srv.login(SMTP_USER, SMTP_PASS)
            srv.sendmail(FROM_EMAIL, [to], msg.as_string())
    except Exception as e:
        print("email error:", e)

def send_email(to: str, subject: str, html: str):
    threading.Thread(target=_send, args=(to, subject, html), daemon=True).start()

def email_html(title: str, body: str, cta_text: str = "", cta_url: str = "") -> str:
    btn = (f'<a href="{cta_url}" style="display:inline-block;background:#15171A;color:#fff;'
           f'text-decoration:none;font-weight:600;font-size:15px;padding:12px 22px;border-radius:10px;'
           f'margin-top:10px;">{cta_text}</a>') if (cta_text and cta_url) else ""
    return (f'<div style="font-family:Inter,Arial,Helvetica,sans-serif;max-width:520px;margin:0 auto;color:#15171A;">'
            f'<div style="font-weight:800;font-size:20px;letter-spacing:-1px;margin-bottom:18px;">'
            f'<span style="display:inline-block;width:14px;height:14px;border-radius:4px;background:#1E5DFF;'
            f'vertical-align:-1px;margin-right:6px;"></span>Lumi</div>'
            f'<h1 style="font-size:22px;margin:0 0 12px;">{title}</h1>'
            f'<div style="font-size:15px;color:#5B6168;line-height:1.65;">{body}</div>{btn}'
            f'<hr style="border:none;border-top:1px solid #ECEEF1;margin:26px 0 14px;">'
            f'<div style="font-size:12px;color:#8A9099;">Lumi · аренда пространств в Тбилиси по часам</div></div>')

def fmt_date(d: str) -> str:
    p = d.split("-")
    return f"{p[2]}.{p[1]}.{p[0]}" if len(p) == 3 else d

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# ---------- models ----------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Space(Base):
    __tablename__ = "spaces"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String, nullable=False)
    cat = Column(String, nullable=False)
    cat_name = Column(String, nullable=False)
    use = Column(String, default="")
    loc = Column(String, default="")
    addr = Column(String, default="")
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    cap = Column(Integer, default=0)
    rate = Column(Integer, default=0)
    rating = Column(Float, default=0)
    host = Column(String, default="")
    descr = Column(Text, default="")
    amen = Column(Text, default="[]")
    reviews = Column(Text, default="[]")
    is_new = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True)
    space_id = Column(Integer, ForeignKey("spaces.id"))
    renter_id = Column(Integer, ForeignKey("users.id"))
    renter_name = Column(String, default="")
    date = Column(String)          # YYYY-MM-DD
    slot = Column(Integer)
    hours = Column(Integer)
    guests = Column(Integer)
    sub = Column(Integer)
    dep = Column(Integer)
    total = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Inquiry(Base):
    __tablename__ = "inquiries"
    id = Column(Integer, primary_key=True)
    name = Column(String, default="")
    contact = Column(String, default="")
    date = Column(String, default="")
    kind = Column(String, default="")
    message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(engine)

# ---------- helpers ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode()[:72], bcrypt.gensalt()).decode()

def check_pw(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode()[:72], h.encode())
    except Exception:
        return False

def make_token(uid: int) -> str:
    payload = {"uid": uid, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30)}
    return jwt.encode(payload, SECRET, algorithm="HS256")

def user_from_header(authorization: Optional[str], db: Session) -> Optional[User]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(authorization[7:], SECRET, algorithms=["HS256"])
    except Exception:
        return None
    return db.get(User, payload.get("uid"))

def require_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> User:
    u = user_from_header(authorization, db)
    if not u:
        raise HTTPException(status_code=401, detail="Нужно войти")
    return u

def dep_for(rate: int) -> int:
    return max(50, round(rate * 0.8 / 10) * 10)

def space_dict(s: Space) -> dict:
    return {
        "id": s.id, "name": s.name, "cat": s.cat, "catName": s.cat_name,
        "use": s.use, "loc": s.loc, "addr": s.addr, "lat": s.lat, "lon": s.lon,
        "cap": s.cap, "rate": s.rate, "rating": s.rating, "host": s.host,
        "desc": s.descr, "amen": json.loads(s.amen or "[]"),
        "rev": json.loads(s.reviews or "[]"),
        "isNew": bool(s.is_new), "ownerId": s.owner_id,
    }

def booking_dict(b: Booking, space_name: str = "") -> dict:
    return {
        "id": b.id, "spaceId": b.space_id, "spaceName": space_name,
        "renterName": b.renter_name, "date": b.date, "slot": b.slot,
        "hours": b.hours, "guests": b.guests, "sub": b.sub, "dep": b.dep, "total": b.total,
    }

# ---------- schemas ----------
class RegIn(BaseModel):
    email: str
    name: str
    password: str

class LoginIn(BaseModel):
    email: str
    password: str

class SpaceIn(BaseModel):
    name: str
    cat: str
    catName: str = ""
    use: str = ""
    loc: str = ""
    addr: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    cap: int = 0
    rate: int = 0
    desc: str = ""
    amen: list = []

class BookingIn(BaseModel):
    spaceId: int
    date: str
    slot: int
    hours: int
    guests: int = 1

# ---------- app ----------
app = FastAPI(title="Lumi API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/")
def root():
    return {"ok": True, "service": "lumi-api"}

# ----- auth -----
@app.post("/api/auth/register")
def register(body: RegIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not email or not body.password or not body.name.strip():
        raise HTTPException(400, "Заполни имя, почту и пароль")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "Такая почта уже занята")
    u = User(email=email, name=body.name.strip(), password_hash=hash_pw(body.password))
    db.add(u); db.commit(); db.refresh(u)
    send_email(u.email, "Добро пожаловать в Lumi",
        email_html(f"Привет, {u.name.split(' ')[0]}!",
                   "Профиль создан. Теперь можно бронировать пространства Тбилиси по часам — "
                   "и размещать свои, если захочешь сдавать.",
                   "Открыть Lumi", APP_URL))
    return {"token": make_token(u.id), "user": {"id": u.id, "email": u.email, "name": u.name}}

@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    u = db.query(User).filter(User.email == email).first()
    if not u or not check_pw(body.password, u.password_hash):
        raise HTTPException(400, "Неверная почта или пароль")
    return {"token": make_token(u.id), "user": {"id": u.id, "email": u.email, "name": u.name}}

@app.get("/api/me")
def me(u: User = Depends(require_user)):
    return {"id": u.id, "email": u.email, "name": u.name}

# ----- spaces -----
@app.get("/api/spaces")
def list_spaces(db: Session = Depends(get_db)):
    rows = db.query(Space).order_by(Space.id.desc()).all()
    return [space_dict(s) for s in rows]

@app.get("/api/spaces/{sid}")
def get_space(sid: int, db: Session = Depends(get_db)):
    s = db.get(Space, sid)
    if not s:
        raise HTTPException(404, "Пространство не найдено")
    return space_dict(s)

@app.get("/api/space")
def main_space(db: Session = Depends(get_db)):
    s = db.query(Space).filter(Space.name == MAIN_NAME).first()
    if not s:
        raise HTTPException(404, "Пространство не найдено")
    return space_dict(s)

class ContactIn(BaseModel):
    name: str
    contact: str
    date: str = ""
    kind: str = ""
    message: str = ""

@app.post("/api/contact")
def contact(body: ContactIn, db: Session = Depends(get_db)):
    if not body.name.strip() or not body.contact.strip():
        raise HTTPException(400, "Укажи имя и контакт")
    q = Inquiry(name=body.name.strip(), contact=body.contact.strip(),
                date=body.date, kind=body.kind, message=body.message)
    db.add(q); db.commit()
    if OWNER_EMAIL:
        send_email(OWNER_EMAIL, "Новая заявка на мероприятие — Lumi Space",
            email_html("Новая заявка на мероприятие",
                       f"<b>{body.name}</b><br>Контакт: {body.contact}<br>"
                       f"Дата: {body.date or '—'}<br>Формат: {body.kind or '—'}<br><br>"
                       f"{body.message or '(без комментария)'}",
                       "Открыть Lumi", APP_URL))
    return {"ok": True}

# ----- bookings -----
@app.post("/api/bookings")
def create_booking(body: BookingIn, u: User = Depends(require_user), db: Session = Depends(get_db)):
    s = db.get(Space, body.spaceId)
    if not s:
        raise HTTPException(404, "Пространство не найдено")
    sub = s.rate * body.hours
    dep = dep_for(s.rate)
    b = Booking(
        space_id=s.id, renter_id=u.id, renter_name=u.name,
        date=body.date, slot=body.slot, hours=body.hours, guests=max(1, body.guests),
        sub=sub, dep=dep, total=sub + dep,
    )
    db.add(b); db.commit(); db.refresh(b)
    when = f"{fmt_date(body.date)} · {body.slot}:00–{body.slot + body.hours}:00"
    guests = max(1, body.guests)
    # confirmation to the guest
    send_email(u.email, f"Бронь подтверждена — {s.name}",
        email_html("Бронь подтверждена ✓",
                   f"<b>{s.name}</b> · {s.loc}, Тбилиси<br>{when} · {guests} чел.<br><br>"
                   f"Аренда ₾{sub} + возвратный залог ₾{dep} = <b>₾{sub + dep}</b>.<br>"
                   f"Хозяин — {s.host}. Напомним за день до встречи.",
                   "Мои брони", APP_URL))
    # notification to the host
    if OWNER_EMAIL:
        send_email(OWNER_EMAIL, f"Новая бронь — {s.name}",
            email_html("Новая бронь 🎉",
                       f"<b>{s.name}</b><br>{when} · {guests} чел.<br><br>"
                       f"Гость — {u.name} ({u.email}).<br>Аренда ₾{sub}.",
                       "Открыть Lumi", APP_URL))
    return booking_dict(b, s.name)

@app.get("/api/my/bookings")
def my_bookings(u: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.query(Booking).filter(Booking.renter_id == u.id).order_by(Booking.date).all()
    out = []
    for b in rows:
        s = db.get(Space, b.space_id)
        out.append(booking_dict(b, s.name if s else ""))
    return out

# ---------- seed demo catalogue ----------
SEED = [
    ("Студия «Окна»","photo","Съёмка","съёмки и контент","Вера",12,60,4.9,"Нино",
     "Светлая студия с большими окнами и мягким дневным светом. Подходит для съёмок, интервью и небольших классов.",
     ["Дневной свет","Циклорама","Свет","Гримёрка","Wi-Fi"],[["Марика","Май","Свет шикарный, окна — мечта. Вернусь."]]),
    ("Лофт «Кирпич»","loft","Лофт","вечеринки и съёмки","Чугурети",40,90,4.8,"Гио",
     "Просторный лофт с кирпичными стенами и высокими потолками. Звук, свет, бар-зона — для вечеринок и съёмок.",
     ["Звук","Свет","Бар","Парковка","Кондиционер"],[["Гио","Апрель","Идеально для дня рождения, все были в восторге."]]),
    ("Мастерская «Глина»","clay","Керамика","гончарные классы","Сололаки",8,45,5.0,"Кетеван",
     "Уютная гончарная мастерская с кругами и печью. Для классов и личной практики.",
     ["Гончарные круги","Печь","Глина","Туалет"],[["Софи","Май","Кетеван — золото, всё показала и помогла."]]),
    ("Зал «Поток»","move","Танец и йога","йога, танцы, репетиции","Сабуртало",20,50,4.7,"Лела",
     "Зеркальный зал с мягким покрытием. Для йоги, танцев и репетиций.",
     ["Зеркала","Коврики","Звук","Раздевалка"],[]),
    ("Веранда «Сад»","event","Мероприятия","дни рождения, лекции","Ваке",35,80,4.8,"Дато",
     "Зелёная веранда с садом. Для дней рождения, лекций и тёплых встреч.",
     ["Сад","Мебель","Проектор","Кухня"],[["Нина","Июнь","Гости не хотели уходить — так красиво."]]),
    ("Коворкинг «Тихо»","work","Коворк","встречи и работа","Ваке",14,40,4.6,"Анна",
     "Спокойный коворкинг для встреч и сосредоточенной работы.",
     ["Wi-Fi","Проектор","Кофе","Кондиционер"],[]),
    ("Кухня-студия «Тесто»","food","Кухня","кулинарные классы","Марджанишвили",10,55,4.9,"Софо",
     "Кухня-студия с островом и красивым светом. Для кулинарных классов и съёмок еды.",
     ["Кухня","Посуда","Дневной свет","Мебель"],[["Лаша","Май","Снимали рецепты — картинка вкусная."]]),
    ("Арт-пространство «Палитра»","art","Арт","выставки, мастер-классы","Сололаки",25,70,4.8,"Тамар",
     "Светлое арт-пространство под выставки и мастер-классы.",
     ["Свет","Мебель","Wi-Fi","Туалет"],[]),
    ("Фотостудия «Циклорама»","photo","Съёмка","fashion и предметка","Дигоми",15,75,4.9,"Леван",
     "Профессиональная фотостудия с циклорамой и студийным светом.",
     ["Циклорама","Студийный свет","Гримёрка","Парковка"],[["Эка","Апрель","Циклорама большая, света хватает."]]),
    ("Зал «Сцена»","event","Мероприятия","концерты, спектакли","Мтацминда",50,110,4.7,"Ника",
     "Большой зал со сценой и звуком для концертов и спектаклей.",
     ["Сцена","Звук","Свет","Гримёрка"],[]),
    ("Студия «Барре»","move","Танец и йога","балет, стретчинг","Вера",16,48,4.8,"Мариам",
     "Балетная студия со станком и зеркалами.",
     ["Станок","Зеркала","Покрытие","Раздевалка"],[]),
    ("Лофт «Панорама»","loft","Лофт","съёмки с видом","Мтацминда",30,100,5.0,"Заза",
     "Лофт с панорамным окном и видом на город. Для съёмок и встреч.",
     ["Панорама","Дневной свет","Мебель","Wi-Fi"],[["Тео","Июнь","Вид на закате — отдельный вид искусства."]]),
]

def seed():
    db = SessionLocal()
    try:
        if db.query(Space).count() == 0:
            for (name,cat,catName,use,loc,cap,rate,rating,host,desc,amen,rev) in SEED:
                db.add(Space(
                    owner_id=None, name=name, cat=cat, cat_name=catName, use=use, loc=loc,
                    cap=cap, rate=rate, rating=rating, host=host, descr=desc,
                    amen=json.dumps(amen, ensure_ascii=False),
                    reviews=json.dumps(rev, ensure_ascii=False), is_new=0,
                ))
            db.commit()
    finally:
        db.close()

def ensure_main():
    db = SessionLocal()
    try:
        if not db.query(Space).filter(Space.name == MAIN_NAME).first():
            db.add(Space(
                owner_id=None, name=MAIN_NAME, cat="event", cat_name="Творческое пространство",
                use="съёмок, занятий, встреч и праздников", loc="Ваке", addr="Тбилиси, Ваке",
                lat=41.7095, lon=44.7860, cap=30, rate=80, rating=5.0, host="Lumi",
                descr="Светлое творческое пространство в районе Ваке. Большие окна, дневной свет и "
                      "гибкая рассадка — подходит для съёмок, классов, встреч и небольших праздников.",
                amen=json.dumps(["Дневной свет","Wi-Fi","Звук","Кухня","Мебель","Кондиционер","Проектор","Туалет"], ensure_ascii=False),
                reviews="[]", is_new=0,
            ))
            db.commit()
    finally:
        db.close()

seed()
ensure_main()
