from newsapi import NewsApiClient

# Init
newsapi = NewsApiClient(api_key='48806b5843074639b77860448da1687a')

# /v2/everything
all_articles = newsapi.get_top_headlines(country='au',
                                      language='en',)
print(all_articles)