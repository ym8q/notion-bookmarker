import streamlit as st
import requests
from bs4 import BeautifulSoup
from notion_client import Client
from urllib.parse import urlparse
from datetime import datetime
import time

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
    
    /* ダークモード対応 */
    @media (prefers-color-scheme: dark) {
        .info-card {
            background-color: #1E1E1E;
            border-left: 4px solid #4361EE;
        }
        
        .domain-badge {
            background-color: #2E2E2E;
            color: #D1D5DB;
        }
    }
    
    /* プログレスバーのスタイル */
    .stProgress > div > div > div > div {
        background-color: #4361EE;
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

# メイン画面表示 - ヘッダー部分
st.markdown("<h1>Notion Bookmarker</h1>", unsafe_allow_html=True)
st.markdown("""
<div style="margin-bottom: 2rem;">
    <p style="font-size: 1.1rem; color: #4B5563; margin-bottom: 1.5rem;">
        ウェブページの情報を簡単にNotionデータベースに保存します。
    </p>
</div>
""", unsafe_allow_html=True)

# URLからウェブページの情報を抽出する関数
def extract_webpage_info(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
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
    
    # ドメイン名を取得
    domain = urlparse(url).netloc
    
    # 基本情報をセット
    page_info = {
        'title': f"Saved from {domain}",
        'url': url,
        'description': "No description available",
        'thumbnail': "",
        'domain': domain
    }
    
    try:
        # ウェブページのコンテンツを取得
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        # エラーチェック
        if response.status_code != 200:
            return page_info
        
        # BeautifulSoupでHTMLを解析
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # タイトルを取得
        if soup.title and soup.title.string:
            page_info['title'] = soup.title.string.strip()
        
        # メタ説明を取得
        meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        if meta_desc:
            page_info['description'] = meta_desc.get('content', '')
        
        # サムネイル画像を取得 (Open Graph画像を優先)
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image:
            page_info['thumbnail'] = og_image.get('content', '')
        
        return page_info
            
    except Exception:
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
    
    # ウェブページ情報を抽出
    page_info = extract_webpage_info(url)
    st.session_state['page_info'] = page_info
    st.session_state['loading'] = False
    
    # プログレスバーを完了状態にして少し待ってから消す
    progress_bar.progress(100)
    time.sleep(0.5)
    progress_bar.empty()
    
    # ページをリロードして、下のコンテンツを表示
    st.experimental_rerun()

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
        st.experimental_rerun()
    
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

# モバイルで本アプリをホーム画面に追加するよう促すティップス
if st.session_state.get('first_run', True):
    st.session_state['first_run'] = False
    
    # モバイルデバイスのみに表示
    st.markdown("""
    <script>
    if (/iPhone|iPad|iPod|Android/i.test(navigator.userAgent)) {
        document.write(`
            <div style="background-color: #FEF3C7; color: #92400E; padding: 1rem; border-radius: 8px; margin: 1rem 0; display: flex; align-items: center;">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 0.75rem;">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <span>このアプリをホーム画面に追加すると、いつでも簡単にアクセスできます。</span>
            </div>
        `);
    }
    </script>
    """, unsafe_allow_html=True)

# フッター
st.markdown("""
<footer>
    <p>© 2025 Notion Bookmarker - すべてのコンテンツをNotionに保存</p>
</footer>
""", unsafe_allow_html=True)