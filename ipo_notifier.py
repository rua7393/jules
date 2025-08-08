import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import warnings
import smtplib
import ssl
import time
import schedule
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# FutureWarning를 무시하도록 설정
warnings.simplefilter(action='ignore', category=FutureWarning)

# ==============================================================================
# 사용자 설정 - 이메일 정보를 입력해주세요.
# ==============================================================================
# 보내는 사람 Gmail 주소 (예: "my_email@gmail.com")
SENDER_EMAIL = "YOUR_GMAIL@gmail.com"

# Gmail 앱 비밀번호 (Gmail 2단계 인증 설정 후 생성 가능)
# 중요: 실제 Gmail 비밀번호가 아닌 '앱 비밀번호'를 사용해야 합니다.
# 생성 방법: Google 계정 관리 -> 보안 -> 2단계 인증 -> 앱 비밀번호
SENDER_PASSWORD = "YOUR_APP_PASSWORD"

# 받는 사람 이메일 주소
RECIPIENT_EMAIL = "rua7393@gmail.com"
# ==============================================================================


def get_ipo_data():
    """
    38커뮤니케이션 웹사이트에서 공모주 데이터를 스크래핑하여 DataFrame으로 반환합니다.
    """
    try:
        url = "http://www.38.co.kr/html/fund/index.htm?o=k"
        response = requests.get(url)
        response.encoding = 'euc-kr'
        soup = BeautifulSoup(response.text, 'html.parser')
        tables = soup.find_all('table', {'summary': '공모주 청약일정'})
        if not tables:
            print("오류: 공모주 일정 테이블을 찾을 수 없습니다.")
            return pd.DataFrame()

        df = pd.read_html(str(tables[0]), header=0)[0]
        df = df.iloc[:, :8]
        df.columns = ['종목명', '공모주일', '확정공모가', '희망공모가', '주간사', '경쟁률', '상장일', '구분']
        df = df[df['종목명'].notna()]
        df = df[~df['종목명'].str.contains('스팩', na=False)]
        df['상장일'] = pd.to_datetime(df['상장일'], errors='coerce')
        return df
    except Exception as e:
        print(f"오류: 데이터 처리 중 문제가 발생했습니다. ({e})")
        return pd.DataFrame()

def get_todays_subscriptions(df):
    """
    공모주 데이터프레임에서 오늘 청약 가능한 종목을 필터링합니다.
    """
    today = datetime.now().date()
    subscription_list = []
    for _, row in df.iterrows():
        date_range_str = row['공모주일']
        if isinstance(date_range_str, str) and '~' in date_range_str:
            try:
                start_date_str, end_date_str = date_range_str.split('~')
                start_year = start_date_str.split('.')[0]
                if '.' not in end_date_str:
                    end_date_str = f"{start_year}.{end_date_str}"
                start_date = datetime.strptime(start_date_str, '%Y.%m.%d').date()
                end_date = datetime.strptime(end_date_str, '%Y.%m.%d').date()
                if start_date <= today <= end_date:
                    subscription_list.append(row)
            except (ValueError, IndexError):
                continue
    return pd.DataFrame(subscription_list)

def get_todays_listings(df):
    """
    공모주 데이터프레임에서 오늘 상장하는 종목을 필터링합니다.
    """
    today_str = datetime.now().strftime('%Y-%m-%d')
    return df[df['상장일'] == today_str]

def format_ipo_data_as_html(subs_df, listings_df):
    """
    DataFrame을 이메일로 보내기 위한 HTML 형식으로 변환합니다.
    """
    today_str = datetime.now().strftime('%Y-%m-%d')
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif; }}
            h1 {{ color: #2c3e50; }}
            h2 {{ color: #34495e; border-bottom: 2px solid #ecf0f1; padding-bottom: 5px; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; box-shadow: 0 2px 3px rgba(0,0,0,0.1); }}
            th, td {{ border: 1px solid #e0e0e0; padding: 12px; text-align: left; }}
            th {{ background-color: #3498db; color: white; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .no-data {{ color: #7f8c8d; font-style: italic; }}
        </style>
    </head>
    <body>
        <h1>📅 {today_str} 오늘의 공모주 정보</h1>
        <h2>🔔 오늘 청약 가능한 공모주</h2>
    """
    if not subs_df.empty:
        subs_display = subs_df[['종목명', '확정공모가', '주간사']].copy()
        subs_display.columns = ['종목명', '공모가(원)', '주간사']
        html += subs_display.to_html(index=False, border=0)
    else:
        html += "<p class='no-data'>오늘 청약 가능한 공모주가 없습니다.</p>"

    html += "<h2>📈 오늘 상장하는 공모주</h2>"
    if not listings_df.empty:
        listings_display = listings_df[['종목명']].copy()
        listings_display.columns = ['종목명']
        html += listings_display.to_html(index=False, border=0)
    else:
        html += "<p class='no-data'>오늘 상장하는 공모주가 없습니다.</p>"

    html += "</body></html>"
    return html

def send_email(html_content):
    """
    내용을 HTML 형식으로 이메일 발송합니다.
    """
    if SENDER_EMAIL == "YOUR_GMAIL@gmail.com" or SENDER_PASSWORD == "YOUR_APP_PASSWORD":
        print("================ 경 고 ================")
        print("이메일 정보가 설정되지 않았습니다.")
        print("스크립트 상단의 SENDER_EMAIL과 SENDER_PASSWORD를")
        print("자신의 정보로 수정한 후 다시 실행해주세요.")
        print("=======================================")
        return

    message = MIMEMultipart()
    message['From'] = SENDER_EMAIL
    message['To'] = RECIPIENT_EMAIL
    message['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 오늘의 공모주 정보"
    message.attach(MIMEText(html_content, 'html'))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, message.as_string())
        print(f"성공: {RECIPIENT_EMAIL}(으)로 이메일을 발송했습니다.")
    except Exception as e:
        print(f"오류: 이메일 발송에 실패했습니다. ({e})")
        print("팁: Gmail 2단계 인증 후 '앱 비밀번호'를 사용하고 있는지 확인하세요.")

def job():
    """
    스케줄러가 실행할 작업
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 작업을 시작합니다: 공모주 정보 스크래핑...")
    ipo_df = get_ipo_data()
    if ipo_df.empty:
        print("데이터를 가져오지 못해 작업을 중단합니다.")
        return

    todays_subs = get_todays_subscriptions(ipo_df)
    todays_listings = get_todays_listings(ipo_df)

    html_body = format_ipo_data_as_html(todays_subs, todays_listings)
    send_email(html_body)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 작업 완료.")

if __name__ == "__main__":
    print("--- 📧 공모주 이메일 알림 프로그램 시작 ---")
    print(f"매일 오전 9:00에 {RECIPIENT_EMAIL}(으)로 알림을 보냅니다.")
    print("프로그램을 종료하려면 Ctrl+C를 누르세요.")

    # 스케줄 설정
    schedule.every().day.at("09:00").do(job)

    # 프로그램 시작 시 테스트를 위해 즉시 1회 실행
    print("\n[최초 실행] 테스트를 위해 작업을 1회 실행합니다...")
    job()

    while True:
        schedule.run_pending()
        time.sleep(60) # 1분마다 다음 작업 시간을 확인합니다.
