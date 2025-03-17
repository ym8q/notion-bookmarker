import streamlit as st
import requests
from bs4 import BeautifulSoup
from notion_client import Client
from urllib.parse import urlparse, urljoin
from datetime import datetime
import time
import re
import json
import base64
from io import BytesIO

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

# カスタムCSSを適用（省略）
st.markdown("""<style>/* スタイル省略 */</style>""", unsafe_allow_html=True)

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

# メイン画面表示 - ヘッダー部分
st.markdown("<h1>Notion Bookmarker</h1>", unsafe_allow_html=True)

# 複数のユーザーエージェントを設定
USER_AGENTS = [
    # モバイルエージェント (iOS)
    'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
    # デスクトップエージェント (Chrome)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
    # デスクトップエージェント (Firefox)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0',
    # モバイルエージェント (Android)
    'Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.104 Mobile Safari/537.36'
]

# 生のHTMLを表示する関数
def display_raw_html(html):
    """HTML内容を分析し、重要な部分を表示する"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 重要な部分を抽出
    head_content = soup.head.prettify() if soup.head else "見つかりません"
    
    # タイトル関連の要素
    title_tag = soup.title.prettify() if soup.title else "見つかりません"
    og_tags = [str(tag) for tag in soup.find_all('meta', property=re.compile(r'^og:'))]
    twitter_tags = [str(tag) for tag in soup.find_all('meta', attrs={'name': re.compile(r'^twitter:')})]
    
    # h1タグ
    h1_tags = [str(tag) for tag in soup.find_all('h1')]
    
    # 特定のクラスを持つ要素 (iwaraサイト向け)
    title_classes = []
    for cls in ['video-title', 'title', 'heading', 'header-title']:
        elements = soup.find_all(class_=re.compile(cls, re.I))
        for el in elements:
            title_classes.append(f"Class '{cls}': {str(el)}")
    
    # 表示用のMarkdown
    st.markdown("### HTMLの重要部分")
    
    with st.expander("titleタグ", expanded=False):
        st.code(title_tag, language="html")
        
    with st.expander("OGPメタタグ", expanded=False):
        if og_tags:
            for tag in og_tags:
                st.code(tag, language="html")
        else:
            st.write("OGPメタタグは見つかりませんでした")
            
    with st.expander("Twitterカードメタタグ", expanded=False):
        if twitter_tags:
            for tag in twitter_tags:
                st.code(tag, language="html")
        else:
            st.write("Twitterカードメタタグは見つかりませんでした")
    
    with st.expander("h1タグ", expanded=False):
        if h1_tags:
            for tag in h1_tags:
                st.code(tag, language="html")
        else:
            st.write("h1タグは見つかりませんでした")
    
    with st.expander("タイトル関連のクラス", expanded=False):
        if title_classes:
            for cls in title_classes:
                st.code(cls, language="html")
        else:
            st.write("タイトル関連のクラスは見つかりませんでした")

# メタデータリクエスト高度化版
def get_metadata_advanced(url):
    """高度な方法でWebページからメタデータを取得"""
    
    # 初期化
    page_info = {
        'title': None,
        'description': None,
        'thumbnail': None,
        'url': url,
        'domain': urlparse(url).netloc
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
                'Pragma': 'no-cache',
                'Referer': 'https://www.google.com/',
                'Upgrade-Insecure-Requests': '1',
                'Connection': 'keep-alive',
                'dnt': '1'
            }
            
            # urlがiwara.tvの場合、特別な処理
            if 'iwara' in url:
                headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                headers['Accept-Language'] = 'ja,en-US;q=0.7,en;q=0.3'
                headers['Referer'] = 'https://www.iwara.tv/'
            
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
            
            # HTML解析
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
            
            # 5. 特定のサイト向けカスタム処理
            if 'iwara' in url:
                # video-titleクラスを探す
                video_title = soup.find(class_='video-title')
                if video_title and video_title.text.strip():
                    title_candidates.append(('iwara_video_title', video_title.text.strip()))
                
                # nodeのタイトルを探す
                node_title = soup.find(class_='node-title')
                if node_title and node_title.text.strip():
                    title_candidates.append(('iwara_node_title', node_title.text.strip()))
                
                # h4タグを探す (iwaraの一部ページで使用)
                h4_title = soup.find('h4')
                if h4_title and h4_title.text.strip():
                    title_candidates.append(('iwara_h4', h4_title.text.strip()))
            
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
            
            # 3. 特定のサイト向けカスタム処理
            if 'iwara' in url:
                # ビデオサムネイル
                video_thumb = soup.find('img', class_='video-thumbnail')
                if video_thumb and video_thumb.get('src'):
                    image_url = video_thumb.get('src').strip()
                    if not image_url.startswith(('http://', 'https://')):
                        image_url = urljoin(url, image_url)
                    image_candidates.append(('iwara_video_thumbnail', image_url))
            
            # 最良の画像を選択
            if image_candidates:
                page_info['thumbnail'] = image_candidates[0][1]
        
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
    
    # ウェブページ情報を抽出（改良版）
    page_info, raw_html, debug_info = get_metadata_advanced(url)
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
    
    # サムネイル - 非推奨のuse_column_widthをuse_container_widthに変更
    if page_info['thumbnail']:
        st.image(page_info['thumbnail'], caption="サムネイル", use_container_width=True)
    
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