from flask import Flask, render_template, request, Response, url_for, jsonify, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from newsapi import NewsApiClient
import os
from dotenv import load_dotenv
import requests
from datetime import datetime
from flask_caching import Cache

load_dotenv()
app = Flask(__name__)

# Configure app
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://') or 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Configure NewsAPI
news_api_key = os.getenv('NEWS_API_KEY')
newsapi = NewsApiClient(api_key=news_api_key)

categories = ['general', 'business', 'entertainment', 'health', 'science', 'sports', 'technology']

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@cache.memoize(timeout=300)
def get_news(category='general', page=1, query=None):
    try:
        params = {
            'category': category,
            'language': 'en',
            'page': page,
            'page_size': 12
        }
        if query:
            params['q'] = query
        all_articles = newsapi.get_top_headlines(**params)
        return all_articles
    except Exception as e:
        print(f"Error fetching news: {e}")
        return {'articles': [], 'totalResults': 0}

@app.route('/')
@app.route('/category/<category>')
@app.route('/category/<category>/page/<int:page>')
@login_required
def index(category='general', page=1):
    query = request.args.get('q')
    if category not in categories:
        category = 'general'
    if page < 1 or page > 5:
        page = 1

    news_data = get_news(category, page, query)
    articles = news_data.get('articles', [])

    for article in articles:
        article['title'] = article.get('title', 'No title available')
        article['description'] = article.get('description', 'No description available')[:150] + '...' if article.get('description') else ''
        article['url'] = article.get('url', '#')
        article['urlToImage'] = article.get('urlToImage', url_for('static', filename='default_image.jpg'))
        article['source'] = article.get('source', {'name': 'Unknown'})
        article['publishedAt'] = datetime.strptime(article.get('publishedAt', ''), "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y") if article.get('publishedAt') else 'Unknown date'

    total_results = min(news_data.get('totalResults', 0), 60)
    total_pages = min((total_results // 12) + 1, 5)

    return render_template('index.html', articles=articles, category=category, categories=categories, page=page, total_pages=total_pages, query=query)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('index.html', form='login')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('signup'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('signup'))
        
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('index.html', form='register')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/api/news')
@login_required
def api_news():
    category = request.args.get('category', 'general')
    page = int(request.args.get('page', 1))
    query = request.args.get('q')
    news_data = get_news(category, page, query)
    return jsonify(news_data)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)