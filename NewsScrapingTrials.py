import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse
import time
import json
from typing import List, Dict, Optional

class NewsSearchScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Common search form selectors and URL patterns
        self.search_patterns = {
            'form_selectors': [
                'form[action*="search"]',
                'form[id*="search"]',
                'form[class*="search"]',
                'form input[name*="search"]',
                '.search-form',
                '#search-form'
            ],
            'input_selectors': [
                'input[name*="search"]',
                'input[name="q"]',
                'input[name="query"]',
                'input[name="s"]',
                'input[type="search"]',
                'input[placeholder*="search" i]'
            ],
            'url_patterns': [
                '/search',
                '/search.php',
                '/search.html',
                '/?s=',
                '/search?q=',
                '/search?query='
            ]
        }

    def find_search_functionality(self, base_url: str) -> Optional[Dict]:
        """Find search functionality on a website"""
        try:
            response = self.session.get(base_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Method 1: Look for search forms
            for selector in self.search_patterns['form_selectors']:
                forms = soup.select(selector)
                for form in forms:
                    action = form.get('action', '')
                    method = form.get('method', 'GET').upper()
                    
                    # Find input field
                    input_field = None
                    for input_sel in self.search_patterns['input_selectors']:
                        input_field = form.select_one(input_sel)
                        if input_field:
                            break
                    
                    if input_field:
                        return {
                            'type': 'form',
                            'action': urljoin(base_url, action) if action else base_url,
                            'method': method,
                            'input_name': input_field.get('name', 'q')
                        }
            
            # Method 2: Look for search input fields without forms
            for selector in self.search_patterns['input_selectors']:
                input_field = soup.select_one(selector)
                if input_field:
                    return {
                        'type': 'input',
                        'base_url': base_url,
                        'input_name': input_field.get('name', 'q')
                    }
            
            # Method 3: Try common URL patterns
            for pattern in self.search_patterns['url_patterns']:
                test_url = urljoin(base_url, pattern)
                try:
                    test_response = self.session.head(test_url, timeout=5)
                    if test_response.status_code == 200:
                        return {
                            'type': 'url_pattern',
                            'search_url': test_url,
                            'param_name': 'q' if '?q=' in pattern else 's'
                        }
                except:
                    continue
                    
        except Exception as e:
            print(f"Error finding search functionality: {e}")
        
        return None

    def perform_search(self, search_info: Dict, keywords: str) -> Optional[str]:
        """Perform search using the found search functionality"""
        try:
            if search_info['type'] == 'form':
                if search_info['method'] == 'POST':
                    data = {search_info['input_name']: keywords}
                    response = self.session.post(search_info['action'], data=data, timeout=10)
                else:
                    params = {search_info['input_name']: keywords}
                    response = self.session.get(search_info['action'], params=params, timeout=10)
                    
            elif search_info['type'] == 'input':
                params = {search_info['input_name']: keywords}
                response = self.session.get(search_info['base_url'], params=params, timeout=10)
                
            elif search_info['type'] == 'url_pattern':
                if '?' in search_info['search_url']:
                    search_url = f"{search_info['search_url']}{keywords}"
                else:
                    search_url = f"{search_info['search_url']}?{search_info['param_name']}={keywords}"
                response = self.session.get(search_url, timeout=10)
            
            response.raise_for_status()
            return response.text
            
        except Exception as e:
            print(f"Error performing search: {e}")
            return None

    def extract_search_results(self, html_content: str, base_url: str) -> List[str]:
        """Extract article URLs from search results"""
        soup = BeautifulSoup(html_content, 'html.parser')
        article_urls = []
        
        # Common selectors for article links in search results
        selectors = [
            'article a[href]',
            '.search-result a[href]',
            '.search-results a[href]',
            '.result a[href]',
            '.post a[href]',
            '.entry a[href]',
            'h1 a[href], h2 a[href], h3 a[href]',
            'a[href*="/article/"]',
            'a[href*="/news/"]',
            'a[href*="/post/"]'
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    if self.is_article_url(full_url) and full_url not in article_urls:
                        article_urls.append(full_url)
        
        # Fallback: get all links and filter
        if not article_urls:
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    if self.is_article_url(full_url):
                        article_urls.append(full_url)
        
        return list(set(article_urls))[:10]  # Limit to first 10 unique URLs

    def is_article_url(self, url: str) -> bool:
        """Check if URL likely points to an article"""
        url_lower = url.lower()
        article_indicators = [
            '/article/', '/news/', '/post/', '/story/', '/blog/',
            '/press-release/', '/report/', '/editorial/'
        ]
        
        # Check for article indicators
        for indicator in article_indicators:
            if indicator in url_lower:
                return True
        
        # Check for date patterns (common in news URLs)
        if re.search(r'/\d{4}/\d{2}/', url) or re.search(r'/\d{4}-\d{2}-\d{2}', url):
            return True
            
        # Avoid common non-article URLs
        avoid_patterns = [
            '/search', '/category/', '/tag/', '/author/', '/page/',
            '/contact', '/about', '/privacy', '/terms', '/login',
            '.pdf', '.jpg', '.png', '.gif', 'javascript:'
        ]
        
        for pattern in avoid_patterns:
            if pattern in url_lower:
                return False
                
        return True

    def extract_article_data(self, url: str) -> Dict:
        """Extract article data from a single article URL"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = self.extract_title(soup)
            
            # Extract author
            author = self.extract_author(soup)
            
            # Extract date and timestamp
            date, timestamp = self.extract_date_timestamp(soup)
            
            # Extract image
            image = self.extract_image(soup, url)
            
            # Extract content/summary
            content = self.extract_content(soup)
            
            return {
                'url': url,
                'title': title,
                'author': author,
                'date': date,
                'timestamp': timestamp,
                'image': image,
                'content': content
            }
            
        except Exception as e:
            print(f"Error extracting article data from {url}: {e}")
            return {
                'url': url,
                'title': None,
                'author': None,
                'date': None,
                'timestamp': None,
                'image': None,
                'content': None,
                'error': str(e)
            }

    def extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article title"""
        selectors = [
            'h1',
            '.entry-title',
            '.post-title',
            '.article-title',
            '[class*="title"]',
            'title'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element and element.get_text(strip=True):
                return element.get_text(strip=True)
        
        return None

    def extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article author"""
        selectors = [
            '.author',
            '.byline',
            '.post-author',
            '.entry-author',
            '[class*="author"]',
            '[rel="author"]',
            '.by-author'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element and element.get_text(strip=True):
                return element.get_text(strip=True)
        
        # Check meta tags
        meta_author = soup.find('meta', {'name': 'author'})
        if meta_author and meta_author.get('content'):
            return meta_author.get('content')
            
        return None

    def extract_date_timestamp(self, soup: BeautifulSoup) -> tuple:
        """Extract date and timestamp"""
        # Look for datetime attributes
        time_elements = soup.find_all(['time', 'span', 'div'], attrs={'datetime': True})
        for element in time_elements:
            datetime_str = element.get('datetime')
            if datetime_str:
                try:
                    dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                    return dt.strftime('%Y-%m-%d'), int(dt.timestamp())
                except:
                    continue
        
        # Look for date patterns in text
        date_selectors = [
            '.date', '.post-date', '.entry-date', '.published',
            '[class*="date"]', '[class*="time"]'
        ]
        
        for selector in date_selectors:
            element = soup.select_one(selector)
            if element:
                date_text = element.get_text(strip=True)
                parsed_date = self.parse_date_string(date_text)
                if parsed_date:
                    return parsed_date.strftime('%Y-%m-%d'), int(parsed_date.timestamp())
        
        return None, None

    def parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Parse various date string formats"""
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{2}/\d{2}/\d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})',
            r'(\w+ \d{1,2}, \d{4})',
            r'(\d{1,2} \w+ \d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    date_part = match.group(1)
                    # Try different parsing formats
                    formats = ['%Y-%m-%d', '%m/%d/%Y', '%B %d, %Y', '%d %B %Y']
                    for fmt in formats:
                        try:
                            return datetime.strptime(date_part, fmt)
                        except:
                            continue
                except:
                    continue
        
        return None

    def extract_image(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract main article image"""
        # Look for featured image
        selectors = [
            '.featured-image img',
            '.post-image img',
            '.article-image img',
            '.entry-image img',
            'img[class*="featured"]',
            'img[class*="main"]'
        ]
        
        for selector in selectors:
            img = soup.select_one(selector)
            if img and img.get('src'):
                return urljoin(base_url, img.get('src'))
        
        # Look for og:image meta tag
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return urljoin(base_url, og_image.get('content'))
        
        # Fallback to first image in content
        content_area = soup.find(['article', '.content', '.post-content', '.entry-content'])
        if content_area:
            img = content_area.find('img')
            if img and img.get('src'):
                return urljoin(base_url, img.get('src'))
        
        return None

    def extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article content or summary"""
        # Look for main content area
        content_selectors = [
            '.post-content',
            '.entry-content',
            '.article-content',
            '.content',
            'article',
            '.main-content'
        ]
        
        for selector in content_selectors:
            content_area = soup.select_one(selector)
            if content_area:
                # Remove unwanted elements
                for unwanted in content_area.find_all(['script', 'style', 'nav', 'aside', '.ads', '.advertisement']):
                    unwanted.decompose()
                
                text = content_area.get_text(separator=' ', strip=True)
                if len(text) > 100:  # Ensure we have substantial content
                    return text[:1000] + '...' if len(text) > 1000 else text
        
        # Fallback to meta description
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc.get('content')
        
        return None

    def search_news_site(self, base_url: str, keywords: str, max_articles: int = 5) -> List[Dict]:
        """Main method to search a news site and extract article data"""
        print(f"Searching {base_url} for: {keywords}")
        
        # Find search functionality
        search_info = self.find_search_functionality(base_url)
        if not search_info:
            print("Could not find search functionality on this site")
            return []
        
        print(f"Found search method: {search_info['type']}")
        

        search_results_html = self.perform_search(search_info, keywords)
        if not search_results_html:
            print("Could not perform search")
            return []
        

        article_urls = self.extract_search_results(search_results_html, base_url)
        if not article_urls:
            print("No article URLs found in search results")
            return []
        
        print(f"Found {len(article_urls)} article URLs")
        

        articles_data = []
        for i, url in enumerate(article_urls[:max_articles]):
            print(f"Extracting data from article {i+1}/{min(max_articles, len(article_urls))}")
            article_data = self.extract_article_data(url)
            articles_data.append(article_data)
            time.sleep(1)  
        
        return articles_data


def search_multiple_news_sites(sites: List[str], keywords: str, max_articles_per_site: int = 3):
    """Search multiple news sites for keywords"""
    scraper = NewsSearchScraper()
    all_results = {}
    
    for site in sites:
        try:
            results = scraper.search_news_site(site, keywords, max_articles_per_site)
            all_results[site] = results
            print(f"Completed search for {site}: {len(results)} articles found\n")
        except Exception as e:
            print(f"Error searching {site}: {e}\n")
            all_results[site] = []
    
    return all_results



if __name__ == "__main__":

    news_sites = [

        # "https://timesofindia.indiatimes.com",
        # "https://www.dailythanthi.com",
        # "https://www.republicworld.com",
        # "https://bangaloremirror.indiatimes.com",
        # "https://www.dinamalar.com",
        'amarasom.com', 
        'https://assamtribune.com/',
        'https://www.dailyexcelsior.com/',
        'https://www.dailythanthi.com/',
        'https://dainikagradoot.in/',
        'https://bartamanpatrika.com/',
        'https://bodolandnews.in/',
        'bodonews.org',
        'bodolandnews.in',
        'https://www.jagran.com/',
        'https://www.gomantaktimes.com/',
        'https://jagbani.punjabkesari.in/',
        'https://www.bhaskar.com/',
        'https://www.kannadaprabha.com/',
        'http://jugasankhaepaper.com/',
        'https://kashmirreader.com/'
      
    ]
    

    keywords = "fire accident"
    
 
    results = search_multiple_news_sites(news_sites, keywords, max_articles_per_site=10)
    

    for site, articles in results.items():
        print(f"\n{'='*50}")
        print(f"Results from {site}")
        print(f"{'='*50}")
        
        for i, article in enumerate(articles, 1):
            print(f"\nArticle {i}:")
            print(f"Title: {article.get('title', 'N/A')}")
            print(f"Author: {article.get('author', 'N/A')}")
            print(f"Date: {article.get('date', 'N/A')}")
            print(f"URL: {article.get('url', 'N/A')}")
            if article.get('content'):
                print(f"Summary: {article['content'][:200]}...")
    
    # JSON file
    with open('news_search_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
