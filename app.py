from flask import Flask, render_template, request
from newsapi import NewsApiClient

app = Flask(__name__)

# Initialize NewsApiClient
newsapi = NewsApiClient(api_key='4c1c1dd6c7ae453f8193b87839bf4bae')

# Define categories
categories = ['general', 'business', 'entertainment', 'health', 'science', 'sports', 'technology']

def get_news(category='general', page=1):
    all_articles = newsapi.get_top_headlines(
        category=category,
        language='en',
        page=page,
        page_size=20  # Number of articles per page
    )
    return all_articles

@app.route('/')
@app.route('/category/<category>')
@app.route('/category/<category>/page/<int:page>')
def index(category='general', page=1):
    if category not in categories:
        category = 'general'
    if page < 1 or page > 5:  # Limit to 5 pages
        page = 1
    news_data = get_news(category, page)
    articles = news_data.get('articles', [])

    # Print the urlToImage field for debugging
    for article in articles:
        print(article.get('urlToImage'))

    total_results = min(news_data.get('totalResults', 0), 100)  # Limit to 100 articles (5 pages * 20 articles)
    total_pages = min((total_results // 20) + 1, 5)  # Max 5 pages
    return render_template('index.html', articles=articles, category=category, categories=categories, page=page, total_pages=total_pages)

if __name__ == '__main__':
    app.run(debug=True)