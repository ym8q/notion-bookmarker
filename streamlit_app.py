import streamlit as st
import requests
from bs4 import BeautifulSoup
from notion_client import Client
from urllib.parse import urlparse, urljoin
from datetime import datetime
import time
import re

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
    
    /* ヘルプボックス */
    .help-box {
        background-color: #FEF3C7;
        border-left: 4px solid #F59E0B;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    /* ステップバイステップガイド */
    .step {
        display: flex;
        margin-bottom: 0.5rem;
    }
    
    .step-number {
        background-color: #4361EE;
        color: white;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 0.75rem;
        flex-shrink: 0;
    }
    
    .step-content {
        flex: 1;
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

# メイン画面表示 - ヘッダー部分
st.markdown("<h1>Notion Bookmarker</h1>", unsafe_allow_html=True)
st.markdown("""
<div style="margin-bottom: 2rem;">
    <p style="font-size: 1.1rem; color: #4B5563; margin-bottom: 1.5rem;">
        ウェブページの情報を簡単にNotionデータベースに保存します。
    </p>
</div>
""", unsafe_allow_html=True)

# ベーシックなウェブページ情報抽出関数
def get_basic_page_info(url):
    """
    URLから基本的なページ情報を抽出
    """
    # ドメイン名を取得
    domain = urlparse(url).netloc
    
    # 基本情報をセット
    page_info = {
        'title': None,
        'description': None,
        'thumbnail': None,
        'url': url,
        'domain': domain
    }
    
    try:
        # リクエストヘッダー
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Referer': 'https://www.google.com/'
        }
        
        # リクエスト送信
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # タイトル取得
            if soup.title and soup.title.string:
                title_text = soup.title.string.strip()
                # Just a momentを除外
                if not ('just a moment' in title_text.lower()):
                    page_info['title'] = title_text
            
            # タイトルがない場合、OGPから取得
            if not page_info['title']:
                og_title = soup.find('meta', property='og:title')
                if og_title and og_title.get('content'):
                    page_info['title'] = og_title.get('content').strip()
            
            # 最終的にドメインからタイトルを生成
            if not page_info['title']:
                page_info['title'] = f"Content from {domain}"
            
            # 説明文取得
            meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
            if meta_desc and meta_desc.get('content'):
                page_info['description'] = meta_desc.get('content').strip()
            
            # ページ全体のHTMLを保存
            page_info['html'] = response.text
            
    except Exception as e:
        # エラー時はドメインからタイトル作成
        page_info['title'] = f"Content from {domain}"
        
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
    
    # ウェブページ情報を抽出（シンプル版）
    with st.spinner("ページ情報を取得中..."):
        for percent_complete in range(0, 80, 10):
            time.sleep(0.1)
            progress_bar.progress(percent_complete)
            
        page_info = get_basic_page_info(url)
        
        for percent_complete in range(80, 101, 5):
            time.sleep(0.05)
            progress_bar.progress(percent_complete)
    
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
    </div>
    """, unsafe_allow_html=True)
    
    # タイトル手動編集機能
    st.subheader("タイトルの編集")
    edited_title = st.text_input("タイトルを編集:", value=page_info['title'])
    if edited_title != page_info['title']:
        page_info['title'] = edited_title
        st.session_state['page_info'] = page_info
        st.success("タイトルを更新しました")
    
    # サムネイルの手動入力セクション
    st.subheader("サムネイル画像")
    
    # サムネイル入力のガイド
    st.markdown("""
    <div class="help-box">
        <h4 style="margin-top: 0;">サムネイル画像の取得方法</h4>
        <div class="step">
            <div class="step-number">1</div>
            <div class="step-content">元のウェブページで画像を右クリック → 「画像アドレスをコピー」を選択</div>
        </div>
        <div class="step">
            <div class="step-number">2</div>
            <div class="step-content">または、画像の上で右クリック → 「検証」を選択 → imgタグのsrcやdata-src属性のURLをコピー</div>
        </div>
        <div class="step">
            <div class="step-number">3</div>
            <div class="step-content">コピーしたURLを下の入力欄に貼り付けて「プレビュー」をクリック</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # サムネイルURLの入力フォームと検証ボタン
    col1, col2 = st.columns([3, 1])
    with col1:
        thumbnail_url = st.text_input("サムネイルのURL:", value=page_info.get('thumbnail', ''))
    with col2:
        preview_button = st.button("プレビュー", key="preview_button", use_container_width=True)
    
    # プレビューボタンが押されたとき
    if preview_button and thumbnail_url:
        try:
            st.image(thumbnail_url, caption="サムネイルプレビュー", use_container_width=True)
            page_info['thumbnail'] = thumbnail_url
            st.session_state['page_info'] = page_info
            st.success("サムネイルが更新されました")
        except Exception as e:
            st.error(f"画像の読み込みに失敗しました: {str(e)}")
    
    # 既存のサムネイルがある場合は表示
    elif page_info.get('thumbnail'):
        try:
            st.image(page_info['thumbnail'], caption="サムネイル", use_container_width=True)
        except:
            st.warning("保存されたサムネイルの表示に失敗しました。URLを修正してください。")
    
    # 特定のドメイン向けのヒント
    domain = urlparse(url).netloc
    
    if 'japaneseasmr.com' in domain:
        st.markdown("""
        <div class="help-box">
            <h4>japaneseasmr.com のヒント</h4>
            <p>このサイトでは、記事内の最初の画像がよいサムネイルになります。記事内の画像を右クリックして「画像アドレスをコピー」を選択してください。</p>
        </div>
        """, unsafe_allow_html=True)
    
    elif 'supjav.com' in domain:
        st.markdown("""
        <div class="help-box">
            <h4>supjav.com のヒント</h4>
            <p>このサイトでは、動画のプレビュー画像がサムネイルに適しています。プレビュー画像を右クリックして「画像アドレスをコピー」を選択するか、「検証」からdata-srcやdata-original属性の値をコピーしてください。</p>
        </div>
        """, unsafe_allow_html=True)
    
    # 説明文セクション
    if page_info.get('description'):
        st.subheader("説明")
        st.text_area("説明文:", value=page_info['description'], height=100)
    
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