from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, CarouselColumn,
                            CarouselTemplate, MessageAction, URIAction, ImageCarouselColumn, ImageCarouselTemplate,
                            ImageSendMessage, ButtonsTemplate, ConfirmTemplate)
import os
import requests
from bs4 import BeautifulSoup
import random

# 新增: Google Sheets 所需模組
import gspread
from oauth2client.service_account import ServiceAccountCredentials

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
line_handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

app = Flask(__name__)

# 記錄會員資料查詢狀態
user_states = {}

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
    user_msg = event.message.text

    if user_msg == '會員':
        buttons_template = TemplateSendMessage(
            alt_text='會員福利選單',
            template=ButtonsTemplate(
                title='會員專區',
                text='請選擇功能',
                actions=[
                    MessageAction(
                        label='查詢會員資料',
                        text='查詢會員資料')
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)

    elif user_msg == '查詢會員資料':
        user_states[user_id] = 'awaiting_member_id'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='請輸入您的會員編號：'))

    elif user_states.get(user_id) == 'awaiting_member_id':
        member_id = user_msg.strip()
        user_states.pop(user_id)

        # 連接 Google Sheets
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name('161622333688-cvlb8ishheag0as3apjbv3u1icuc1kj8.apps.googleusercontent.com', scope)
            client = gspread.authorize(creds)
            sheet = client.open("享受健身俱樂部試算表").worksheet("會員資料")
            records = sheet.get_all_records()

            member_data = next((row for row in records if str(row['會員ID']) == member_id), None)
            if member_data:
                reply_text = f"姓名：{member_data['姓名']}\n會員類型：{member_data['會員類型']}\n會員點數：{member_data['會員點數']}\n會員到期日：{member_data['會員到期日']}"
            else:
                reply_text = '查無此會員編號，請確認後再試一次。'

        except Exception as e:
            reply_text = f"查詢失敗：{str(e)}"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

    # 原有功能保留
    elif user_msg == 'confirm':
        confirm_template = TemplateSendMessage(
            alt_text = 'confirm template',
            template = ConfirmTemplate(
                text = 'drink coffee?',
                actions = [
                    MessageAction(
                        label = 'yes',
                        text = 'yes'),
                    MessageAction(
                        label = 'no',
                        text = 'no')]
                )
            )
        line_bot_api.reply_message(event.reply_token, confirm_template)

    elif user_msg == '咖啡讚':
        buttons_template = TemplateSendMessage(
            alt_text = 'buttons template',
            template = ButtonsTemplate(
                thumbnail_image_url='https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg',
                title = 'Brown Cafe',
                text = 'Enjoy your coffee',
                actions = [
                    MessageAction(
                        label = '咖啡有什麼好處?',
                        text = '讓人有精神!!!'),
                    URIAction(
                        label = '伯朗咖啡',
                        uri = 'https://www.mrbrown.com.tw/')]
                )
            )
        line_bot_api.reply_message(event.reply_token, buttons_template)

    elif user_msg == '咖啡2個':
        carousel_template = TemplateSendMessage(
            alt_text = 'carousel template',
            template = CarouselTemplate(
                columns = [
                    CarouselColumn(
                        thumbnail_image_url = 'https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg',
                        title = 'this is menu1',
                        text = 'menu1',
                        actions = [
                            MessageAction(
                                label = '咖啡有什麼好處',
                                text = '讓人有精神'),
                            URIAction(
                                label = '伯朗咖啡',
                                uri = 'https://www.mrbrown.com.tw/')]),
                    CarouselColumn(
                        thumbnail_image_url = 'https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg',
                        title = 'this is menu2',
                        text = 'menu2',
                        actions = [
                            MessageAction(
                                label = '咖啡有什麼好處',
                                text = '讓人有精神'),
                            URIAction(
                                label = '伯朗咖啡',
                                uri = 'https://www.mrbrown.com.tw/')])
                ])
            )
        line_bot_api.reply_message(event.reply_token, carousel_template)

    elif user_msg == '照片':
        image_carousel_template = TemplateSendMessage(
            alt_text = 'image carousel template',
            template = ImageCarouselTemplate(
                columns = [
                    ImageCarouselColumn(
                        image_url = 'https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg',
                        action = URIAction(
                            label = '伯朗咖啡',
                            uri = 'https://www.mrbrown.com.tw/')),
                    ImageCarouselColumn(
                        image_url = 'https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg',
                        action = URIAction(
                            label = '伯朗咖啡',
                            uri = 'https://www.mrbrown.com.tw/'))                       
                ])
            )
        line_bot_api.reply_message(event.reply_token, image_carousel_template)

if __name__ == "__main__":
    app.run()
