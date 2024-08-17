from flask import Flask, render_template, request, Response, url_for, jsonify
from newsapi import NewsApiClient
import os
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
import re
from flask_caching import Cache
import logging

load_dotenv()
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Configure caching
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

news_api_key = os.getenv('NEWS_API_KEY')
newsapi = NewsApiClient(api_key=news_api_key)

categories = ['general', 'business', 'entertainment', 'health', 'science', 'sports', 'technology']

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
def search():
    query = request.args.get('q', '')
    category = request.args.get('category', 'general')
    page = int(request.args.get('page', 1))
    return index(category, page)

@app.route('/api/news')
def api_news():
    category = request.args.get('category', 'general')
    page = int(request.args.get('page', 1))
    query = request.args.get('q')
    news_data = get_news(category, page, query)
    return jsonify(news_data)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True)