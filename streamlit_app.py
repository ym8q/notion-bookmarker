import streamlit as st
import requests
from bs4 import BeautifulSoup
from notion_client import Client
from urllib.parse import urlparse, urljoin
from datetime import datetime
import time
import re
import json
import logging

# 固定の認証情報
NOTION_API_TOKEN = "ntn_i2957150244j9hSJCmlhWx1tkxlBP2MNliQk9Z3AkBHgcK"
DATABASE_ID = "1b90b0428824814fa0d9db921aa812d0"

# ロギング設定
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NotionBookmarker")

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
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 2rem;
        color: #4361EE;
    }
    .info-card {
        padding: 1.5rem;
        border-radius: 0.5rem;
        background-color: #f8f9fa;
        margin-bottom: 1.5rem;
        border-left: 4px solid #4361EE;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .domain-badge {
        display: inline-block;
        background-color: #e9ecef;
        border-radius: 2rem;
        padding: 0.25rem 0.75rem;
        font-size: 0.75rem;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .content-type-badge {
        display: inline-block;
        background-color: #4361EE;
        color: white;
        border-radius: 2rem;
        padding: 0.25rem 0.75rem;
        font-size: 0.75rem;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
        font-weight: 600;
    }
    .btn-primary {
        background-color: #4361EE;
        color: white;
    }
    .section-header {
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        color: #343a40;
        border-bottom: 2px solid #4361EE;
        padding-bottom: 0.5rem;
    }
    footer {
        margin-top: 3rem;
        text-align: center;
        color: #6c757d;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
def init_session_state():
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

init_session_state()

# ユーザーエージェント設定
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0',
    'Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.104 Mobile Safari/537.36'
]

def guess_content_type(url, soup):
    """URLとHTMLからコンテンツタイプを推測する"""
    domain = urlparse(url).netloc
    url_lower = url.lower()
    
    # URLのパターンでチェック
    if any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png', '.gif']):
        return 'image'
    elif any(ext in url_lower for ext in ['.mp4', '.avi', '.mov', '.wmv']):
        return 'video'
    elif any(ext in url_lower for ext in ['.pdf', '.doc', '.docx', '.ppt', '.xls']):
        return 'document'
    
    # アニメ関連サイト
    if any(site in domain for site in ['crunchyroll', 'funimation', 'animelab', 'myanimelist', 'anilist']):
        return 'anime'
    
    # 漫画関連サイト
    if any(site in domain for site in ['mangadex', 'mangaplus', 'comixology', 'manga-up']):
        return 'manga'
    
    # ASMR関連サイト
    if any(keyword in domain or keyword in url_lower for keyword in ['asmr', 'whispering', 'binaural']):
        return 'ASMR'
    
    # 一般的な動画サイト
    if any(site in domain for site in ['youtube.com', 'youtu.be', 'vimeo.com', 'nicovideo.jp']):
        return 'video'
    
    # 一般的な画像サイト
    if any(site in domain for site in ['instagram.com', 'flickr.com', 'imgur.com', 'pixiv.net']):
        return 'image'
    
    # SNSサイト
    if any(site in domain for site in ['twitter.com', 'facebook.com', 'linkedin.com']):
        return 'social'
    
    # ECサイト
    if any(site in domain for site in ['amazon', 'rakuten', 'shopping.yahoo']):
        return 'product'
    
    # HTMLのメタデータで判定
    if soup:
        # Open Graphタイプを確認
        og_type = soup.find('meta', property='og:type')
        if og_type and og_type.get('content'):
            og_content = og_type.get('content').lower()
            if 'video' in og_content:
                return 'video'
            elif 'article' in og_content:
                return 'article'
            elif 'product' in og_content:
                return 'product'
            elif 'music' in og_content:
                return 'music'
        
        # キーワードをチェック
        keywords_meta = soup.find('meta', attrs={'name': 'keywords'})
        if keywords_meta and keywords_meta.get('content'):
            keywords = keywords_meta.get('content').lower()
            if 'anime' in keywords:
                return 'anime'
            elif 'manga' in keywords:
                return 'manga'
            elif 'asmr' in keywords:
                return 'ASMR'
        
        # タイトルやコンテンツからキーワードをチェック
        page_text = ''
        if soup.title:
            page_text += soup.title.string.lower() if soup.title.string else ''
        
        if 'anime' in page_text:
            return 'anime'
        elif 'manga' in page_text:
            return 'manga'
        elif 'asmr' in page_text:
            return 'ASMR'
        
        # ビデオ要素をチェック
        if soup.find('video') or soup.find('iframe', src=lambda x: x and ('youtube.com' in x or 'vimeo.com' in x)):
            return 'video'
    
    # デフォルトは記事
    return 'article'

def get_metadata_advanced(url):
    """高度な方法でWebページからメタデータを取得"""
    
    # 初期化
    page_info = {
        'title': None,
        'description': None,
        'thumbnail': None,
        'url': url,
        'domain': urlparse(url).netloc,
        'content_type': None
    }
    raw_html = None
    best_html = None
    debug_info = {}
    
    # セッションを作成して再利用する
    session = requests.Session()
    
    # 複数のユーザーエージェントとヘッダーで試す
    for idx, agent in enumerate(USER_AGENTS):
        try:
            headers = {
                'User-Agent': agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                'Cache-Control': 'no-cache',
                'Referer': 'https://www.google.com/',
                'Upgrade-Insecure-Requests': '1',
                'Connection': 'keep-alive',
                'dnt': '1'
            }
            
            debug_info[f'request_{idx}'] = {
                'user_agent': agent,
                'headers': headers
            }
            
            # リクエスト送信
            response = session.get(url, headers=headers, timeout=20, allow_redirects=True)
            debug_info[f'response_{idx}'] = {
                'status_code': response.status_code,
                'content_type': response.headers.get('Content-Type', 'unknown'),
                'encoding': response.encoding
            }
            
            # ステータスコードが200以外の場合はスキップ
            if response.status_code != 200:
                continue
            
            # HTMLの解析
            html_content = response.text
            
            # 最初の成功したHTMLを保存
            if raw_html is None:
                raw_html = html_content
            
            # ページタイトルが含まれている可能性が高いHTMLを検索
            if 'title' in html_content.lower() or 'og:title' in html_content.lower():
                best_html = html_content
                break
        
        except Exception as e:
            debug_info[f'error_{idx}'] = str(e)
            continue
    
    # 最良のHTMLを使用（なければ最初のHTML）
    html_to_parse = best_html or raw_html
    
    # HTML解析
    if html_to_parse:
        try:
            soup = BeautifulSoup(html_to_parse, 'html.parser')
            
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
            
            # 4. H1 Tag
            h1 = soup.find('h1')
            if h1 and h1.text.strip():
                title_candidates.append(('h1', h1.text.strip()))
            
            # 最良のタイトルを選択
            if title_candidates:
                # タイトル候補を記録
                debug_info['title_candidates'] = title_candidates
                
                # 最初の候補を使用（優先順位順）
                page_info['title'] = title_candidates[0][1]
            else:
                page_info['title'] = f"Saved from {page_info['domain']}"
            
            # 説明文抽出
            description_candidates = []
            
            # 1. Open Graph Description
            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content'):
                description_candidates.append(('og:description', og_desc.get('content').strip()))
            
            # 2. Twitter Card Description
            twitter_desc = soup.find('meta', attrs={'name': 'twitter:description'})
            if twitter_desc and twitter_desc.get('content'):
                description_candidates.append(('twitter:description', twitter_desc.get('content').strip()))
            
            # 3. Meta Description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                description_candidates.append(('meta_description', meta_desc.get('content').strip()))
            
            # 最良の説明文を選択
            if description_candidates:
                page_info['description'] = description_candidates[0][1]
            
            # サムネイル画像抽出
            image_candidates = []
            
            # 1. Open Graph Image
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                image_url = og_image.get('content').strip()
                if not image_url.startswith(('http://', 'https://')):
                    image_url = urljoin(url, image_url)
                image_candidates.append(('og:image', image_url))
            
            # 2. Twitter Card Image
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                image_url = twitter_image.get('content').strip()
                if not image_url.startswith(('http://', 'https://')):
                    image_url = urljoin(url, image_url)
                image_candidates.append(('twitter:image', image_url))
                
            # 3. コンテンツ内の画像を探す
            content_classes = ['entry-content', 'article-content', 'content', 'post-content']
            for class_name in content_classes:
                content_area = soup.find(class_=class_name)
                if content_area:
                    images = content_area.find_all('img', src=True)
                    for img in images:
                        image_url = img['src']
                        if not image_url.startswith(('http://', 'https://')):
                            image_url = urljoin(url, image_url)
                        image_candidates.append(('content_image', image_url))
                        break  # 最初の1つだけ取得
            
            # 4. ギャラリー内の画像を探す
            gallery_classes = ['gallery', 'fotorama', 'carousel', 'slider']
            for class_name in gallery_classes:
                gallery = soup.find(class_=class_name)
                if gallery:
                    images = gallery.find_all('img', src=True)
                    for img in images:
                        image_url = img['src']
                        if not image_url.startswith(('http://', 'https://')):
                            image_url = urljoin(url, image_url)
                        image_candidates.append(('gallery_image', image_url))
                        break  # 最初の1つだけ取得
            
            # 最良の画像を選択
            if image_candidates:
                page_info['thumbnail'] = image_candidates[0][1]
            
            # コンテンツタイプを推測
            page_info['content_type'] = guess_content_type(url, soup)
            
        except Exception as e:
            debug_info['parsing_error'] = str(e)
    
    # タイトルが取得できなかった場合のフォールバック
    if not page_info['title'] or page_info['title'] == f"Saved from {page_info['domain']}":
        # MetaScraperサービスを試す
        try:
            meta_response = requests.get(f"https://api.microlink.io/?url={url}")
            if meta_response.status_code == 200:
                meta_data = meta_response.json()
                if meta_data.get('status') == 'success':
                    data = meta_data.get('data', {})
                    if data.get('title'):
                        page_info['title'] = data['title']
                    if data.get('description') and not page_info['description']:
                        page_info['description'] = data['description']
                    if data.get('image') and data['image'].get('url') and not page_info['thumbnail']:
                        page_info['thumbnail'] = data['image']['url']
        except:
            pass
    
    # 最終的なフォールバック
    if not page_info['title'] or page_info['title'] == f"Saved from {page_info['domain']}":
        # ドメイン名からの生成
        domain_parts = page_info['domain'].split('.')
        if len(domain_parts) > 1:
            page_info['title'] = f"Content from {domain_parts[-2].capitalize()}"
    
    # 結果を返す
    return page_info, raw_html, debug_info

def add_to_notion(page_info):
    """Notionデータベースにブックマーク情報を追加する"""
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

        # コンテンツタイプフィールド
        if 'カテゴリ' in db['properties'] and db['properties']['カテゴリ']['type'] == 'select':
            content_type = page_info.get('content_type', 'article')
            properties['カテゴリ'] = {'select': {'name': content_type}}
                
        # タグフィールド - ドメインをタグとして追加「しない」
        if 'タグ' in db['properties'] and db['properties']['タグ']['type'] == 'multi_select':
            # ここでタグを空の配列として設定（ドメインを追加しない）
            properties['タグ'] = {'multi_select': []}
        
        # ソースフィールド
        if 'ソース' in db['properties'] and db['properties']['ソース']['type'] == 'select':
            properties['ソース'] = {'select': {'name': page_info['domain']}}
            
        # 説明フィールド
        if '説明' in db['properties'] and db['properties']['説明']['type'] in ['rich_text', 'text']:
            if page_info.get('description'):
                properties['説明'] = {
                    'rich_text': [{'text': {'content': page_info['description'][:2000]}}]
                }
        
        # Notionページを作成
        new_page = notion.pages.create(
            parent={'database_id': DATABASE_ID},
            properties=properties
        )
        
        # サムネイル画像がある場合は、子ブロックとして追加
        if page_info.get('thumbnail'):
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
            except Exception as e:
                logger.warning(f"サムネイル画像の追加に失敗: {str(e)}")
        
        return True, new_page['url']
    
    except Exception as e:
        logger.error(f"Notion追加エラー: {str(e)}")
        return False, str(e)

# メイン画面
st.markdown("<h1 class='main-header'>Notion Bookmarker</h1>", unsafe_allow_html=True)

# URL入力フォーム
url = st.text_input("ブックマークするURLを入力", placeholder="https://example.com")

# 検索ボタンとローディング状態の管理
col1, col2 = st.columns([1, 3])
with col1:
    fetch_button = st.button("情報を取得", key="fetch_button", use_container_width=True)

if fetch_button and url:
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    st.session_state['loading'] = True
    st.session_state['page_info'] = None
    st.session_state['success'] = False
    st.session_state['error'] = None
    
    # プログレスバーを表示
    progress_bar = st.progress(0)
    for percent_complete in range(0, 101, 10):
        time.sleep(0.05)
        progress_bar.progress(percent_complete)
    
    # ウェブページ情報を抽出
    try:
        page_info, raw_html, debug_info = get_metadata_advanced(url)
        st.session_state['page_info'] = page_info
        st.session_state['raw_html'] = raw_html
    except Exception as e:
        st.session_state['error'] = f"情報取得中にエラーが発生しました: {str(e)}"
    
    st.session_state['loading'] = False
    
    # プログレスバーを完了
    progress_bar.progress(100)
    time.sleep(0.5)
    progress_bar.empty()
    
    # ページをリロード
    st.rerun()

# 情報を取得した後の表示
if st.session_state['page_info']:
    page_info = st.session_state['page_info']
    
    # 抽出した情報をカードUIで表示
    st.markdown("<h2 class='section-header'>取得した情報</h2>", unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="info-card">
        <h3 style="margin-top: 0; margin-bottom: 0.75rem; font-size: 1.4rem;">{page_info['title']}</h3>
        <a href="{page_info['url']}" target="_blank" style="color: #4361EE; text-decoration: none; font-size: 1rem; display: block; margin-bottom: 0.75rem;">{page_info['url']}</a>
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
            <div class="domain-badge">{page_info['domain']}</div>
            <div class="content-type-badge">{page_info.get('content_type', 'article')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # サムネイル表示
    if page_info.get('thumbnail'):
        st.image(page_info['thumbnail'], caption="サムネイル", use_container_width=True)
    
    # 説明
    if page_info.get('description'):
        st.markdown("**説明**:")
        st.write(page_info['description'])
    
    # 編集セクション
    st.markdown("<h2 class='section-header'>情報の編集</h2>", unsafe_allow_html=True)
    
    # タイトル編集
    edited_title = st.text_input("タイトルを編集:", value=page_info['title'])
    if edited_title != page_info['title']:
        page_info['title'] = edited_title
        st.session_state['page_info'] = page_info
        st.success("タイトルを更新しました")

    # コンテンツタイプ編集
    content_types = ['article', 'video', 'image', 'social', 'product', 'document', 'music', 'anime', 'manga', 'ASMR', 'other']
    selected_type = st.selectbox(
        "コンテンツタイプ:", 
        options=content_types, 
        index=content_types.index(page_info.get('content_type', 'article')) if page_info.get('content_type') in content_types else 0
    )
    if selected_type != page_info.get('content_type'):
        page_info['content_type'] = selected_type
        st.session_state['page_info'] = page_info
        st.success("コンテンツタイプを更新しました")
    
    # 保存ボタン
    save_col1, save_col2 = st.columns([1, 3])
    with save_col1:
        save_button = st.button("Notionに保存", key="save_button", use_container_width=True)
    
    if save_button:
        st.session_state['saving'] = True
        
        # プログレスバー
        save_progress = st.progress(0)
        for percent_complete in range(0, 101, 20):
            time.sleep(0.1)
            save_progress.progress(percent_complete)
        
        # Notionに保存
        success, result = add_to_notion(page_info)
        
        save_progress.progress(100)
        time.sleep(0.5)
        save_progress.empty()
        
        st.session_state['saving'] = False
        
        if success:
            st.session_state['success'] = True
            st.session_state['notion_url'] = result
            st.success("✅ Notionに保存しました！")
            st.markdown(f"[Notionで開く]({result})")
        else:
            st.session_state['error'] = result
            st.error(f"❌ 保存中にエラーが発生しました: {result}")

# エラーメッセージ表示
if st.session_state.get('error'):
    st.error(st.session_state['error'])

# フッター
st.markdown("""
<footer>
    <p>© 2025 Notion Bookmarker</p>
</footer>
""", unsafe_allow_html=True)