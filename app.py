import re
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

# 분야 이름과 YES24 분야 번호 매핑
CATEGORIES = {
    "국내도서 종합": "001",
    "소설/시/희곡": "001001046",
    "에세이": "001001047",
    "자기계발": "001001026",
    "경제 경영": "001001025",
    "인문": "001001019",
    "IT 모바일": "001001003",
}


def extract_number(text):
    """문자열에서 숫자만 뽑아 정수로 반환하는 함수"""
    # 정규표현식으로 숫자(0~9)가 아닌 문자를 모두 제거
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else 0


def fetch_html(category_code):
    """YES24 베스트셀러 페이지의 HTML을 가져오는 함수"""
    url = f"https://www.yes24.com/Product/Category/BestSeller?categoryNumber={category_code}&pageNumber=1&pageSize=24"
    # 브라우저에서 접속하는 것처럼 보이게 하는 헤더 설정
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        # 10초 제한 시간을 두고 웹페이지 요청
        response = requests.get(url, headers=headers, timeout=10)
        # 200 OK가 아니면 HTTP 에러 발생
        response.raise_for_status()
        return response.text

    except requests.exceptions.Timeout:
        st.error("요청 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.")
    except requests.exceptions.ConnectionError:
        st.error("네트워크 연결에 실패했습니다. 인터넷 상태를 확인해주세요.")
    except requests.exceptions.HTTPError as e:
        st.error(f"웹페이지 접속 중 HTTP 오류가 발생했습니다. (상태 코드: {e.response.status_code})")
    except requests.exceptions.RequestException as e:
        st.error(f"데이터를 가져오는 중 알 수 없는 오류가 발생했습니다: {e}")

    return None


def parse_books(html):
    """HTML에서 책 정보를 추출해 리스트로 반환하는 함수"""
    soup = BeautifulSoup(html, "html.parser")
    # id가 yesBestList인 요소 안의 모든 li 태그(책 목록) 찾기
    book_items = soup.select("#yesBestList > li")

    # 광고나 빈 li 태그가 섞여 있을 수 있으므로 실제 책 제목이 있는 항목만 필터링
    books = []
    rank = 1

    for item in book_items:
        title_tag = item.select_one("a.gd_name")
        # 제목 태그가 없으면 책 항목이 아니므로 건너뜀
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)

        # 저자 추출 (태그가 없을 경우를 대비한 처리)
        author_tag = item.select_one("span.info_auth")
        author = author_tag.get_text(strip=True) if author_tag else "정보 없음"

        # 출판사 추출
        pub_tag = item.select_one("span.info_pub")
        publisher = pub_tag.get_text(strip=True) if pub_tag else "정보 없음"

        # 판매가 추출 후 정수 변환
        price_tag = item.select_one("div.info_price em.yes_b")
        price = extract_number(price_tag.get_text()) if price_tag else 0

        # 판매지수 추출 후 정수 변환
        sale_tag = item.select_one("span.saleNum")
        sales_index = extract_number(sale_tag.get_text()) if sale_tag else 0

        books.append({
            "순위": rank,
            "제목": title,
            "저자": author,
            "출판사": publisher,
            "판매가": price,
            "판매지수": sales_index,
        })
        rank += 1

    return books


def display_results(df, category_name):
    """수집한 데이터를 표, 차트, 다운로드 버튼으로 화면에 출력하는 함수"""
    st.subheader(f"{category_name} 베스트셀러 목록 (총 {len(df)}권)")
    # 인덱스를 숨기고 표 형태로 출력
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("판매지수 상위 10권 차트")
    # 판매지수 기준 내림차순 정렬 후 상위 10개 추출
    top10_df = df.sort_values(by="판매지수", ascending=False).head(10)
    # 가로 막대 차트 출력 (x축: 제목, y축: 판매지수)
    st.bar_chart(top10_df, x="제목", y="판매지수", horizontal=True)

    # 한글 깨짐 방지를 위해 utf-8-sig 인코딩으로 CSV 변환
    csv_data = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="CSV 파일 다운로드",
        data=csv_data,
        file_name=f"yes24_bestseller_{category_name}.csv",
        mime="text/csv",
    )


def main():
    """전체 앱의 화면 구성과 실행 흐름을 제어하는 메인 함수"""
    st.title("YES24 분야별 베스트셀러 수집기")

    # 1. 분야 선택 selectbox
    selected_category = st.selectbox("조회할 분야를 선택하세요", list(CATEGORIES.keys()))

    # 2. 데이터 수집 실행 버튼
    if st.button("베스트셀러 가져오기"):
        category_code = CATEGORIES[selected_category]

        with st.spinner("데이터를 수집하고 있습니다..."):
            # 웹페이지 HTML 가져오기
            html = fetch_html(category_code)

            if html:
                # HTML에서 책 데이터 추출
                book_list = parse_books(html)

                # 책을 하나도 찾지 못한 경우 에러 처리
                if not book_list:
                    st.warning("책 정보를 하나도 찾지 못했습니다. 페이지 구조가 변경되었거나 데이터가 없습니다.")
                else:
                    # 데이터프레임으로 변환 후 화면에 출력
                    df = pd.DataFrame(book_list)
                    display_results(df, selected_category)


if __name__ == "__main__":
    main()