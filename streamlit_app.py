import streamlit as st
import requests
from bs4 import BeautifulSoup
from notion_client import Client
from urllib.parse import urlparse
from datetime import datetime

# 固定の認証情報 (APIトークンとデータベースID)
NOTION_API_TOKEN = "ntn_i2957150244j9hSJCmlhWx1tkxlBP2MNliQk9Z3AkBHgcK"  # あなたの実際のAPIトークンに置き換えてください
DATABASE_ID = "1b90b0428824814fa0d9db921aa812d0"  # あなたの実際のデータベースIDに置き換えてください

# アプリのタイトルとスタイル設定
st.set_page_config(
    page_title="Notionブックマーカー",
    page_icon="📚",
    layout="centered"
)

# モバイル向けのスタイル調整
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    @media (max-width: 768px) {
        .stButton button {
            width: 100%;
            margin-bottom: 0.5rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化 (ページ情報のみ保持)
if 'page_info' not in st.session_state:
    st.session_state['page_info'] = None

# メイン画面表示
st.title("Notionブックマーカー")
st.markdown("URLを入力すると、ページ情報をNotionデータベースに保存します。")

# URLからウェブページの情報を抽出する関数
def extract_webpage_info(url):
    # ヘッダー設定
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
        # 進捗状況インジケータを表示
        with st.spinner('ページ情報を取得中...'):
            # ウェブページのコンテンツを取得
            response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            
            # エラーチェック
            if response.status_code != 200:
                st.warning(f"HTTPステータスコード {response.status_code} が返されました。基本情報のみ使用します。")
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
            
    except requests.exceptions.RequestException as e:
        st.error(f"リクエストエラーが発生しました: {e}")
        return page_info
    except Exception as e:
        st.error(f"その他のエラーが発生しました: {e}")
        return page_info

# Notionに情報を追加する関数
def add_to_notion(page_info):
    try:
        # Notionクライアントを初期化
        notion = Client(auth=NOTION_API_TOKEN)
        
        with st.spinner('Notionデータベースに接続中...'):
            # まず、データベースが存在するか確認
            try:
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
                    st.error("タイトル用のプロパティが見つかりません")
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
                with st.spinner('Notionにページを作成中...'):
                    new_page = notion.pages.create(
                        parent={'database_id': DATABASE_ID},
                        properties=properties
                    )
                    
                    # サムネイル画像がある場合は、子ブロックとして追加
                    if page_info['thumbnail']:
                        with st.spinner('サムネイル画像を追加中...'):
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
                            except Exception as img_error:
                                st.warning(f"サムネイル画像の追加中にエラーが発生しました: {img_error}")
                    
                    return True, new_page['url']
            
            except Exception as e:
                error_msg = str(e)
                if "Could not find database" in error_msg:
                    return False, f"データベースIDが無効です: {DATABASE_ID}"
                return False, f"データベースの取得中にエラーが発生しました: {error_msg}"
        
    except Exception as e:
        error_msg = str(e)
        if "API token is invalid" in error_msg:
            return False, "APIトークンが無効です。"
        return False, f"Notionへの接続中にエラーが発生しました: {error_msg}"

# メイン部分: URLの入力フォーム (簡素化されたUI)
url = st.text_input("ウェブページのURLを入力してください", placeholder="https://example.com")

# 検索ボタンが押されたとき
if st.button("情報を取得", key="fetch_button"):
    if url:
        # ウェブページ情報を抽出
        page_info = extract_webpage_info(url)
        st.session_state['page_info'] = page_info
        
        # 抽出した情報を表示
        st.subheader("取得した情報")
        
        # タイトル
        st.markdown(f"**タイトル**: {page_info['title']}")
        
        # URL
        st.markdown(f"**URL**: [{page_info['url']}]({page_info['url']})")
        
        # ドメイン
        st.markdown(f"**ドメイン**: {page_info['domain']}")
        
        # サムネイル
        if page_info['thumbnail']:
            st.image(page_info['thumbnail'], caption="サムネイル", width=250)
        
        # 説明
        if page_info['description']:
            st.markdown("**説明**:")
            st.text_area("", value=page_info['description'], height=100, disabled=True, label_visibility="collapsed")
        
        # Notionに保存するボタン
        if st.button("Notionに保存する", key="save_button"):
            success, result = add_to_notion(page_info)
            
            if success:
                st.success("✅ Notionに保存しました！")
                st.markdown(f"[Notionで開く]({result})")
            else:
                st.error(f"❌ 保存に失敗しました: {result}")
    else:
        st.warning("URLを入力してください。")

# 以前に取得した情報がある場合に表示
elif 'page_info' in st.session_state and st.session_state['page_info']:
    page_info = st.session_state['page_info']
    
    st.subheader("取得した情報")
    st.markdown(f"**タイトル**: {page_info['title']}")
    st.markdown(f"**URL**: [{page_info['url']}]({page_info['url']})")
    
    if page_info['thumbnail']:
        st.image(page_info['thumbnail'], caption="サムネイル", width=250)
    
    if st.button("Notionに保存する", key="save_button_cached"):
        success, result = add_to_notion(page_info)
        
        if success:
            st.success("✅ Notionに保存しました！")
            st.markdown(f"[Notionで開く]({result})")
        else:
            st.error(f"❌ 保存に失敗しました: {result}")

# フッター
st.markdown("---")
st.markdown("Notionブックマーカー © 2025")