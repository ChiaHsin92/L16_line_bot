from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, CarouselColumn,
    CarouselTemplate, MessageAction, URIAction, ImageCarouselColumn, ImageCarouselTemplate,
    ImageSendMessage, ButtonsTemplate, ConfirmTemplate
)
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# LineBot API 初始化
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
line_handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

app = Flask(__name__)

# 使用者狀態紀錄（紀錄是否正在輸入會員ID）
user_states = {}

# Google Sheets 認證與連線
def get_gsheet_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("your-credentials.json", scope)
    client = gspread.authorize(creds)
    return client

# 查詢會員資料功能
def query_member_data(member_id):
    client = get_gsheet_client()
    sheet = client.open("享受健身俱樂部試算表").worksheet("會員資料")
    records = sheet.get_all_records()

    for record in records:
        if str(record['會員ID']) == member_id:
            return f"""✅ 會員資料如下：
👤 姓名：{record['姓名']}
🏷️ 會員類型：{record['會員類型']}
🎯 點數：{record['會員點數']}
📅 到期日：{record['會員到期日']}"""
    return "❌ 查無此會員編號，請確認後再輸入。"

@app.route('/')
def home():
    return 'Hello, World!'

@app.route("/webhook", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@line_handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    msg = event.message.text.strip()

    # 會員福利按鈕
    if msg == "會員":
        buttons_template = TemplateSendMessage(
            alt_text='會員福利查詢',
            template=ButtonsTemplate(
                title='會員福利',
                text='享有免費課程、折扣商品、VIP空間等',
                actions=[
                    MessageAction(label='查詢會員資料', text='查詢會員資料')
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return

    # 使用者點擊「查詢會員資料」
    if msg == "查詢會員資料":
        user_states[user_id] = "awaiting_member_id"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入您的會員編號（例如：000321）"))
        return

    # 使用者輸入會員編號
    if user_states.get(user_id) == "awaiting_member_id":
        reply_text = query_member_data(msg)
        user_states[user_id] = None
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # 原本的 confirm 樣板
    if msg == 'confirm':
        confirm_template = TemplateSendMessage(
            alt_text='confirm template',
            template=ConfirmTemplate(
                text='drink coffee?',
                actions=[
                    MessageAction(label='yes', text='yes'),
                    MessageAction(label='no', text='no')
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, confirm_template)
        return

    # 按鈕樣板
    if msg == '咖啡':
        buttons_template = TemplateSendMessage(
            alt_text='buttons template',
            template=ButtonsTemplate(
                thumbnail_image_url='https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg',
                title='Brown Cafe',
                text='Enjoy your coffee',
                actions=[
                    MessageAction(label='咖啡有什麼好處?', text='讓人有精神!!!'),
                    URIAction(label='伯朗咖啡', uri='https://www.mrbrown.com.tw/')
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return

    # Carousel 樣板
    if msg == '咖啡2個':
        carousel_template = TemplateSendMessage(
            alt_text='carousel template',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg',
                        title='this is menu1',
                        text='menu1',
                        actions=[
                            MessageAction(label='咖啡有什麼好處', text='讓人有精神'),
                            URIAction(label='伯朗咖啡', uri='https://www.mrbrown.com.tw/')
                        ]),
                    CarouselColumn(
                        thumbnail_image_url='https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg',
                        title='this is menu2',
                        text='menu2',
                        actions=[
                            MessageAction(label='咖啡有什麼好處', text='讓人有精神'),
                            URIAction(label='伯朗咖啡', uri='https://www.mrbrown.com.tw/')
                        ])
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, carousel_template)
        return

    # Image Carousel 樣板
    if msg == '照片':
        image_carousel_template = TemplateSendMessage(
            alt_text='image carousel template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg',
                        action=URIAction(label='伯朗咖啡', uri='https://www.mrbrown.com.tw/')),
                    ImageCarouselColumn(
                        image_url='https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg',
                        action=URIAction(label='伯朗咖啡', uri='https://www.mrbrown.com.tw/'))
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, image_carousel_template)
        return

if __name__ == "__main__":
    app.run()
