import os
import sys
import glob
import pandas as pd
import gspread
from datetime import datetime # datetime 임포트
from oauth2client.service_account import ServiceAccountCredentials
import config # 설정 파일 import


def find_and_load_latest_excel():
    """
    './send_number' 폴더에서 가장 최신 엑셀 파일을 찾아 데이터를 정제한 후 DataFrame으로 반환합니다.
    """
    try:
        # 1. 스크립트가 있는 디렉토리를 기준으로 'send_number' 폴더 경로 설정
        script_dir = os.path.dirname(os.path.abspath(__file__))
        download_dir = os.path.join(script_dir, "send_number") # 폴더 이름 확인
        
        if not os.path.isdir(download_dir):
            print(f"오류: '{download_dir}' 폴더를 찾을 수 없습니다.")
            return None

        # 2. 폴더 내 모든 엑셀 파일 목록 가져오기
        excel_files = glob.glob(os.path.join(download_dir, '*.xls*'))

        if not excel_files:
            print(f"오류: '{download_dir}' 폴더에 엑셀 파일(*.xls, *.xlsx)이 없습니다.")
            return None

        # 3. 가장 최신 파일 찾기 (수정 시간을 기준으로)
        latest_file = max(excel_files, key=os.path.getmtime)
        print(f"가장 최신 엑셀 파일을 찾았습니다: {os.path.basename(latest_file)}")

        # 4. '번호'가 포함된 행을 찾아 헤더로 지정하여 파일 불러오기
        print(f"'{os.path.basename(latest_file)}' 파일을 분석하여 헤더 위치를 찾습니다...")
        temp_df = pd.read_excel(latest_file, header=None)
        header_row_index = 0  # 기본값은 첫 번째 행

        for index, row in temp_df.iterrows():
            if row.astype(str).str.contains('번호').any():
                header_row_index = index
                print(f"'번호'가 포함된 행({header_row_index + 1}번째 행)을 헤더로 지정합니다.")
                break
        else:
            print("경고: '번호' 컬럼을 찾지 못했습니다. 첫 번째 행을 헤더로 사용합니다.")

        df = pd.read_excel(latest_file, header=header_row_index)
        print(f"파일을 성공적으로 불러왔습니다. (총 {len(df)}건)")

        # 5. 컬럼명 정리
        df.columns = df.columns.str.strip()
        print(f"\n[확인] 엑셀 파일의 실제 컬럼명 목록입니다:\n{df.columns.tolist()}\n")

        # 6. '수하인명'과 '주소'가 동일한 중복 데이터 제거
        required_excel_cols = ['수하인명', '주소', '운송장번호', '접수일자']
        if not all(col in df.columns for col in required_excel_cols):
            print(f"경고: 엑셀 파일에 필요한 컬럼({', '.join(required_excel_cols)}) 중 일부가 없습니다. 현재 컬럼: {df.columns.tolist()}")
            return None
        
        # 7. '수하인명'과 '주소'가 동일한 중복 데이터 제거
        initial_rows = len(df)
        df.drop_duplicates(subset=['수하인명', '주소'], keep='first', inplace=True)
        removed_count = initial_rows - len(df)
        if removed_count > 0:
            print(f"'수하인명'과 '주소'가 동일한 중복 데이터 {removed_count}건을 제거했습니다.")
        else:
            print("중복된 데이터가 없습니다.")
        
        return df

    except Exception as e:
        print(f"파일 처리 중 오류가 발생했습니다: {e}")
        return None

def authenticate_google_sheets():
    """Google Sheets API 인증을 수행하고 클라이언트 객체를 반환합니다."""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(config.GOOGLE_SHEET_CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        print("\nGoogle Sheets 인증 성공.")
        return client
    except Exception as e:
        print(f"오류: Google Sheets 인증 실패: {e}")
        return None

def upload_to_google_sheet(client, df):
    """DataFrame의 운송장 번호를 Google Sheet에 업데이트합니다."""
    if df is None or df.empty:
        print("업로드할 데이터가 없습니다.")
        return

    try:
        # 1. config 파일에서 스프레드시트와 워크시트 열기
        spreadsheet = client.open_by_key(config.DB_SPREADSHEET_ID)
        worksheet_name = config.TARGET_SHEET_NAME
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
            print(f"'{worksheet_name}' 워크시트를 찾았습니다.")
        except gspread.WorksheetNotFound:
            print(f"오류: '{worksheet_name}' 워크시트를 찾을 수 없습니다. 스크립트를 종료합니다.")
            return

        # 2. 엑셀의 '수하인명'과 시트의 '받는분'을 비교하여 '운송장번호' 업데이트
        update_google_sheet_with_invoice_numbers(worksheet, df)

    except Exception as e:
        print(f"오류: Google Sheet 업로드 중 오류 발생: {e}")

def update_google_sheet_with_invoice_numbers(worksheet, df):
    """
    엑셀 파일의 '수하인명'과 구글 시트의 '받는분'을 비교하여 '운송장번호'를 업데이트합니다.
    """
    print("Google Sheet 데이터와 엑셀 데이터를 비교하여 송장번호 업데이트를 시작합니다...")

    try:
        # 구글 시트의 전체 데이터를 가져와 DataFrame으로 변환 (더 효율적)
        # get_all_records()는 첫 행을 헤더로 간주합니다.
        sheet_data = worksheet.get_all_records()
        sheet_df = pd.DataFrame(sheet_data)
        
        # 필요한 컬럼 확인
        required_sheet_cols = ['날짜', '받는분', '주소', '송장번호']
        if not all(col in sheet_df.columns for col in required_sheet_cols):
            print(f"오류: 구글 시트에 필요한 컬럼({', '.join(required_sheet_cols)})이 모두 존재하지 않습니다.")
            return

        updates = []
        matched_excel_rows_count = 0 # 일치하는 엑셀 행의 수를 세는 카운터
        for index, row in df.iterrows():
            # 엑셀 데이터에서 필요한 값 추출
            recipient_name = str(row.get('수하인명', '')).strip()
            excel_receipt_date = str(row.get('접수일자', '')).strip() # 엑셀의 접수일자
            excel_address = str(row.get('주소', '')).strip()
            invoice_number = str(row.get('운송장번호', '')).strip()

            # 필수 데이터가 없으면 건너뜁니다.
            if not recipient_name or not excel_receipt_date or not excel_address or not invoice_number:
                print(f"경고: 엑셀 데이터에 필수 정보(수하인명, 접수일자, 주소, 운송장번호)가 누락되어 이 행은 건너뜁니다: {row.to_dict()}")
                continue

            # 엑셀 접수일자를 구글 시트 날짜 형식(YYYY.MM.DD)으로 변환
            # (엑셀에서 날짜가 YYYY-MM-DD 형식이라고 가정)
            # [수정] 엑셀 날짜가 'YYYY-MM-DD' 또는 'YYYY.MM.DD' 등 다양한 형식을 수용하도록 정규화
            # 모든 구분자를 '.'으로 통일합니다.
            import re
            formatted_excel_receipt_date = re.sub(r'[-./]', '.', excel_receipt_date)

            # 구글 시트 DataFrame에서 다음 조건이 모두 일치하는 행 찾기:
            # 1. 구글 시트의 '날짜'가 엑셀의 '접수일자' (YYYY.MM.DD 형식)와 일치
            # 2. 구글 시트의 '받는분'이 엑셀의 '수하인명'과 정확히 일치
            # 3. 구글 시트의 '주소'가 엑셀의 '주소'를 포함
            match_indices = sheet_df.index[
                (sheet_df['날짜'].astype(str).str.strip().str.replace(r'[-./]', '.', regex=True) == formatted_excel_receipt_date) &
                (sheet_df['받는분'].astype(str).str.strip() == recipient_name) &
                (sheet_df['주소'].astype(str).str.strip().str.contains(excel_address, na=False))
            ].tolist()

            if match_indices: # 일치하는 행이 하나라도 있다면
                matched_excel_rows_count += 1 # 일치하는 엑셀 행 카운트 증가
                for i in match_indices:
                    # [수정된 로직] 구글 시트에 이미 송장번호가 있는지 확인
                    existing_invoice = str(sheet_df.loc[i, '송장번호']).strip()
                    row_to_update = i + 2 # gspread는 1-based index, DataFrame은 0-based. 헤더가 있으므로 +2

                    if existing_invoice:
                        print(f"경고: 시트 {row_to_update}행에 이미 송장번호 '{existing_invoice}'가 존재하므로 건너뜁니다.")
                        continue # 다음 매칭 항목으로 넘어감

                    # gspread는 1-based index, DataFrame은 0-based. 헤더가 있으므로 +2
                    # '송장번호' 컬럼의 위치(1-based) 찾기
                    col_to_update = sheet_df.columns.get_loc('송장번호') + 1
                    
                    # 업데이트할 셀 정보 추가
                    updates.append(gspread.Cell(row_to_update, col_to_update, invoice_number))
                    print(f"'{recipient_name}'의 송장 번호를 '{invoice_number}'(으)로 업데이트 예정입니다. (시트의 {row_to_update}행)")

        if updates:
            worksheet.update_cells(updates)
            print(f"\n총 {matched_excel_rows_count}개의 엑셀 행에서 일치하는 데이터를 찾아 {len(updates)}건의 송장번호 업데이트를 완료했습니다.")
        else:
            print("\n업데이트할 송장번호가 없습니다.")

    except Exception as e:
        print(f"오류: 구글 시트 업데이트 중 오류 발생: {e}")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    dataframe = find_and_load_latest_excel()
    if dataframe is not None:
        print("\n[확인] 정제된 데이터 (상위 5개 행):")
        print(dataframe.head())
        gsheet_client = authenticate_google_sheets()
        if gsheet_client:
            upload_to_google_sheet(gsheet_client, dataframe)
