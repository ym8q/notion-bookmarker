import streamlit as st
import requests
from bs4 import BeautifulSoup
from notion_client import Client
from urllib.parse import urlparse, urljoin
from datetime import datetime
import time
import re
import json

# 固定の認証情報
NOTION_API_TOKEN = "ntn_i2957150244j9hSJCmlhWx1tkxlBP2MNliQk9Z3AkBHgcK"  # あなたの実際のAPIトークンに置き換えてください
DATABASE_ID = "1b90b0428824814fa0d9db921aa812d0"  # あなたの実際のデータベースIDに置き換えてください

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
    /* ここにCSSコードを入れる */
    /* テキストスタイル */
    h1, h2, h3 {
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 500;
        color: #1E1E1E;
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
    
    /* 情報カードのスタイル */
    .info-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        margin: 1.5rem 0;
        border-left: 4px solid #4361EE;
    }
    
    /* ドメインバッジなど、その他のスタイル */
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

# メイン画面表示 - ヘッダー部分
st.markdown("<h1>Notion Bookmarker</h1>", unsafe_allow_html=True)
st.markdown("""
<div style="margin-bottom: 2rem;">
    <p style="font-size: 1.1rem; color: #4B5563; margin-bottom: 1.5rem;">
        ウェブページの情報を簡単にNotionデータベースに保存します。
    </p>
</div>
""", unsafe_allow_html=True)

# Webクリッパーのような動作をするための関数
def fetch_page_info_like_clipper(url):
    # 基本情報の初期化
    domain = urlparse(url).netloc
    page_info = {
        'title': f"Saved from {domain}",
        'url': url,
        'description': "No description available",
        'thumbnail': "",
        'domain': domain
    }
    
    # Notionウェブクリッパーのような多様なリクエストヘッダーを設定
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.google.com/',  # リファラーを追加
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }
    
    # リクエストの偽装を強化するセッション
    session = requests.Session()
    session.headers.update(headers)
    
    # 特定サイト向けの特別処理
    special_site_handlers = {
        'iwara': handle_iwara_site
    }
    
    # 特定サイト向けの処理を適用
    for site_key, handler in special_site_handlers.items():
        if site_key in domain:
            return handler(url, session, page_info)
    
    # 通常の処理
    try:
        # ページコンテンツを取得
        response = session.get(url, timeout=15, allow_redirects=True)
        response.raise_for_status()  # エラーがあれば例外を発生
        
        # HTMLを解析
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # タイトル取得 - Notionクリッパーに似た優先順位
        title = extract_title(soup, url)
        if title:
            page_info['title'] = title.strip()
        
        # 説明取得
        description = extract_description(soup)
        if description:
            page_info['description'] = description.strip()
        
        # サムネイル画像取得
        thumbnail = extract_thumbnail(soup, url)
        if thumbnail:
            page_info['thumbnail'] = thumbnail
        
        return page_info
    
    except Exception as e:
        st.error(f"ページ情報の取得中にエラーが発生しました: {str(e)}")
        return page_info

# タイトル抽出関数 - Notionクリッパーのアルゴリズムに近い実装
def extract_title(soup, url):
    # 優先順位に従ってタイトルを抽出
    
    # 1. Open Graph title
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        return og_title.get('content')
    
    # 2. Twitter Card title
    twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
    if twitter_title and twitter_title.get('content'):
        return twitter_title.get('content')
    
    # 3. HTML title tag
    if soup.title and soup.title.string:
        return soup.title.string
    
    # 4. 最初のh1タグ
    h1 = soup.find('h1')
    if h1 and h1.text:
        return h1.text
    
    # 5. 特定のクラス/IDを持つ要素 (一般的なパターン)
    title_candidates = [
        soup.find('div', class_=re.compile(r'title', re.I)),
        soup.find('div', id=re.compile(r'title', re.I)),
        soup.find('h2', class_=re.compile(r'title', re.I)),
        soup.find('h2')
    ]
    
    for candidate in title_candidates:
        if candidate and candidate.text and len(candidate.text.strip()) > 3:
            return candidate.text
    
    # 6. Schema.org構造化データからのタイトル取得
    try:
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and 'headline' in data:
                    return data['headline']
                elif isinstance(data, dict) and 'name' in data:
                    return data['name']
            except:
                continue
    except:
        pass
    
    # URLからドメイン名を抽出
    domain = urlparse(url).netloc
    return f"Saved from {domain}"

# 説明文抽出関数
def extract_description(soup):
    # 1. Open Graph description
    og_desc = soup.find('meta', property='og:description')
    if og_desc and og_desc.get('content'):
        return og_desc.get('content')
    
    # 2. Twitter Card description
    twitter_desc = soup.find('meta', attrs={'name': 'twitter:description'})
    if twitter_desc and twitter_desc.get('content'):
        return twitter_desc.get('content')
    
    # 3. Meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        return meta_desc.get('content')
    
    # 4. 最初の段落
    p = soup.find('p')
    if p and p.text and len(p.text.strip()) > 10:
        return p.text.strip()[:200] + ("..." if len(p.text) > 200 else "")
    
    return "No description available"

# サムネイル画像抽出関数
def extract_thumbnail(soup, url):
    # 1. Open Graph image
    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        return og_image.get('content')
    
    # 2. Twitter Card image
    twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
    if twitter_image and twitter_image.get('content'):
        return twitter_image.get('content')
    
    # 3. 最初の大きな画像
    for img in soup.find_all('img', width=True, height=True):
        try:
            width = int(img.get('width'))
            height = int(img.get('height'))
            if width >= 100 and height >= 100:
                # 相対URLを絶対URLに変換
                src = img.get('src', '')
                if src and not src.startswith(('http://', 'https://')):
                    src = urljoin(url, src)
                return src
        except:
            continue
    
    # 4. srcsetを持つ画像
    for img in soup.find_all('img', srcset=True):
        srcset = img.get('srcset', '')
        # 最も高解像度の画像を取得
        srcs = [s.strip().split(' ')[0] for s in srcset.split(',')]
        if srcs:
            # 相対URLを絶対URLに変換
            src = srcs[-1]
            if src and not src.startswith(('http://', 'https://')):
                src = urljoin(url, src)
            return src
    
    # 5. 最初の画像
    img = soup.find('img', src=True)
    if img:
        src = img.get('src', '')
        if src and not src.startswith(('http://', 'https://')):
            src = urljoin(url, src)
        return src
    
    return ""

# iwaraサイト向けの特別ハンドラ
def handle_iwara_site(url, session, page_info):
    try:
        # iwaraサイト向けのカスタムヘッダー
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Referer': 'https://www.iwara.tv/'
        })
        
        # ページコンテンツを取得
        response = session.get(url, timeout=15)
        
        # HTMLを解析
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # iwaraの動画ページは特定のクラスや構造を持つ
        # タイトル取得の試みをいくつか行う
        
        # 方法1: video-titleクラスを持つ要素
        video_title_elem = soup.find(class_='video-title')
        if video_title_elem and video_title_elem.text.strip():
            page_info['title'] = video_title_elem.text.strip()
            return page_info
        
        # 方法2: h1要素
        h1_elem = soup.find('h1')
        if h1_elem and h1_elem.text.strip():
            page_info['title'] = h1_elem.text.strip()
            return page_info
        
        # 方法3: head内のタイトル要素
        title_elem = soup.find('title')
        if title_elem and title_elem.text:
            # "| Iwara"などのサフィックスを削除
            title_text = title_elem.text.strip()
            page_info['title'] = re.sub(r'\s*\|\s*Iwara.*$', '', title_text)
            return page_info
        
        # 方法4: メタデータからの抽出
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            page_info['title'] = og_title.get('content').strip()
            return page_info
        
        # サムネイル取得
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            page_info['thumbnail'] = og_image.get('content')
        else:
            # ビデオサムネイルの特定のパターンを探す
            video_thumbnail = soup.find('img', class_='video-thumbnail')
            if video_thumbnail and video_thumbnail.get('src'):
                img_src = video_thumbnail.get('src')
                if not img_src.startswith(('http://', 'https://')):
                    img_src = urljoin(url, img_src)
                page_info['thumbnail'] = img_src
        
        return page_info
    
    except Exception as e:
        st.error(f"iwara情報の取得中にエラーが発生しました: {str(e)}")
        return page_info

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
    for percent_complete in range(0, 101, 10):
        time.sleep(0.05)  # シミュレーションのための遅延
        progress_bar.progress(percent_complete)
    
    # ウェブページ情報を抽出（クリッパーのような動作）
    page_info = fetch_page_info_like_clipper(url)
    st.session_state['page_info'] = page_info
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
    """, unsafe_allow_html=True)
    
    # サムネイル
    if page_info['thumbnail']:
        st.markdown("</div>", unsafe_allow_html=True)  # 一度カードを閉じる
        st.markdown('<div class="thumbnail-container">', unsafe_allow_html=True)
        st.image(page_info['thumbnail'], use_column_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="info-card" style="margin-top: 0; border-top-left-radius: 0; border-top-right-radius: 0;">', unsafe_allow_html=True)
    
    # 説明
    if page_info['description']:
        st.markdown(f"""
        <p style="margin-top: 1rem; color: #4B5563; line-height: 1.5;">{page_info['description']}</p>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)  # カードを閉じる
    
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
        st.markdown(f"""
        <div class="success-message">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
            <span>Notionに保存しました！</span>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state['notion_url']:
            st.markdown(f"""
            <a href="{st.session_state['notion_url']}" target="_blank" style="display: inline-block; background-color: #E5E7EB; color: #374151; text-decoration: none; padding: 0.5rem 1rem; border-radius: 6px; margin-top: 0.5rem; margin-bottom: 1rem; font-weight: 500; transition: all 0.2s;">
                <span style="display: flex; align-items: center;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 0.5rem;">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                        <polyline points="15 3 21 3 21 9"></polyline>
                        <line x1="10" y1="14" x2="21" y2="3"></line>
                    </svg>
                    Notionで開く
                </span>
            </a>
            """, unsafe_allow_html=True)
    
    # エラー時の表示
    if st.session_state['error']:
        st.markdown(f"""
        <div class="error-message">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 0.5rem;">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span>保存中にエラーが発生しました: {st.session_state['error']}</span>
        </div>
        """, unsafe_allow_html=True)

# フッター
st.markdown("""
<footer>
    <p>© 2025 Notion Bookmarker - すべてのコンテンツをNotionに保存</p>
</footer>
""", unsafe_allow_html=True)