import streamlit as st
import requests
from bs4 import BeautifulSoup
from notion_client import Client
from urllib.parse import urlparse, urljoin
from datetime import datetime
import time
import re
import json
import random
import http.cookiejar
import base64
from io import BytesIO
from PIL import Image

# 固定の認証情報
NOTION_API_TOKEN = "ntn_i2957150244j9hSJCmlhWx1tkxlBP2MNliQk9Z3AkBHgcK"  # あなたの実際のAPIトークンに置き換えてください
DATABASE_ID = "1b90b0428824814fa0d9db921aa812d0"  # あなたの実際のデータベースIDに置き換えてください

# 成人向けサイト対応のスクレイパー
class AdultSiteScraper:
    def __init__(self):
        # クッキーを保存するクッキージャーを作成
        self.cookie_jar = http.cookiejar.CookieJar()
        
        # 様々なUser-Agentを用意
        self.user_agents = [
            # デスクトップブラウザ
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
            # モバイルブラウザ
            'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.104 Mobile Safari/537.36'
        ]
        
        # セッションを作成して再利用する
        self.session = requests.Session()
        self.session.cookies = self.cookie_jar
    
    def get_page_info(self, url):
        """Webページから情報を取得"""
        # 初期化
        page_info = {
            'title': None,
            'description': None,
            'thumbnail': None,
            'url': url,
            'domain': urlparse(url).netloc
        }
        raw_html = None
        debug_info = {}
        
        # ドメイン特有の処理を適用
        domain = urlparse(url).netloc
        
        # 特殊なサイトの処理
        if 'japaneseasmr.com' in domain:
            return self._process_japaneseasmr(url, page_info)
        elif 'supjav.com' in domain:
            return self._process_supjav(url, page_info)
        elif 'iwara' in domain:
            return self._process_iwara(url, page_info)
        else:
            # 一般的なサイトの処理
            return self._process_general_site(url, page_info)
    
    def _process_japaneseasmr(self, url, page_info):
        """japaneseasmr.comのページ処理"""
        debug_info = {}
        
        try:
            # 成人向けサイト用のヘッダー
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'cross-site',
                'Pragma': 'no-cache',
                'Cache-Control': 'no-cache'
            }
            
            # リクエスト送信 
            response = self.session.get(url, headers=headers, timeout=20)
            
            if response.status_code == 200:
                raw_html = response.text
                soup = BeautifulSoup(raw_html, 'html.parser')
                
                # タイトル抽出
                if soup.title and soup.title.string and 'just a moment' not in soup.title.string.lower():
                    page_info['title'] = soup.title.string.strip()
                else:
                    # 記事タイトルを探す
                    article_title = soup.find('h1', class_='article-title')
                    if article_title:
                        page_info['title'] = article_title.text.strip()
                
                # サムネイル画像を抽出 - japaneseasmr特有の処理
                # 方法1: アイキャッチ画像
                thumbnail = soup.find('div', class_='eye-catch')
                if thumbnail and thumbnail.find('img'):
                    img = thumbnail.find('img')
                    if img.get('src'):
                        page_info['thumbnail'] = urljoin(url, img.get('src'))
                
                # 方法2: コンテンツ内の最初の画像
                if not page_info['thumbnail']:
                    article_content = soup.find('div', class_='article-body')
                    if article_content:
                        img_tags = article_content.find_all('img')
                        for img in img_tags:
                            if img.get('src') and not img.get('src').endswith(('.gif', 'spacer.png', 'blank.gif')):
                                page_info['thumbnail'] = urljoin(url, img.get('src'))
                                break
                
                # 方法3: img要素のdata-src属性
                if not page_info['thumbnail']:
                    for img in soup.find_all('img', attrs={'data-src': True}):
                        if not img.get('data-src').endswith(('.gif', 'spacer.png', 'blank.gif')):
                            page_info['thumbnail'] = urljoin(url, img.get('data-src'))
                            break
                
                # 方法4: articleタグの背景画像
                if not page_info['thumbnail']:
                    article = soup.find('article')
                    if article:
                        style = article.get('style')
                        if style and 'background-image' in style:
                            # 正規表現でURL抽出
                            bg_match = re.search(r'background-image:\s*url\([\'"]?(.*?)[\'"]?\)', style)
                            if bg_match:
                                page_info['thumbnail'] = urljoin(url, bg_match.group(1))
                
                # 説明抽出
                meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
                if meta_desc and meta_desc.get('content'):
                    page_info['description'] = meta_desc.get('content').strip()
                else:
                    # 記事の最初の段落
                    first_para = soup.find('div', class_='article-body').find('p')
                    if first_para:
                        page_info['description'] = first_para.text.strip()[:200]
            
            return page_info, raw_html, debug_info
            
        except Exception as e:
            debug_info['error'] = str(e)
            return page_info, None, debug_info
    
    def _process_supjav(self, url, page_info):
        """supjav.comのページ処理"""
        debug_info = {}
        
        try:
            # 成人向けサイト用のヘッダー
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cookie': 'kt_tcookie=1; kt_is_visited=1; kt_ips=127.0.0.1',  # 成人向けサイトで必要なことがある
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            }
            
            # リクエスト送信
            response = self.session.get(url, headers=headers, timeout=20)
            
            if response.status_code == 200:
                raw_html = response.text
                soup = BeautifulSoup(raw_html, 'html.parser')
                
                # タイトル抽出
                if soup.title and soup.title.string and 'just a moment' not in soup.title.string.lower():
                    page_info['title'] = soup.title.string.strip()
                else:
                    # 記事タイトル要素を探す
                    article_title = soup.find('h1', class_='article-title') or soup.find('h1', class_='entry-title')
                    if article_title:
                        page_info['title'] = article_title.text.strip()
                
                # サムネイル画像を抽出 - supjav特有の処理
                # 方法1: サムネイル専用クラス
                for class_name in ['thumb', 'thumbnail', 'wp-post-image', 'video-thumb']:
                    if not page_info['thumbnail']:
                        thumbnail = soup.find('img', class_=class_name)
                        if thumbnail and thumbnail.get('src'):
                            page_info['thumbnail'] = urljoin(url, thumbnail.get('src'))
                
                # 方法2: ビデオプレビュー画像
                if not page_info['thumbnail']:
                    video_preview = soup.find('div', class_='video-preview')
                    if video_preview and video_preview.find('img'):
                        img = video_preview.find('img')
                        if img.get('src'):
                            page_info['thumbnail'] = urljoin(url, img.get('src'))
                
                # 方法3: データ属性のある画像
                if not page_info['thumbnail']:
                    for attr in ['data-src', 'data-lazy-src', 'data-original']:
                        for img in soup.find_all('img', attrs={attr: True}):
                            if not img.get(attr).endswith(('.gif', 'spacer.png')):
                                page_info['thumbnail'] = urljoin(url, img.get(attr))
                                break
                        if page_info['thumbnail']:
                            break
                
                # 方法4: スタイル属性から背景画像を抽出
                if not page_info['thumbnail']:
                    elements_with_style = soup.find_all(style=re.compile(r'background(-image)?:\s*url'))
                    for element in elements_with_style:
                        style = element.get('style')
                        bg_match = re.search(r'background(-image)?:\s*url\([\'"]?(.*?)[\'"]?\)', style)
                        if bg_match:
                            page_info['thumbnail'] = urljoin(url, bg_match.group(2))
                            break
                
                # 方法5: メタタグからの抽出
                if not page_info['thumbnail']:
                    og_image = soup.find('meta', property='og:image')
                    if og_image and og_image.get('content'):
                        page_info['thumbnail'] = og_image.get('content')
                
                # 説明抽出
                meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
                if meta_desc and meta_desc.get('content'):
                    page_info['description'] = meta_desc.get('content').strip()
            
            return page_info, raw_html, debug_info
            
        except Exception as e:
            debug_info['error'] = str(e)
            return page_info, None, debug_info
    
    def _process_iwara(self, url, page_info):
        """iwaraサイトの処理"""
        debug_info = {}
        
        try:
            # iwaraサイト用のヘッダー
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                'Referer': 'https://www.iwara.tv/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # リクエスト送信
            response = self.session.get(url, headers=headers, timeout=20)
            
            if response.status_code == 200:
                raw_html = response.text
                soup = BeautifulSoup(raw_html, 'html.parser')
                
                # タイトル抽出
                title_candidates = []
                
                # 1. video-titleクラスを探す
                video_title = soup.find(class_='video-title')
                if video_title and video_title.text.strip():
                    title_candidates.append(video_title.text.strip())
                
                # 2. nodeのタイトルを探す
                node_title = soup.find(class_='node-title')
                if node_title and node_title.text.strip():
                    title_candidates.append(node_title.text.strip())
                
                # 3. h1タグを探す
                h1 = soup.find('h1')
                if h1 and h1.text.strip():
                    title_candidates.append(h1.text.strip())
                
                # 4. ページタイトル
                if soup.title and soup.title.string:
                    title_text = soup.title.string.strip()
                    # "iwara"の部分を削除
                    title_text = re.sub(r'\s*[|\-–—]\s*iwara.*$', '', title_text, flags=re.IGNORECASE)
                    title_candidates.append(title_text)
                
                # 最適なタイトルを選択
                if title_candidates:
                    page_info['title'] = title_candidates[0]
                
                # サムネイル画像抽出
                # 1. video-thumbnailクラス
                video_thumb = soup.find('img', class_='video-thumbnail')
                if video_thumb and video_thumb.get('src'):
                    page_info['thumbnail'] = urljoin(url, video_thumb.get('src'))
                
                # 2. OGP画像
                if not page_info['thumbnail']:
                    og_image = soup.find('meta', property='og:image')
                    if og_image and og_image.get('content'):
                        page_info['thumbnail'] = og_image.get('content')
                
                # 3. ビデオプレビュー画像
                if not page_info['thumbnail']:
                    video_preview = soup.find('div', class_='video-preview')
                    if video_preview and video_preview.find('img'):
                        img = video_preview.find('img')
                        if img.get('src'):
                            page_info['thumbnail'] = urljoin(url, img.get('src'))
                
                # 説明抽出
                meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
                if meta_desc and meta_desc.get('content'):
                    page_info['description'] = meta_desc.get('content').strip()
            
            return page_info, raw_html, debug_info
            
        except Exception as e:
            debug_info['error'] = str(e)
            return page_info, None, debug_info
    
    def _process_general_site(self, url, page_info):
        """一般的なサイトの処理"""
        debug_info = {}
        
        try:
            # 一般的なヘッダー
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            }
            
            # リクエスト送信
            response = self.session.get(url, headers=headers, timeout=20)
            
            if response.status_code == 200:
                raw_html = response.text
                soup = BeautifulSoup(raw_html, 'html.parser')
                
                # タイトル抽出
                title_candidates = []
                
                # 1. Open Graph Title
                og_title = soup.find('meta', property='og:title')
                if og_title and og_title.get('content'):
                    title_candidates.append(('og:title', og_title.get('content').strip()))
                
                # 2. Twitter Card Title
                twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
                if twitter_title and twitter_title.get('content'):
                    title_candidates.append(('twitter:title', twitter_title.get('content').strip()))
                
                # 3. HTML Title
                if soup.title and soup.title.string:
                    title_text = soup.title.string.strip()
                    # サイト名を除去する処理
                    title_text = re.sub(r'\s*[|\-–—]\s*.*$', '', title_text)
                    title_candidates.append(('html_title', title_text))
                
                # 最良のタイトルを選択
                if title_candidates:
                    page_info['title'] = title_candidates[0][1]
                else:
                    page_info['title'] = f"Saved from {page_info['domain']}"
                
                # サムネイル画像抽出
                # 1. Open Graph Image
                og_image = soup.find('meta', property='og:image')
                if og_image and og_image.get('content'):
                    page_info['thumbnail'] = og_image.get('content')
                
                # 2. Twitter Card Image
                if not page_info['thumbnail']:
                    twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
                    if twitter_image and twitter_image.get('content'):
                        page_info['thumbnail'] = twitter_image.get('content')
                
                # 3. 最初の大きな画像
                if not page_info['thumbnail']:
                    for img in soup.find_all('img', attrs={'width': True, 'height': True}):
                        try:
                            width = int(img.get('width'))
                            height = int(img.get('height'))
                            if width >= 100 and height >= 100:
                                page_info['thumbnail'] = urljoin(url, img.get('src'))
                                break
                        except:
                            pass
                
                # 説明抽出
                meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
                if meta_desc and meta_desc.get('content'):
                    page_info['description'] = meta_desc.get('content').strip()
            
            return page_info, raw_html, debug_info
            
        except Exception as e:
            debug_info['error'] = str(e)
            return page_info, None, debug_info

# アプリのタイトルとスタイル設定
st.set_page_config(
    page_title="Notion Bookmarker",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# カスタムCSSを適用
st.markdown("""
<style>
    /* 全体のスタイリング */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 800px;
    }
    
    /* テキストスタイル */
    h1, h2, h3 {
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 500;
        color: #1E1E1E;
    }
    
    h1 {
        font-size: 2.5rem;
        margin-bottom: 1.5rem;
    }
    
    h2 {
        font-size: 1.8rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
        color: #2E2E2E;
    }
    
    /* カードUIスタイル */
    .css-nahz7x, div.stButton > button, [data-testid="stForm"] {
        border-radius: 12px;
    }
    
    /* 入力フィールドのスタイル */
    .stTextInput > div > div > input {
        padding: 0.75rem 1rem;
        font-size: 1.1rem;
        border-radius: 8px;
        border: 1px solid #E0E0E0;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* ボタンスタイル */
    div.stButton > button {
        background-color: #4361EE;
        color: white;
        font-weight: 500;
        padding: 0.5rem 1.25rem;
        font-size: 1rem;
        border: none;
        box-shadow: 0 2px 5px rgba(67, 97, 238, 0.3);
        transition: all 0.2s ease;
    }
    
    div.stButton > button:hover {
        background-color: #3A56D4;
        box-shadow: 0 4px 10px rgba(67, 97, 238, 0.4);
        transform: translateY(-1px);
    }
    
    /* 情報カードのスタイル */
    .info-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        margin: 1.5rem 0;
        border-left: 4px solid #4361EE;
    }
    
    /* ドメインバッジ */
    .domain-badge {
        display: inline-block;
        background-color: #F3F4F6;
        color: #4B5563;
        font-size: 0.85rem;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        margin-top: 0.5rem;
        font-weight: 500;
    }
    
    /* サムネイル画像のスタイル */
    .thumbnail-container {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
    
    /* 成功メッセージのスタイル */
    .success-message {
        background-color: #10B981;
        color: white;
        padding: 1rem;
        border-radius: 8px;
        display: flex;
        align-items: center;
        margin: 1rem 0;
    }
    
    .success-message svg {
        margin-right: 0.75rem;
    }
    
    /* エラーメッセージのスタイル */
    .error-message {
        background-color: #EF4444;
        color: white;
        padding: 1rem;
        border-radius: 8px;
        display: flex;
        align-items: center;
        margin: 1rem 0;
    }
    
    /* モバイル最適化 */
    @media (max-width: 768px) {
        .stButton button {
            width: 100%;
            margin-bottom: 0.75rem;
            padding: 0.75rem 1rem;
        }
        
        h1 {
            font-size: 2rem;
        }
        
        .info-card {
            padding: 1.25rem;
        }
    }
    
    /* フッタースタイル */
    footer {
        margin-top: 3rem;
        padding-top: 1.5rem;
        border-top: 1px solid #E0E0E0;
        color: #6B7280;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
if 'page_info' not in st.session_state:
    st.session_state['page_info'] = None
if 'loading' not in st.session_state:
    st.session_state['loading'] = False
if 'saving' not in st.session_state:
    st.session_state['saving'] = False
if 'success' not in st.session_state:
    st.session_state['success'] = False
if 'error' not in st.session_state:
    st.session_state['error'] = None
if 'notion_url' not in st.session_state:
    st.session_state['notion_url'] = None
if 'raw_html' not in st.session_state:
    st.session_state['raw_html'] = None
if 'scraper' not in st.session_state:
    st.session_state['scraper'] = AdultSiteScraper()

# メイン画面表示 - ヘッダー部分
st.markdown("<h1>Notion Bookmarker</h1>", unsafe_allow_html=True)
st.markdown("""
<div style="margin-bottom: 2rem;">
    <p style="font-size: 1.1rem; color: #4B5563; margin-bottom: 1.5rem;">
        ウェブページの情報を簡単にNotionデータベースに保存します。
    </p>
</div>
""", unsafe_allow_html=True)

# メタデータリクエスト
def get_metadata_advanced(url):
    """Webページからメタデータを取得（成人向けサイト対応）"""
    scraper = st.session_state['scraper']
    return scraper.get_page_info(url)

# Notionに情報を追加する関数
def add_to_notion(page_info):
    try:
        # Notionクライアントを初期化
        notion = Client(auth=NOTION_API_TOKEN)
        
        # データベースが存在するか確認
        db = notion.databases.retrieve(database_id=DATABASE_ID)
        
        # データベースのプロパティを確認
        properties = {}
        
        # タイトルフィールド (必須) を検出
        title_field = None
        for name, prop in db['properties'].items():
            if prop['type'] == 'title':
                title_field = name
                properties[name] = {
                    'title': [{'text': {'content': page_info['title']}}]
                }
                break
        
        if not title_field:
            return False, "タイトル用のプロパティが見つかりません"
        
        # URLフィールド
        if 'URL' in db['properties'] and db['properties']['URL']['type'] == 'url':
            properties['URL'] = {'url': page_info['url']}
        
        # タグフィールド
        if 'タグ' in db['properties'] and db['properties']['タグ']['type'] == 'multi_select':
            properties['タグ'] = {'multi_select': []}
        
        # 作成日時フィールド
        if '作成日時' in db['properties'] and db['properties']['作成日時']['type'] == 'date':
            properties['作成日時'] = {
                'date': {
                    'start': datetime.now().isoformat()
                }
            }
        
        # Notionページを作成
        new_page = notion.pages.create(
            parent={'database_id': DATABASE_ID},
            properties=properties
        )
        
        # サムネイル画像がある場合は、子ブロックとして追加
        if page_info['thumbnail']:
            try:
                notion.blocks.children.append(
                    block_id=new_page['id'],
                    children=[
                        {
                            "object": "block",
                            "type": "image",
                            "image": {
                                "type": "external",
                                "external": {
                                    "url": page_info['thumbnail']
                                }
                            }
                        }
                    ]
                )
            except Exception:
                pass
        
        return True, new_page['url']
    
    except Exception as e:
        return False, str(e)

# URL入力エリア - スタイリッシュなデザイン
st.markdown("""
<div style="background-color: white; padding: 1.75rem; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); margin-bottom: 2rem;">
    <h3 style="margin-top: 0; margin-bottom: 1rem; font-size: 1.3rem; color: #333;">📌 ウェブページのURLを入力</h3>
</div>
""", unsafe_allow_html=True)

# URLの入力フォーム
url = st.text_input("", placeholder="https://example.com", label_visibility="collapsed")

# 検索ボタンとローディング状態の管理
col1, col2 = st.columns([1, 3])
with col1:
    fetch_button = st.button("情報を取得", key="fetch_button", use_container_width=True)
with col2:
    pass

if fetch_button and url:
    st.session_state['loading'] = True
    st.session_state['page_info'] = None
    st.session_state['success'] = False
    st.session_state['error'] = None
    
    # プログレスバーを表示
    progress_bar = st.progress(0)
    
    # ウェブページ情報を抽出（改良版）
    with st.spinner("ページ情報を取得中..."):
        for percent_complete in range(0, 80, 10):
            time.sleep(0.1)
            progress_bar.progress(percent_complete)
            
        page_info, raw_html, debug_info = get_metadata_advanced(url)
        
        for percent_complete in range(80, 101, 5):
            time.sleep(0.05)
            progress_bar.progress(percent_complete)
    
    st.session_state['page_info'] = page_info
    st.session_state['raw_html'] = raw_html
    st.session_state['debug_info'] = debug_info
    st.session_state['loading'] = False
    
    # プログレスバーを完了状態にして少し待ってから消す
    progress_bar.progress(100)
    time.sleep(0.5)
    progress_bar.empty()
    
    # ページをリロードして、下のコンテンツを表示
    st.rerun()

# 情報を取得した後の表示
if st.session_state['page_info']:
    page_info = st.session_state['page_info']
    
    # 抽出した情報をカードUIで表示
    st.markdown("""
    <h2>取得した情報</h2>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="info-card">
        <h3 style="margin-top: 0; margin-bottom: 0.75rem; font-size: 1.4rem;">{page_info['title']}</h3>
        <a href="{page_info['url']}" target="_blank" style="color: #4361EE; text-decoration: none; font-size: 1rem; display: block; margin-bottom: 0.75rem;">{page_info['url']}</a>
        <div class="domain-badge">{page_info['domain']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # サムネイル - use_container_widthを使用
    if page_info['thumbnail']:
        st.image(page_info['thumbnail'], caption="サムネイル", use_container_width=True)
    else:
        st.warning("サムネイル画像を取得できませんでした。")
        
        # 手動でサムネイルURLを入力するオプション
        manual_thumbnail = st.text_input("サムネイルURLを手動で入力:", placeholder="https://example.com/image.jpg")
        if manual_thumbnail:
            try:
                st.image(manual_thumbnail, caption="入力されたサムネイル", use_container_width=True)
                page_info['thumbnail'] = manual_thumbnail
                st.session_state['page_info'] = page_info
                st.success("サムネイルを更新しました")
            except Exception as e:
                st.error(f"画像の読み込みに失敗しました: {str(e)}")
    
    # 説明
    if page_info.get('description'):
        st.markdown("**説明**:")
        st.write(page_info['description'])
    
    # タイトル手動編集機能
    st.subheader("タイトルの編集")
    edited_title = st.text_input("タイトルを編集:", value=page_info['title'])
    if edited_title != page_info['title']:
        page_info['title'] = edited_title
        st.session_state['page_info'] = page_info
        st.success("タイトルを更新しました")
    
    # 保存ボタン - アクセントカラー使用
    save_col1, save_col2 = st.columns([1, 3])
    with save_col1:
        save_button = st.button("Notionに保存", key="save_button", use_container_width=True)
    with save_col2:
        pass
    
    # 保存ボタンが押されたとき
    if save_button:
        st.session_state['saving'] = True
        
        # プログレスバーを表示
        save_progress = st.progress(0)
        for percent_complete in range(0, 101, 20):
            time.sleep(0.1)  # シミュレーションのための遅延
            save_progress.progress(percent_complete)
        
        # Notionに保存
        success, result = add_to_notion(page_info)
        
        # プログレスバーを完了状態にして少し待ってから消す
        save_progress.progress(100)
        time.sleep(0.5)
        save_progress.empty()
        
        st.session_state['saving'] = False
        st.session_state['success'] = success
        
        if success:
            st.session_state['notion_url'] = result
        else:
            st.session_state['error'] = result
        
        # ページをリロードして結果を表示
        st.rerun()
    
    # 保存成功時の表示
    if st.session_state['success']:
        st.success("✅ Notionに保存しました！")
        
        if st.session_state.get('notion_url'):
            st.markdown(f"[Notionで開く]({st.session_state['notion_url']})")
    
    # エラー時の表示
    if st.session_state['error']:
        st.error(f"❌ 保存中にエラーが発生しました: {st.session_state['error']}")

# フッター
st.markdown("""
<footer>
    <p>© 2025 Notion Bookmarker - すべてのコンテンツをNotionに保存</p>
</footer>
""", unsafe_allow_html=True)