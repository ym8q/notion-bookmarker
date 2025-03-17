import streamlit as st
import requests
from bs4 import BeautifulSoup
from notion_client import Client
from urllib.parse import urlparse
from datetime import datetime
import re
import base64
from io import BytesIO
from PIL import Image

# OpenAIのAPIを使用するためのライブラリ
# pip install openai
import openai

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

# セッション状態の初期化
if 'notion_token' not in st.session_state:
    st.session_state['notion_token'] = ""
if 'database_id' not in st.session_state:
    st.session_state['database_id'] = ""
if 'openai_api_key' not in st.session_state:
    st.session_state['openai_api_key'] = ""
if 'page_info' not in st.session_state:
    st.session_state['page_info'] = None

# メイン画面表示
st.title("Notionブックマーカー")
st.markdown("URLを入力すると、ページ情報をNotionデータベースに保存します。")

# サイドバーに設定項目を表示
with st.sidebar:
    st.header("設定")
    
    # タブ作成
    tab1, tab2 = st.tabs(["基本設定", "AI設定"])
    
    with tab1:
        # Notion APIトークンとデータベースIDの入力
        notion_token = st.text_input(
            "Notion APIトークン", 
            value=st.session_state['notion_token'],
            type="password",
            help="Notionの統合ページで取得したAPIトークン"
        )
        
        database_id = st.text_input(
            "データベースID", 
            value=st.session_state['database_id'],
            help="NotionデータベースのURLからIDを抽出したもの"
        )
    
    with tab2:
        # OpenAI APIキーの入力
        openai_api_key = st.text_input(
            "OpenAI APIキー", 
            value=st.session_state['openai_api_key'],
            type="password",
            help="OpenAIのAPIキー（自動タグ付けに使用）"
        )
        
        # AI設定オプション
        st.subheader("自動タグ付け設定")
        auto_tagging = st.checkbox("自動タグ付けを有効にする", value=True)
        
        # 追加設定
        if auto_tagging:
            tag_confidence = st.slider("タグ付け確信度しきい値", 0.0, 1.0, 0.7)
    
    # 設定を保存
    if st.button("設定を保存", key="save_settings"):
        st.session_state['notion_token'] = notion_token
        st.session_state['database_id'] = database_id
        st.session_state['openai_api_key'] = openai_api_key
        st.success("設定を保存しました！")

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
        'domain': domain,
        'tags': []  # タグ情報を格納する配列
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

# 画像を分析してタグを生成する関数
def analyze_image_for_tags(image_url):
    if not st.session_state['openai_api_key'] or not image_url:
        return []
    
    try:
        # 画像を取得
        response = requests.get(image_url)
        if response.status_code != 200:
            return []
        
        # OpenAIのクライアントを初期化
        client = openai.OpenAI(api_key=st.session_state['openai_api_key'])
        
        # 画像をエンコード
        image_data = BytesIO(response.content)
        
        # 画像が大きすぎる場合はリサイズ
        try:
            img = Image.open(image_data)
            img.thumbnail((1024, 1024))  # OpenAIのAPIの制限に合わせる
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            encoded_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Exception as img_error:
            st.warning(f"画像処理エラー: {img_error}")
            return []
        
        # OpenAIのVision APIを使用して画像分析
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "system",
                    "content": "あなたは画像を分析して、コンテンツの種類を判別するアシスタントです。画像を見て、3次元（実写）、アニメーション、イラスト、漫画など、適切なカテゴリータグを付けてください。1-3個のタグを提案してください。タグはカンマ区切りのリストとして返してください。"
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "この画像を分析して、適切なタグをカンマ区切りで提供してください。例: '実写,人物,風景' や 'アニメ,キャラクター'"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=100
        )
        
        # レスポンスからタグを抽出
        if response.choices and response.choices[0].message.content:
            tags_text = response.choices[0].message.content.strip()
            # カンマで区切られたタグをリストに変換
            tags = [tag.strip() for tag in tags_text.split(',')]
            return tags
        return []
    
    except Exception as e:
        st.error(f"画像分析中にエラーが発生しました: {str(e)}")
        return []

# テキストからタグを生成する関数
def analyze_text_for_tags(title, description, domain):
    if not st.session_state['openai_api_key']:
        return []
    
    try:
        # OpenAIのクライアントを初期化
        client = openai.OpenAI(api_key=st.session_state['openai_api_key'])
        
        # コンテキスト情報を作成
        context = f"タイトル: {title}\n説明: {description}\nドメイン: {domain}"
        
        # OpenAIのAPIを使用してテキスト分析
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "あなたはウェブページの内容を分析して、コンテンツの種類を判別するアシスタントです。タイトル、説明、ドメインなどの情報から、コンテンツの種類（実写、アニメ、漫画、イラストなど）を推測し、適切なタグを提案してください。1-5個のタグを提案してください。"
                },
                {
                    "role": "user",
                    "content": f"以下の情報からコンテンツの種類を分析し、適切なタグをカンマ区切りで提供してください:\n\n{context}"
                }
            ],
            max_tokens=100
        )
        
        # レスポンスからタグを抽出
        if response.choices and response.choices[0].message.content:
            tags_text = response.choices[0].message.content.strip()
            # カンマで区切られたタグをリストに変換
            tags = [tag.strip() for tag in tags_text.split(',')]
            return tags
        return []
    
    except Exception as e:
        st.error(f"テキスト分析中にエラーが発生しました: {str(e)}")
        return []

# 自動タグ付け処理をまとめた関数
def generate_automatic_tags(page_info):
    tags = []
    
    if not st.session_state['openai_api_key']:
        st.warning("自動タグ付けを行うにはOpenAI APIキーを設定してください")
        return tags
    
    with st.spinner('AIによるコンテンツ分析中...'):
        # サムネイル画像からタグを生成
        if page_info['thumbnail']:
            image_tags = analyze_image_for_tags(page_info['thumbnail'])
            if image_tags:
                st.info(f"画像分析によるタグ: {', '.join(image_tags)}")
                tags.extend(image_tags)
        
        # テキスト情報からタグを生成
        text_tags = analyze_text_for_tags(
            page_info['title'], 
            page_info['description'], 
            page_info['domain']
        )
        if text_tags:
            st.info(f"テキスト分析によるタグ: {', '.join(text_tags)}")
            tags.extend(text_tags)
        
        # 重複を削除
        tags = list(set(tags))
    
    return tags

# Notionに情報を追加する関数
def add_to_notion(page_info, notion_token, database_id):
    try:
        # Notionクライアントを初期化
        notion = Client(auth=notion_token)
        
        with st.spinner('Notionデータベースに接続中...'):
            # まず、データベースが存在するか確認
            try:
                db = notion.databases.retrieve(database_id=database_id)
                st.success("データベースに接続できました!")
                
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
                
                # タグフィールド - AIで生成したタグを使用
                if 'タグ' in db['properties'] and db['properties']['タグ']['type'] == 'multi_select':
                    tag_objects = []
                    for tag in page_info.get('tags', []):
                        # タグが50文字を超える場合は切り詰める（Notionの制限）
                        if len(tag) > 50:
                            tag = tag[:47] + "..."
                        tag_objects.append({'name': tag})
                    
                    properties['タグ'] = {'multi_select': tag_objects}
                
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
                        parent={'database_id': database_id},
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
                    return False, f"データベースIDが無効です: {database_id}"
                return False, f"データベースの取得中にエラーが発生しました: {error_msg}"
        
    except Exception as e:
        error_msg = str(e)
        if "API token is invalid" in error_msg:
            return False, "APIトークンが無効です。設定を確認してください。"
        return False, f"Notionへの接続中にエラーが発生しました: {error_msg}"

# メイン部分: URLの入力フォーム
url = st.text_input("ウェブページのURLを入力してください", placeholder="https://example.com")

# 検索ボタンが押されたとき
if st.button("情報を取得", key="fetch_button"):
    if url:
        # ウェブページ情報を抽出
        page_info = extract_webpage_info(url)
        
        # 自動タグ付けが有効な場合
        auto_tagging = st.session_state.get('openai_api_key') != ""
        if auto_tagging:
            # AIを使用してタグを生成
            tags = generate_automatic_tags(page_info)
            page_info['tags'] = tags
        
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
        
        # AIで生成したタグ
        if 'tags' in page_info and page_info['tags']:
            st.markdown("**自動生成タグ**:")
            tags_html = ""
            for tag in page_info['tags']:
                tags_html += f'<span style="background-color: #f0f0f0; padding: 3px 8px; margin: 2px; border-radius: 10px;">{tag}</span> '
            st.markdown(tags_html, unsafe_allow_html=True)
            
            # タグの編集
            edited_tags = st.text_input("タグを編集（カンマ区切り）:", ", ".join(page_info['tags']))
            if edited_tags != ", ".join(page_info['tags']):
                page_info['tags'] = [tag.strip() for tag in edited_tags.split(",") if tag.strip()]
                st.session_state['page_info'] = page_info
        
        # サムネイル
        if page_info['thumbnail']:
            st.image(page_info['thumbnail'], caption="サムネイル", width=250)
        
        # 説明
        if page_info['description']:
            st.markdown("**説明**:")
            st.text_area("", value=page_info['description'], height=100, disabled=True, label_visibility="collapsed")
        
        # Notionに保存するボタン
        if st.button("Notionに保存する", key="save_button"):
            if not st.session_state['notion_token'] or not st.session_state['database_id']:
                st.error("⚠️ APIトークンとデータベースIDを設定してください")
                st.sidebar.error("⚠️ 左のサイドバーで設定を入力してください")
            else:
                success, result = add_to_notion(
                    page_info,
                    st.session_state['notion_token'],
                    st.session_state['database_id']
                )
                
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
    
    # AIで生成したタグ
    if 'tags' in page_info and page_info['tags']:
        st.markdown("**自動生成タグ**:")
        tags_html = ""
        for tag in page_info['tags']:
            tags_html += f'<span style="background-color: #f0f0f0; padding: 3px 8px; margin: 2px; border-radius: 10px;">{tag}</span> '
        st.markdown(tags_html, unsafe_allow_html=True)
        
        # タグの編集
        edited_tags = st.text_input("タグを編集（カンマ区切り）:", ", ".join(page_info['tags']))
        if edited_tags != ", ".join(page_info['tags']):
            page_info['tags'] = [tag.strip() for tag in edited_tags.split(",") if tag.strip()]
            st.session_state['page_info'] = page_info
    
    if page_info['thumbnail']:
        st.image(page_info['thumbnail'], caption="サムネイル", width=250)
    
    if st.button("Notionに保存する", key="save_button_cached"):
        if not st.session_state['notion_token'] or not st.session_state['database_id']:
            st.error("⚠️ APIトークンとデータベースIDを設定してください")
            st.sidebar.error("⚠️ 左のサイドバーで設定を入力してください")
        else:
            success, result = add_to_notion(
                page_info,
                st.session_state['notion_token'],
                st.session_state['database_id']
            )
            
            if success:
                st.success("✅ Notionに保存しました！")
                st.markdown(f"[Notionで開く]({result})")
            else:
                st.error(f"❌ 保存に失敗しました: {result}")

# フッター
st.markdown("---")
st.markdown("Notionブックマーカー © 2025")