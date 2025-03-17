import streamlit as st
import requests
from bs4 import BeautifulSoup
from notion_client import Client
from urllib.parse import urlparse
from datetime import datetime

# アプリのタイトルとスタイル設定
st.set_page_config(
    page_title="Notionブックマーカー",
    page_icon="📚",
    layout="centered"
)

st.title("Notionブックマーカー")
st.markdown("URLを入力すると、ページ情報をNotionデータベースに保存します。")

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

# サイドバーまたはタブで設定項目を表示（モバイル対応）
if st.session_state.get('view_mode') != 'settings':
    if st.button("⚙️ 設定を開く", key="open_settings"):
        st.session_state['view_mode'] = 'settings'
        st.rerun()

    # メイン画面コンテンツ
    if 'notion_token' not in st.session_state or 'database_id' not in st.session_state:
        st.session_state['notion_token'] = ""
        st.session_state['database_id'] = ""

    # 設定が空の場合は警告
    if not st.session_state['notion_token'] or not st.session_state['database_id']:
        st.warning("⚠️ APIトークンとデータベースIDを設定してください")

    def extract_webpage_info(url):
        """URLからウェブページの情報を抽出する関数"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # ドメイン名を取得 (エラー時のフォールバック用)
        domain = urlparse(url).netloc
        
        # 基本情報をセット (エラー時のフォールバック用)
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
                
                # ステータスコードが200以外の場合
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

    def add_to_notion(page_info, notion_token, database_id):
        """抽出したページ情報をNotionデータベースに追加する関数"""
        try:
            # Notionクライアントを初期化
            notion = Client(auth=notion_token)
            
            # データベースのプロパティを取得して確認
            db = notion.databases.retrieve(database_id=database_id)
            
            # 指定の順序でプロパティを整理する
            properties = {}
            
            # 1. 名前（タイトル）
            if '名前' in db['properties']:
                properties['名前'] = {
                    'title': [
                        {
                            'text': {
                                'content': page_info['title']
                            }
                        }
                    ]
                }
            
            # 2. URL
            if 'URL' in db['properties']:
                properties['URL'] = {
                    'url': page_info['url']
                }
            
            # 3. タグ（空）
            if 'タグ' in db['properties']:
                properties['タグ'] = {
                    'multi_select': []
                }
            
            # 4. 作成日時
            if '作成日時' in db['properties']:
                properties['作成日時'] = {
                    'date': {
                        'start': datetime.now().isoformat()
                    }
                }
            
            # Notion API呼び出し用のパラメータを作成
            params = {
                'parent': {'database_id': database_id},
                'properties': properties
            }
            
            # Notionページを作成
            with st.spinner('Notionに保存中...'):
                new_page = notion.pages.create(**params)
                
                # サムネイル画像がある場合は、子ブロックとして追加
                if page_info['thumbnail']:
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
                
                return True, new_page['url']
        
        except Exception as e:
            return False, str(e)

    # メイン部分: URLの入力フォーム
    url = st.text_input("ウェブページのURLを入力してください", placeholder="https://example.com")

    # 検索ボタンが押されたとき
    if st.button("情報を取得", key="fetch_button"):
        if url:
            # ウェブページ情報を抽出
            page_info = extract_webpage_info(url)
            
            if page_info:
                # セッションに情報を保存
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
                
                # 保存ボタン
                if st.button("Notionに保存する", key="save_button"):
                    success, result = add_to_notion(
                        page_info,
                        st.session_state['notion_token'],
                        st.session_state['database_id']
                    )
                    
                    if success:
                        st.success("✅ Notionに保存しました！")
                        st.markdown(f"[Notionで開く]({result})")
                    else:
                        st.error(f"❌ 保存中にエラーが発生しました: {result}")
            else:
                st.error("ページ情報の取得に失敗しました。")
        else:
            st.warning("URLを入力してください。")

else:
    # 設定画面
    st.header("設定")
    
    # 戻るボタン
    if st.button("← メイン画面に戻る"):
        st.session_state['view_mode'] = 'main'
        st.rerun()
    
    # Notion APIトークンとデータベースIDの入力
    notion_token = st.text_input(
        "Notion APIトークン", 
        value=st.session_state.get('notion_token', ""),
        type="password",
        help="Notionの統合ページで取得したAPIトークンを入力してください"
    )
    
    database_id = st.text_input(
        "データベースID", 
        value=st.session_state.get('database_id', ""),
        help="NotionデータベースのURLからIDを抽出して入力してください"
    )
    
    # 設定を保存
    if st.button("設定を保存"):
        st.session_state['notion_token'] = notion_token
        st.session_state['database_id'] = database_id
        st.session_state['view_mode'] = 'main'
        st.success("設定を保存しました！")
        st.rerun()

# フッター
st.markdown("---")
st.markdown("Notionブックマーカー © 2025")