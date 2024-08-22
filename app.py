from flask import Flask, render_template, request, Response, url_for, jsonify, redirect, flash
from newsapi import NewsApiClient
import os
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
import re
from flask_caching import Cache
import logging
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Configure caching
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Configure database
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://')
db = SQLAlchemy(app)

# Configure login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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

@cache.memoize(timeout=300)  # Cache for 5 minutes
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
        app.logger.info(f"Fetched {len(all_articles.get('articles', []))} articles for category: {category}")
        return all_articles
    except Exception as e:
        app.logger.error(f"Error fetching news: {e}")
        return {'articles': [], 'totalResults': 0}

@app.route('/proxy_image/<path:image_url>')
@cache.memoize(timeout=3600)  # Cache images for 1 hour
def proxy_image(image_url):
    try:
        app.logger.info(f"Attempting to fetch image: {image_url}")
        response = requests.get(image_url, timeout=5)
        app.logger.info(f"Image fetch status code: {response.status_code}")
        return Response(response.content, content_type=response.headers['Content-Type'])
    except Exception as e:
        app.logger.error(f"Error proxying image {image_url}: {str(e)}")
        return Response(status=404)

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
        if article.get('urlToImage'):
            article['urlToImage'] = url_for('proxy_image', image_url=article['urlToImage'])
        else:
            article['urlToImage'] = url_for('static', filename='default_image.jpg')
        article['source'] = article.get('source', {'name': 'Unknown'})
        article['publishedAt'] = datetime.strptime(article.get('publishedAt', ''), "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y") if article.get('publishedAt') else 'Unknown date'
        
        article['description'] = re.sub(r'No description available', '', article['description'])

    total_results = min(news_data.get('totalResults', 0), 60)
    total_pages = min((total_results // 12) + 1, 5)

    return render_template('index.html', articles=articles, category=category, categories=categories, page=page, total_pages=total_pages, query=query)

@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    category = request.args.get('category', 'general')
    page = int(request.args.get('page', 1))
    return index(category, page)

@app.route('/api/news')
@login_required
def api_news():
    category = request.args.get('category', 'general')
    page = int(request.args.get('page', 1))
    query = request.args.get('q')
    news_data = get_news(category, page, query)
    return jsonify(news_data)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists', 'danger')
            return redirect(url_for('register'))
        
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('index.html', form='register')

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
            return redirect(url_for('login'))
    
    return render_template('index.html', form='login')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html', error='404 - Page not found'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('index.html', error='500 - Internal server error'), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
    app.run(debug=True)