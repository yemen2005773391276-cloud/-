import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yemen_lens_x_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///yemen_lens_v3.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- جداول قاعدة البيانات بنظام المتابعة والتوثيق ---

# جدول الوسيط للمتابعين (Followers)
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.String(200), default="عاشق لجمال اليمن 🇾🇪")
    is_verified = db.Column(db.Boolean, default=False) # العلامة الزرقاء
    photos = db.relationship('Photo', backref='author', lazy=True)
    
    # علاقة المتابعة
    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('follower_list', lazy='dynamic'), lazy='dynamic'
    )

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(50), nullable=False)
    image_file = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- وظيفة حماية الحقوق الرقمية ---
def protect_image(filename, username):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    img = Image.open(file_path)
    exif = img.getexif()
    # كود 0x010e يمثل "ImageDescription" في معايير Metadata العالمية
    exif[0x010e] = f"حقوق الصورة محفوظة للمصور @{username} - منصة عدسة اليمن"
    img.save(file_path, exif=exif)

# --- المسارات (Routes) ---

@app.route('/')
def index():
    photos = Photo.query.order_by(Photo.id.desc()).all()
    return render_template('index.html', photos=photos)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        new_user = User(username=request.form['username'], password=hashed_pw, bio=request.form.get('bio'))
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    file = request.files.get('photo')
    if file:
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        # تطبيق حماية الحقوق الرقمية
        protect_image(filename, current_user.username)
        
        new_photo = Photo(
            title=request.form.get('title'),
            location=request.form.get('location'),
            image_file=filename,
            user_id=current_user.id
        )
        db.session.add(new_photo)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user:
        current_user.follow(user)
        db.session.commit()
    return redirect(request.referrer)

@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('profile.html', user=user)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
