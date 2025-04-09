from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ButtonsTemplate, MessageAction, FlexSendMessage
)
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import tempfile
import sys
import logging
import re
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
line_handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
user_states = {}

def get_gspread_client():
    credentials_content = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_CONTENT")
    if not credentials_content:
        logger.error("缺少 GOOGLE_APPLICATION_CREDENTIALS_CONTENT 環境變數")
        raise ValueError("環境變數未設定")
    try:
        with tempfile.NamedTemporaryFile(mode="w+", delete=True, suffix=".json") as temp_file:
            temp_file.write(credentials_content)
            temp_file.flush()
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = ServiceAccountCredentials.from_json_keyfile_name(temp_file.name, scope)
            client = gspread.authorize(creds)
            return client
    except Exception as e:
        logger.error(f"Google Sheets 授權錯誤：{e}", exc_info=True)
        sys.exit(1)
@app.route("/")
def home():
    return "LINE Bot 正常運作中！"

@app.route("/webhook", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@line_handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_msg = event.message.text.strip()
    logger.info(f"使用者 {user_id} 傳送訊息：{user_msg}")
    # 會員專區選單
    if user_msg == "會員專區":
        template = TemplateSendMessage(
            alt_text="會員功能選單",
            template=ButtonsTemplate(
                title="會員專區",
                text="請選擇功能",
                actions=[
                    MessageAction(label="查詢會員資料", text="查詢會員資料"),
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, template)

    elif user_msg == "查詢會員資料":
        user_states[user_id] = "awaiting_member_id"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請輸入您的會員編號：")
        )

    elif user_states.get(user_id) == "awaiting_member_id":
        member_id = re.sub(r"\D", "", user_msg)
        user_states.pop(user_id)

        try:
            client = get_gspread_client()
            sheet = client.open_by_key("1jVhpPNfB6UrRaYZjCjyDR4GZApjYLL4KZXQ1Si63Zyg").worksheet("會員資料")
            records = sheet.get_all_records()

            member_data = next(
                (row for row in records if re.sub(r"\D", "", str(row["會員編號"])) == member_id),
                None
            )

            if member_data:
                reply_text = (
                    f"✅ 查詢成功\n"
                    f"👤 姓名：{member_data['姓名']}\n"
                    f"📱 電話：{member_data['電話']}\n"
                    f"🧾 會員類型：{member_data['會員類型']}\n"
                    f"📌 狀態：{member_data['會員狀態']}\n"
                    f"🎯 點數：{member_data['會員點數']}\n"
                    f"⏳ 到期日：{member_data['會員到期日']}"
                )
            else:
                reply_text = "❌ 查無此會員編號，請確認後再試一次。"

        except Exception as e:
            reply_text = f"❌ 查詢失敗：{str(e)}"
            logger.error(f"查詢會員資料失敗：{e}", exc_info=True)

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
    if user_msg == "常見問題":
        faq_categories = ["準備運動", "會員方案", "個人教練方案", "團體課程", "其他"]
        buttons = [
            MessageAction(label=cat, text=cat)
            for cat in faq_categories
        ]
        template = TemplateSendMessage(
            alt_text="常見問題分類",
            template=ButtonsTemplate(
                title="常見問題",
                text="請選擇分類",
                actions=buttons[:4]  # ButtonsTemplate 最多只能放 4 個按鈕
            )
        )
        line_bot_api.reply_message(event.reply_token, template)

    elif user_msg in ["準備運動", "會員方案", "個人教練課程", "團體課程", "其他", "其他"]:
        try:
            client = get_gspread_client()
            sheet = client.open_by_key("1jVhpPNfB6UrRaYZjCjyDR4GZApjYLL4KZXQ1Si63Zyg").worksheet("常見問題")
            records = sheet.get_all_records()
            matched = [row for row in records if row["分類"] == user_msg]

            if not matched:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="找不到相關問題。"))
                return

            bubbles = []
            for item in matched:
                bubble = {
                    "type": "bubble",
                    "size": "mega",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"❓ {item['問題']}",
                                "wrap": True,
                                "weight": "bold",
                                "size": "md",
                                "color": "#333333"
                            },
                            {
                                "type": "text",
                                "text": f"💡 {item['答覆']}",
                                "wrap": True,
                                "size": "sm",
                                "color": "#666666"
                            }
                        ]
                    }
                }
                bubbles.append(bubble)

            flex_message = FlexSendMessage(
                alt_text=f"{user_msg} 的常見問題",
                contents={
                    "type": "carousel",
                    "contents": bubbles[:10]  # 最多 10 筆
                }
            )
            line_bot_api.reply_message(event.reply_token, flex_message)

        except Exception as e:
            logger.error(f"常見問題查詢錯誤：{e}", exc_info=True)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠ 查詢失敗，請稍後再試。"))
if __name__ == "__main__":
    app.run()
