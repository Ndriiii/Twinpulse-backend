from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Boolean, Numeric, Date, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
from passlib.context import CryptContext
import uuid
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# ==========================================
# 1. SETUP DATABASE & PENGATURAN (Supabase Cloud)
# ==========================================
# GANTI URL DI BAWAH INI DENGAN LINK URI DARI SUPABASE KAMU
# Jangan lupa masukkan password aslinya untuk menggantikan [YOUR-PASSWORD]
DATABASE_URL = "postgresql://postgres:Twinpulse123*@db.gylecqsudylmhpmrduhu.supabase.co:5432/postgres"

# Tambahan pool_pre_ping=True sangat penting untuk database cloud agar koneksi tidak putus
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
app = FastAPI()

# ==========================================
# 2. SETUP PENGIRIM EMAIL GMAIL
# ==========================================
SENDER_EMAIL = "twinpulsee@gmail.com"
SENDER_PASSWORD = "xtrttcgfglnbyetr"

def send_real_email(receiver_email: str, subject: str, message: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(message, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email berhasil dikirim ke {receiver_email}")
    except Exception as e:
        print(f"❌ Gagal mengirim email: {e}")

# JEMBATAN BROWSER UNTUK RESET PASSWORD
@app.get("/open-app")
def open_app(action: str, token: str):
    app_link = f"twinpulse://{action}/{token}"
    html_content = f"""
    <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
        <body style="text-align: center; font-family: Arial, sans-serif; padding-top: 50px; background-color: #0A0E1A; color: white;">
            <h2 style="color: #00ADB5;">Sedang membuka TwinPulse...</h2>
            <a href="{app_link}" style="display: inline-block; background-color: #00ADB5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 10px;">Klik Di Sini</a>
            <script>setTimeout(function() {{ window.location.href = "{app_link}"; }}, 1000);</script>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# ==========================================
# 3. MODEL DATABASE
# ==========================================
class UserDB(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    profile_picture = Column(String, nullable=True)
    height = Column(Numeric(5, 2), nullable=True)
    weight = Column(Numeric(5, 2), nullable=True)
    birthdate = Column(Date, nullable=True)
    bmi = Column(Numeric(5, 2), nullable=True)
    is_verified = Column(Boolean, default=False)
    otp_code = Column(String(10), nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    reset_token = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# BARIS INI YANG AKAN OTOMATIS MEMBUAT TABEL DI SUPABASE
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# ==========================================
# 4. SKEMA REQUEST (PYDANTIC)
# ==========================================
class RegisterReq(BaseModel):
    full_name: str
    email: str
    password: str = Field(..., min_length=8)
    birthdate: str

class OTPReq(BaseModel):
    email: str
    token: str

class ResendOTPReq(BaseModel):
    email: str

class LoginReq(BaseModel):
    email: str
    password: str

class ForgotPasswordReq(BaseModel):
    email: str

class ResetPasswordReq(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

class ChangePasswordProfileReq(BaseModel):
    email: str
    old_password: str
    new_password: str = Field(..., min_length=8)

class ProfileUpdateReq(BaseModel):
    email: str
    full_name: str = None
    profile_picture: str = None
    height: float = None
    weight: float = None
    birthdate: str = None

class DeleteAccountReq(BaseModel):
    email: str
    password: str

# ==========================================
# 5. ENDPOINTS (API ROUTES)
# ==========================================

@app.post("/register")
def register(req: RegisterReq, db: Session = Depends(get_db)):
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password minimal harus 8 karakter")
        
    existing_user = db.query(UserDB).filter(UserDB.email == req.email.lower()).first()
    hashed_pw = pwd_context.hash(req.password[:72])
    otp = str(random.randint(100000, 999999))
    
    expiry_time = datetime.now() + timedelta(minutes=1)
    
    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(status_code=400, detail="Email sudah terdaftar dan terverifikasi. Silakan login.")
        else:
            existing_user.full_name = req.full_name
            existing_user.hashed_password = hashed_pw
            existing_user.birthdate = req.birthdate
            existing_user.otp_code = otp
            existing_user.otp_expiry = expiry_time 
            db.commit()
            user_to_email = existing_user
    else:
        new_user = UserDB(
            full_name=req.full_name, 
            email=req.email.lower(), 
            hashed_password=hashed_pw, 
            birthdate=req.birthdate, 
            otp_code=otp,
            otp_expiry=expiry_time 
        )
        db.add(new_user)
        db.commit()
        user_to_email = new_user

    html_message = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; padding: 20px;">
        <p>Halo <b>{user_to_email.full_name}</b>,</p>
        <p>Terima kasih telah mendaftar di TwinPulse!</p>
        <p>Kode OTP 6-digit kamu adalah:</p>
        <h2 style="color: #00ADB5; letter-spacing: 2px;">{otp}</h2>
        <p style="font-size: 12px; color: #777; margin-top: 20px;">Kode ini hanya berlaku selama 1 Menit.</p>
      </body>
    </html>
    """
    send_real_email(user_to_email.email, "Kode OTP Registrasi TwinPulse", html_message)
    return {"message": "Registrasi berhasil, cek email untuk kode OTP."}

@app.post("/verify-otp")
def verify_otp(req: OTPReq, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == req.email.lower()).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="User tidak ditemukan")

    if user.otp_expiry and datetime.now() > user.otp_expiry:
        raise HTTPException(status_code=400, detail="Sorry code is expired try to send another code")

    if user.otp_code != req.token:
        raise HTTPException(status_code=400, detail="OTP salah")
        
    user.is_verified = True
    user.otp_code = None
    user.otp_expiry = None
    db.commit()
    return {"message": "Email diverifikasi"}

@app.post("/resend-otp")
def resend_otp(req: ResendOTPReq, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == req.email.lower()).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="User tidak ditemukan")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email sudah terverifikasi")
        
    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    user.otp_expiry = datetime.now() + timedelta(minutes=1) 
    db.commit()
    
    html_message = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; padding: 20px;">
        <p>Halo <b>{user.full_name}</b>,</p>
        <p>Berikut adalah kode OTP baru kamu:</p>
        <h2 style="color: #00ADB5; letter-spacing: 2px;">{otp}</h2>
        <p style="font-size: 12px; color: #777; margin-top: 20px;">Kode ini hanya berlaku selama 1 Menit.</p>
      </body>
    </html>
    """
    send_real_email(user.email, "Kode OTP Baru TwinPulse", html_message)
    return {"message": "OTP baru telah dikirim"}

@app.post("/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == req.email.lower()).first()
    if not user or not pwd_context.verify(req.password[:72], user.hashed_password):
        raise HTTPException(status_code=400, detail="Email atau password salah")
    if not user.is_verified:
        raise HTTPException(status_code=400, detail="Email belum diverifikasi")
    return {"message": "Login berhasil", "full_name": user.full_name}

@app.post("/forgot-password")
def forgot_password(req: ForgotPasswordReq, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == req.email.lower()).first()
    if not user:
        raise HTTPException(status_code=400, detail="Email tidak terdaftar")
    
    reset_token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    user.reset_token = reset_token
    db.commit()

    link = f"http://192.168.18.15:8000/open-app?action=reset-password&token={reset_token}"
    
    html_message = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; padding: 20px;">
        <p>Halo <b>{user.full_name}</b>,</p>
        <p>Kami menerima permintaan untuk mereset password akun TwinPulse kamu.</p>
        <p>Silakan klik tombol di bawah ini untuk membuat password baru:</p>
        <br>
        <a href="{link}" style="background-color: #00ADB5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Reset Password Sekarang</a>
        <br><br><br>
        <p style="font-size: 12px; color: #777;">Atau salin tautan ini: {link}</p>
        <p style="font-size: 12px; color: #777;">Jika kamu tidak merasa melakukan permintaan ini, abaikan email ini.</p>
      </body>
    </html>
    """
    send_real_email(user.email, "Reset Password TwinPulse", html_message)
    return {"message": "Link dikirim"}

@app.post("/reset-password-direct")
def reset_password(req: ResetPasswordReq, db: Session = Depends(get_db)):
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password baru minimal harus 8 karakter")
        
    user = db.query(UserDB).filter(UserDB.reset_token == req.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Token tidak valid")
        
    if pwd_context.verify(req.new_password[:72], user.hashed_password):
        raise HTTPException(status_code=400, detail="Password baru tidak boleh sama dengan password lama!")
        
    user.hashed_password = pwd_context.hash(req.new_password[:72])
    user.reset_token = None
    db.commit()
    return {"message": "Password diubah"}

@app.post("/change-password-profile")
def change_password_profile(req: ChangePasswordProfileReq, db: Session = Depends(get_db)):
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password baru minimal harus 8 karakter")
        
    user = db.query(UserDB).filter(UserDB.email == req.email.lower()).first()
    if not user or not pwd_context.verify(req.old_password[:72], user.hashed_password):
        raise HTTPException(status_code=400, detail="Password lama salah")
    
    if req.old_password == req.new_password:
        raise HTTPException(status_code=400, detail="Password baru tidak boleh sama dengan password lama!")
    
    user.hashed_password = pwd_context.hash(req.new_password[:72])
    db.commit()
    return {"message": "Password berhasil diubah"}

@app.post("/get-profile")
def get_profile(req: ForgotPasswordReq, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == req.email.lower()).first()
    if not user: raise HTTPException(status_code=404)
    return {"full_name": user.full_name,
            "profile_picture": user.profile_picture,
            "height": user.height,
            "weight": user.weight,
            "birthdate": user.birthdate.isoformat() if user.birthdate else "None",
            "bmi": user.bmi}

@app.post("/update-profile")
def update_profile(req: ProfileUpdateReq, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == req.email.lower()).first()
    if not user: raise HTTPException(status_code=404)
    if req.full_name is not None: user.full_name = req.full_name
    if req.profile_picture is not None: user.profile_picture = req.profile_picture
    if req.height is not None: user.height = req.height
    if req.weight is not None: user.weight = req.weight
    if req.birthdate is not None: user.birthdate = req.birthdate
    if user.height and user.weight:
        user.bmi = round(float(user.weight) / ((float(user.height)/100) ** 2), 2)
    db.commit()
    return {"message": "Update sukses"}

@app.post("/delete-account")
def delete_account(req: DeleteAccountReq, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == req.email.lower()).first()
    if not user or not pwd_context.verify(req.password[:72], user.hashed_password):
        raise HTTPException(status_code=400, detail="Password salah")
    db.delete(user)
    db.commit()
    return {"message": "Akun dihapus"}