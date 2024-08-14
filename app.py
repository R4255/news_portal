from flask import Flask, render_template, request, Response, url_for
from newsapi import NewsApiClient
import os
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)

news_api_key = os.getenv('NEWS_API_KEY')
newsapi = NewsApiClient(api_key=news_api_key)

categories = ['general', 'business', 'entertainment', 'health', 'science', 'sports', 'technology']

def get_news(category='general', page=1):
    try:
        all_articles = newsapi.get_top_headlines(
            category=category,
            language='en',
            page=page,
            page_size=20
        )
        return all_articles
    except Exception as e:
        print(f"Error fetching news: {e}")
        return {'articles': [], 'totalResults': 0}

@app.route('/proxy_image/<path:image_url>')
def proxy_image(image_url):
    try:
        response = requests.get(image_url)
        return Response(response.content, content_type=response.headers['Content-Type'])
    except:
        return Response(status=404)

@app.route('/')
@app.route('/category/<category>')
@app.route('/category/<category>/page/<int:page>')
def index(category='general', page=1):
    if category not in categories:
        category = 'general'
    if page < 1 or page > 5:
        page = 1
    news_data = get_news(category, page)
    articles = news_data.get('articles', [])

    for article in articles:
        article['title'] = article.get('title', 'No title available')
        article['description'] = article.get('description', 'No description available')
        article['url'] = article.get('url', '#')
        if article.get('urlToImage'):
            article['urlToImage'] = url_for('proxy_image', image_url=article['urlToImage'])
        article['source'] = article.get('source', {'name': 'Unknown'})
        article['publishedAt'] = article.get('publishedAt', 'Unknown date')

    total_results = min(news_data.get('totalResults', 0), 100)
    total_pages = min((total_results // 20) + 1, 5)
    return render_template('index.html', articles=articles, category=category, categories=categories, page=page, total_pages=total_pages)

if __name__ == '__main__':
    app.run(debug=True)