from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ButtonsTemplate, MessageAction, FlexSendMessage, ConfirmTemplate, ImageCarouselTemplate, ImageCarouselColumn
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
                    MessageAction(label="健身紀錄", text="健身紀錄"),
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, template)

    elif user_msg == "查詢會員資料":
        user_states[user_id] = "awaiting_member_info"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🆔 請輸入您的會員編號：\n\n⚠️\n忘記會員編號⚠️\n請輸入名字與電話號碼\n（例如：熊享瘦0912345678）")
        )
    
    elif user_states.get(user_id) == "awaiting_member_info":
        user_states.pop(user_id)
        keyword = user_msg.strip()
    
        try:
            import re
            client = get_gspread_client()
            sheet = client.open_by_key("1jVhpPNfB6UrRaYZjCjyDR4GZApjYLL4KZXQ1Si63Zyg").worksheet("會員資料")
            records = sheet.get_all_records()
    
            member_data = None
    
            # 1️⃣ 判斷是否為會員編號（如 A00001）
            if re.match(r"^[A-Z]\d{5}$", keyword.upper()):
                member_data = next(
                    (row for row in records if str(row["會員編號"]).strip().upper() == keyword.upper()),
                    None
                )
            else:
                # 2️⃣ 嘗試拆解姓名 + 電話（如 王小明0912345678）
                match = re.search(r"(.+?)(09\d{8})", keyword)
                if match:
                    name, phone = match.groups()
                    phone_no_zero = phone[1:]  # 移除開頭 0：0912345678 -> 912345678
                
                    # Debug log 可加上這行：
                    # print(f"查詢姓名: {name}，電話: {phone_no_zero}")
                
                    member_data = next(
                        (row for row in records
                         if row.get("姓名", "").replace(" ", "") == name
                         and str(row.get("電話", "")).strip() == phone_no_zero),
                        None
                    )
                else:
                    raise ValueError("\n輸入格式錯誤！\n請輸入正確的會員編號或姓名+手機號碼（例如：熊享瘦0912345678）")
    
            if member_data:
                reply_text = (
                    f"✅ 查詢成功\n\n"
                    f"👤 姓名：{member_data['姓名']}\n\n"
                    f"📱 電話：0{member_data['電話']}\n\n"
                    f"🧾 會員類型：{member_data['會員類型']}\n\n"
                    f"📌 狀態：{member_data['會員狀態']}\n\n"
                    f"🎯 點數：{member_data['會員點數']}\n\n"
                    f"⏳ 到期日：{member_data['會員到期日']}"
                )
            else:
                reply_text = "❌ 查無此會員資料，請確認姓名與電話或會員編號是否正確。"
    
        except Exception as e:
            reply_text = f"❌ 查詢失敗{str(e)}"
            logger.error(f"會員查詢錯誤：{e}", exc_info=True)
    
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

    elif user_msg == "健身紀錄":
        liff_url = "https://liff.line.me/2007341042-bzeprj3R"  # 這是新專案上線的網址
        flex_message = FlexSendMessage(
            alt_text="健身紀錄",
            contents={
                "type": "carousel",
                "contents": [
                    {
                        "type": "bubble",
                        "hero": {
                            "type": "image",
                            "url": "https://i.imgur.com/sevvXcU.jpeg",  # 替換為場地圖片
                            "size": "full",
                            "aspectRatio": "20:13",
                            "aspectMode": "cover"
                        },
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "📚 健身紀錄日誌",
                                    "weight": "bold",
                                    "size": "xl"
                                },
                                {
                                    "type": "text",
                                    "text": "紀錄你的健身事項",
                                    "size": "sm",
                                    "wrap": True,
                                    "color": "#666666"
                                }
                            ]
                        },
                        "footer": {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "uri",
                                        "label": "開始記錄今日健身！",
                                        "uri": liff_url
                                    },
                                    "style": "primary"
                                },
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "message",
                                        "label": "查詢健身紀錄",
                                        "text": "查詢健身紀錄"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        )
        line_bot_api.reply_message(event.reply_token, flex_message)

    elif user_msg == "查詢健身紀錄":
        user_states[user_id] = "awaiting_fitness_name"  # 新增狀態
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請輸入名字與電話號碼以查詢健身紀錄（例如：熊享瘦0912345678)")
        )

    elif user_states.get(user_id) == "awaiting_fitness_name":
        user_states.pop(user_id)  # 清除狀態
        name_phone_input = user_msg.strip()
    
        try:
            import re
            match = re.search(r"(.+?)(09\d{8})", name_phone_input)
            if not match:
                raise ValueError("\n輸入格式錯誤！\n請輸入正確的姓名+手機號碼（例如：熊享瘦0912345678）")
    
            user_name, user_phone = match.groups()
            phone_no_zero = user_phone[1:]  # 去除開頭 0：0912345678 -> 912345678
    
            client = get_gspread_client()
            sheet = client.open_by_key("1jVhpPNfB6UrRaYZjCjyDR4GZApjYLL4KZXQ1Si63Zyg").worksheet("會員健身紀錄")
            records = sheet.get_all_records()
    
            matched_records = [
                record for record in records
                if record.get("紀錄姓名", "").replace(" ", "") == user_name
                and str(record.get("紀錄電話", "")).strip() == phone_no_zero
            ]
    
            if matched_records:
                reply_text = "📋 查詢到以下健身紀錄：\n"
                for record in matched_records:
                    reply_text += (
                        f"📅 日期：{record.get('日期', '無資料')}\n"
                        f"🏋️ 運動項目：{record.get('運動項目', '無資料')}\n"
                        f"⏱️ 時長：{record.get('時長', '無資料')} 分鐘\n"
                        f"📝 備註：{record.get('備註', '無資料')}\n"
                        f"---\n"
                    )
            else:
                reply_text = "❌ 查無此姓名與電話號碼的健身紀錄，請確認輸入是否正確。"
    
        except Exception as e:
            reply_text = f"❌ 查詢失敗：{str(e)}"
    
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            
    elif user_msg == "常見問題":
        faq_categories = ["準備運動", "會員方案", "課程", "其他"]
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

    elif user_msg in ["課程"]:
        confirm_template = TemplateSendMessage(
            alt_text = 'confirm template',
            template = ConfirmTemplate(
                title="常見問題課程分類",
                text="請選擇分類",
                actions = [
                    MessageAction(
                        label = '個人教練',
                        text = '個人教練課程'),
                    MessageAction(
                        label = '團體',
                        text = '團體課程')]
                )
            )
        line_bot_api.reply_message(event.reply_token, confirm_template)

    elif user_msg in ["準備運動", "會員方案", "個人教練課程", "團體課程", "其他"]:
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
            
    elif user_msg == "更多功能":
        flex_message = FlexSendMessage(
            alt_text="更多功能選單",
            contents={
                "type": "carousel",
                "contents": [
                    {
                        "type": "bubble",
                        "hero": {
                            "type": "image",
                            "url": "https://i.imgur.com/d3v7RxR.png",  # 替換為場地圖片
                            "size": "full",
                            "aspectRatio": "20:13",
                            "aspectMode": "cover"
                        },
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "🏟️ 場地介紹",
                                    "weight": "bold",
                                    "size": "xl"
                                },
                                {
                                    "type": "text",
                                    "text": "探索我們的健身空間",
                                    "size": "sm",
                                    "wrap": True,
                                    "color": "#666666"
                                }
                            ]
                        },
                        "footer": {
                            "type": "box",
                            "layout": "horizontal",
                            "spacing": "sm",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "message",
                                        "label": "健身/重訓",
                                        "text": "健身/重訓"
                                    },
                                    "style": "primary"
                                },
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "message",
                                        "label": "上課教室",
                                        "text": "上課教室"
                                    }
                                }
                            ]
                        }
                    },
                    {
                        "type": "bubble",
                        "hero": {
                            "type": "image",
                            "url": "https://i.imgur.com/HrtfSdH.png",  # 替換為課程圖片
                            "size": "full",
                            "aspectRatio": "20:13",
                            "aspectMode": "cover"
                        },
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "📚 課程介紹",
                                    "weight": "bold",
                                    "size": "xl"
                                },
                                {
                                    "type": "text",
                                    "text": "了解我們提供的課程類型",
                                    "size": "sm",
                                    "wrap": True,
                                    "color": "#666666"
                                }
                            ]
                        },
                        "footer": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "message",
                                        "label": "查看課程內容",
                                        "text": "課程內容"
                                    },
                                    "style": "primary"
                                }
                            ]
                        }
                    },
                    {
                        "type": "bubble",
                        "hero": {
                            "type": "image",
                            "url": "https://i.imgur.com/izThqNv.png",  # 替換為團隊圖片
                            "size": "full",
                            "aspectRatio": "20:13",
                            "aspectMode": "cover"
                        },
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "👥 團隊介紹",
                                    "weight": "bold",
                                    "size": "xl"
                                },
                                {
                                    "type": "text",
                                    "text": "認識我們的教練與團隊",
                                    "size": "sm",
                                    "wrap": True,
                                    "color": "#666666"
                                }
                            ]
                        },
                        "footer": {
                            "type": "box",
                            "layout": "horizontal",
                            "spacing": "sm",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "message",
                                        "label": "健身教練",
                                        "text": "健身教練"
                                    },
                                    "style": "primary"
                                },
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "message",
                                        "label": "課程教練",
                                        "text": "課程教練"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        )
        line_bot_api.reply_message(event.reply_token, flex_message)
        
    elif user_msg == "健身/重訓":
        # 顯示分類選單（按鈕）
        subcategories = ["心肺訓練", "背部訓練", "腿部訓練", "自由重量器材"]
        buttons = [
            MessageAction(label=sub, text=sub)
            for sub in subcategories[:4]  # 先顯示前4個
        ]
        # 第二個 bubble 可加更多分類
        template = TemplateSendMessage(
            alt_text="健身/重訓 器材分類",
            template=ButtonsTemplate(
                title="健身/重訓 器材分類",
                text="請選擇器材分類",
                actions=buttons
            )
        )
        line_bot_api.reply_message(event.reply_token, template)
        
    elif user_msg in ["心肺訓練", "背部訓練", "腿部訓練", "自由重量器材"]:
        try:
            client = get_gspread_client()
            sheet = client.open_by_key("1jVhpPNfB6UrRaYZjCjyDR4GZApjYLL4KZXQ1Si63Zyg").worksheet("場地資料")
            records = sheet.get_all_records()

            matched = [
                row for row in records
                if row.get("分類", "").strip() == user_msg and row.get("圖片1", "").startswith("https")
            ]

            if not matched:
                line_bot_api.reply_message(
                    event.reply_token, TextSendMessage(text=f"⚠ 查無『{user_msg}』分類的器材圖片")
                )
                return

            # 每 10 筆一組發送
            for i in range(0, len(matched), 10):
                chunk = matched[i:i + 10]
                image_columns = [
                    ImageCarouselColumn(
                        image_url=row["圖片1"],
                        action=MessageAction(label=row.get("名稱", "查看詳情"), text=row.get("名稱", "查看詳情"))
                    ) for row in chunk
                ]

                carousel = TemplateSendMessage(
                    alt_text=f"{user_msg} 器材圖片",
                    template=ImageCarouselTemplate(columns=image_columns)
                )
                line_bot_api.reply_message(event.reply_token, carousel)

        except Exception as e:
            logger.error(f"{user_msg} 分類查詢錯誤：{e}", exc_info=True)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠ 發生錯誤，請稍後再試。"))
            
    elif user_msg == "上課教室":
        try:
            client = get_gspread_client()
            sheet = client.open_by_key("1jVhpPNfB6UrRaYZjCjyDR4GZApjYLL4KZXQ1Si63Zyg").worksheet("場地資料")
            records = sheet.get_all_records()

            matched = [
                row for row in records
                if row.get("類型", "").strip() == "上課教室" and row.get("圖片1", "").startswith("https")
            ]

            if not matched:
                line_bot_api.reply_message(
                    event.reply_token, TextSendMessage(text="⚠ 查無『上課教室』的場地資料")
                )
                return

            image_columns = [
                ImageCarouselColumn(
                    image_url=row["圖片1"],
                    action=MessageAction(label=row.get("名稱", "查看詳情"), text=row.get("名稱", "查看詳情"))
                ) for row in matched
            ]

            carousel = TemplateSendMessage(
                alt_text="上課教室場地列表",
                template=ImageCarouselTemplate(columns=image_columns[:10])
            )
            line_bot_api.reply_message(event.reply_token, carousel)

        except Exception as e:
            logger.error(f"上課教室查詢失敗：{e}", exc_info=True)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"⚠ 發生錯誤：{e}"))
        
    elif user_msg == "課程內容":
        try:
            client = get_gspread_client()
            sheet = client.open_by_key("1jVhpPNfB6UrRaYZjCjyDR4GZApjYLL4KZXQ1Si63Zyg").worksheet("課程資料")
            records = sheet.get_all_records()

            # 提取唯一課程類型
            course_types = list({row["課程類型"].strip() for row in records if row.get("課程類型")})
            course_types = [t for t in course_types if t]

            # 建立按鈕
            buttons = [
                {
                    "type": "button",
                    "style": "secondary",
                    "action": {
                        "type": "message",
                        "label": t,
                        "text": t
                    }
                } for t in course_types[:6]
            ]

            bubble = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "📚 課程內容查詢",
                            "weight": "bold",
                            "size": "lg",
                            "margin": "md"
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "margin": "lg",
                            "contents": buttons
                        }
                    ]
                }
            }

            flex_msg = FlexSendMessage(
                alt_text="課程類型查詢",
                contents=bubble
            )

            line_bot_api.reply_message(
                event.reply_token,
                [
                    flex_msg,
                    TextSendMessage(text="📅 你也可以輸入日期（例如：2025-05-01）查詢當天開課課程。")
                ]
            )

        except Exception as e:
            logger.error(f"課程內容查詢錯誤：{e}", exc_info=True)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠ 無法讀取課程資料"))

    elif user_msg in ["有氧課程", "瑜珈課程", "游泳課程"]:
        try:
            client = get_gspread_client()
            sheet = client.open_by_key("1jVhpPNfB6UrRaYZjCjyDR4GZApjYLL4KZXQ1Si63Zyg").worksheet("課程資料")
            records = sheet.get_all_records()
    
            matched = [row for row in records if row.get("課程類型", "").strip() == user_msg]
    
            if not matched:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"❌ 查無『{user_msg}』相關課程"))
                return
    
            bubbles = []
            for row in matched[:10]:
                bubble_contents = {
                    "type": "bubble",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": [
                            {"type": "text", "text": row.get("課程名稱", "（未提供課程名稱）"), "weight": "bold", "size": "lg", "wrap": True},
                            {"type": "text", "text": f"👨‍🏫 教練：{row.get('教練姓名', '未知')}", "size": "sm", "wrap": True},
                            {"type": "text", "text": f"📅 開課日期：{row.get('開始日期', '未提供')}", "size": "sm"},
                            {"type": "text", "text": f"🕒 上課時間：{row.get('上課時間', '未提供')}", "size": "sm"},
                            {"type": "text", "text": f"⏱️ 時間：{row.get('時間', '未提供')}", "size": "sm"},
                            {"type": "text", "text": f"💲 價格：{row.get('課程價格', '未定')}", "size": "sm"}
                        ]
                    },
                    "footer": {  # Add the footer for the button
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "button",
                                "style": "primary",
                                "action": {
                                    "type": "message",
                                    "label": "立即預約",
                                    "text": f"我要預約"  # Include course name in the message
                                }
                            }
                        ]
                    }
                }
                bubbles.append(bubble_contents)
    
            line_bot_api.reply_message(
                event.reply_token,
                FlexSendMessage(
                    alt_text=f"{user_msg} 課程內容",
                    contents={"type": "carousel", "contents": bubbles}
                )
            )
    
        except Exception as e:
            logger.error(f"課程類型查詢錯誤：{e}", exc_info=True)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"⚠ 無法查詢課程內容（錯誤：{str(e)}）")
            )

    elif re.match(r"^\d{4}[-/]\d{2}[-/]\d{2}$", user_msg):
        query_date = user_msg.replace("/", "-").strip()
        try:
            client = get_gspread_client()
            sheet = client.open_by_key("1jVhpPNfB6UrRaYZjCjyDR4GZApjYLL4KZXQ1Si63Zyg").worksheet("課程資料")
            records = sheet.get_all_records()

            matched = [row for row in records if row.get("開始日期", "").strip() == query_date]

            if not matched:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 該日期無任何課程"))
                return

            bubbles = []
            for row in matched[:10]:
                bubble_contents = {
                    "type": "bubble",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": [
                            {"type": "text", "text": row.get("課程名稱", "（未提供課程名稱）"), "weight": "bold", "size": "lg", "wrap": True},
                            {"type": "text", "text": f"👨‍🏫 教練：{row.get('教練姓名', '未知')}", "size": "sm", "wrap": True},
                            {"type": "text", "text": f"📅 開課日期：{row.get('開始日期', '未提供')}", "size": "sm"},
                            {"type": "text", "text": f"🕒 上課時間：{row.get('上課時間', '未提供')}", "size": "sm"},
                            {"type": "text", "text": f"⏱️ 時間：{row.get('時間', '未提供')}", "size": "sm"},
                            {"type": "text", "text": f"💲 價格：{row.get('課程價格', '未定')}", "size": "sm"}
                        ]
                    },
                    "footer": {  # Add the footer for the button
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "button",
                                "style": "primary",
                                "action": {
                                    "type": "message",
                                    "label": "立即預約",
                                    "text": f"我要預約"  # Include course name in the message
                                }
                            }
                        ]
                    }
                }
                bubbles.append(bubble_contents)

            line_bot_api.reply_message(
                event.reply_token,
                FlexSendMessage(
                    alt_text=f"{query_date} 的課程",
                    contents={"type": "carousel", "contents": bubbles}
                )
            )

        except Exception as e:
            logger.error(f"課程日期查詢錯誤：{e}", exc_info=True)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"⚠ 無法查詢課程內容（錯誤訊息：{str(e)}）")
            )
            
    elif user_msg == "健身教練":
         try:
             client = get_gspread_client()
             sheet = client.open_by_key("1jVhpPNfB6UrRaYZjCjyDR4GZApjYLL4KZXQ1Si63Zyg").worksheet("教練資料")
             records = sheet.get_all_records()
 
             matched = [
                 row for row in records
                 if row.get("教練類型", "").strip() == "健身教練" and row.get("圖片", "").startswith("https")
             ]
 
             if not matched:
                 line_bot_api.reply_message(
                     event.reply_token, TextSendMessage(text="⚠ 查無『健身教練』的資料")
                 )
                 return
 
             bubbles = []
             for row in matched:
                 bubble = {
                     "type": "bubble",
                     "hero": {
                         "type": "image",
                         "url": row["圖片"],
                         "size": "full",
                         "aspectRatio": "20:13",
                         "aspectMode": "cover"
                     },
                     "body": {
                         "type": "box",
                         "layout": "vertical",
                         "spacing": "sm",
                         "contents": [
                             {
                                 "type": "text",
                                 "text": f"{row['姓名']}（{row['教練類別']}）",
                                 "weight": "bold",
                                 "size": "lg",
                                 "wrap": True
                             },
                             {
                                 "type": "text",
                                 "text": f"專長：{row.get('專長', '未提供')}",
                                 "size": "sm",
                                 "wrap": True,
                                 "color": "#666666"
                             }
                         ]
                     },
                     "footer": {
                         "type": "box",
                         "layout": "vertical",
                         "spacing": "sm",
                         "contents": [
                             {
                                 "type": "button",
                                 "style": "primary",
                                 "action": {
                                     "type": "message",
                                     "label": "立即預約",
                                     "text": f"我要預約"
                                 }
                             }
                         ]
                     }
                 }
                 bubbles.append(bubble)
 
             flex_message = FlexSendMessage(
                 alt_text="健身教練清單",
                 contents={
                     "type": "carousel",
                     "contents": bubbles[:10]
                 }
             )
             line_bot_api.reply_message(event.reply_token, flex_message)
 
         except Exception as e:
             logger.error(f"⚠ 健身教練查詢失敗：{e}", exc_info=True)
             line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"⚠ 發生錯誤：{e}"))

    elif user_msg == "課程教練":
        # 顯示分類選單（按鈕）
        subcategories = ["有氧教練", "瑜珈老師", "游泳教練"]
        buttons = [
            MessageAction(label=sub, text=sub)
            for sub in subcategories[:4]  # 先顯示前4個
        ]
        # 第二個 bubble 可加更多分類
        template = TemplateSendMessage(
            alt_text="課程教練分類",
            template=ButtonsTemplate(
                title="課程教練分類",
                text="請選擇課程教練",
                actions=buttons
            )
        )
        line_bot_api.reply_message(event.reply_token, template)
        
    elif user_msg in ["有氧教練", "瑜珈老師", "游泳教練"]:
         try:
             client = get_gspread_client()
             sheet = client.open_by_key("1jVhpPNfB6UrRaYZjCjyDR4GZApjYLL4KZXQ1Si63Zyg").worksheet("教練資料")
             records = sheet.get_all_records()
 
             matched = [
                 row for row in records
                 if row.get("教練類別", "").strip() == user_msg and row.get("圖片", "").startswith("https")
             ]
 
             if not matched:
                 line_bot_api.reply_message(
                     event.reply_token, TextSendMessage(text="⚠ 查無『{user_msg}』的資料")
                 )
                 return
 
             bubbles = []
             for row in matched:
                 bubble = {
                     "type": "bubble",
                     "hero": {
                         "type": "image",
                         "url": row["圖片"],
                         "size": "full",
                         "aspectRatio": "20:13",
                         "aspectMode": "cover"
                     },
                     "body": {
                         "type": "box",
                         "layout": "vertical",
                         "spacing": "sm",
                         "contents": [
                             {
                                 "type": "text",
                                 "text": f"{row['姓名']}（{row['教練類別']}）",
                                 "weight": "bold",
                                 "size": "lg",
                                 "wrap": True
                             },
                             {
                                 "type": "text",
                                 "text": f"專長：{row.get('專長', '未提供')}",
                                 "size": "sm",
                                 "wrap": True,
                                 "color": "#666666"
                             }
                         ]
                     },
                     "footer": {
                         "type": "box",
                         "layout": "vertical",
                         "spacing": "sm",
                         "contents": [
                             {
                                 "type": "button",
                                 "style": "primary",
                                 "action": {
                                     "type": "message",
                                     "label": "立即預約",
                                     "text": f"我要預約"
                                 }
                             }
                         ]
                     }
                 }
                 bubbles.append(bubble)
 
             flex_message = FlexSendMessage(
                 alt_text="課程教練清單",
                 contents={
                     "type": "carousel",
                     "contents": bubbles[:10]
                 }
             )
             line_bot_api.reply_message(event.reply_token, flex_message)
 
         except Exception as e:
             logger.error(f"課程教練查詢失敗：{e}", exc_info=True)
             line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"⚠ 發生錯誤：{e}"))

    else:
        try:
            client = get_gspread_client()
            sheet = client.open_by_key("1jVhpPNfB6UrRaYZjCjyDR4GZApjYLL4KZXQ1Si63Zyg").worksheet("場地資料")
            records = sheet.get_all_records()

            matched = next((row for row in records if row.get("名稱") == user_msg), None)

            if matched and matched.get("圖片1", "").startswith("https"):
                bubble = {
                    "type": "bubble",
                    "hero": {
                        "type": "image",
                        "url": matched["圖片1"],
                        "size": "full",
                        "aspectRatio": "20:13",
                        "aspectMode": "cover"
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "text",
                                "text": matched["名稱"],
                                "weight": "bold",
                                "size": "xl",
                                "wrap": True
                            },
                            {
                                "type": "text",
                                "text": matched["描述"],
                                "size": "sm",
                                "wrap": True,
                                "color": "#666666"
                            }
                        ]
                    }
                }
            
                # 如果類型為「上課教室」，加上 footer 的立即預約按鈕
                if matched.get("類型") == "上課教室":
                    bubble["footer"] = {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "button",
                                "style": "primary",
                                "action": {
                                    "type": "message",
                                    "label": "立即預約",
                                    "text": "我要預約"
                                }
                            }
                        ]
                    }
            
                flex_msg = FlexSendMessage(
                    alt_text=f"{matched['名稱']} 詳細資訊",
                    contents=bubble
                )
                line_bot_api.reply_message(event.reply_token, flex_msg)

            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage())

        except Exception as e:
            logger.error(f"場地詳情查詢失敗：{e}", exc_info=True)
            pass

if __name__ == "__main__":
    app.run()
