import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import os
from pydantic import BaseModel
from pathlib import Path
import pandas as pd
import requests
import time
import pydeck as pdk
if "favorite_places" not in st.session_state:
    st.session_state.favorite_places = []
_ = load_dotenv()

MODEL = "gpt-5.4-mini"
st.set_page_config(
    page_title="AI 여행 도우미",
    page_icon="✈️",
)
OpenAI_API_KEY = os.environ["OPENAI_API_KEY"]
client = OpenAI(api_key=OpenAI_API_KEY)

class Weather(BaseModel):
    temperature: str
    description: str
    travel_forecast: str

class Budget(BaseModel):
    min_budget: int
    max_budget: int

    accommodation_min: int
    accommodation_max: int

    food_min: int
    food_max: int

    transportation_min: int
    transportation_max: int

    etc_min: int
    etc_max: int

class RecommendedArea(BaseModel):
    name: str
    reason: str
    price_range: str
    suitable_for: list[str]

class PlaceRecommendation(BaseModel):
    name: str
    description: str
    tips: list[str]
    rating: float
class ScheduleItem(BaseModel):
    day: str
    theme: str
    morning: str
    afternoon: str
    evening: str

class AirportTransfer(BaseModel):
    route: str
    duration: str
    cost: int
    currency: str
    recommendation: str

class Transportation(BaseModel):
    airport_to_city: AirportTransfer
    public_transport: str
    transit_card: str
    transportation_tips: list[str]

class PackingItem(BaseModel):
    item: str
    reason: str

class BudgetTip(BaseModel):
    category: str
    tip: str

class TravelGuide(BaseModel):
    summary: str
    weather: Weather
    budget: Budget
    recommended_season: str

    recommended_areas: list[RecommendedArea]

    restaurants: list[PlaceRecommendation]
    attractions: list[PlaceRecommendation]
    hidden_spots: list[PlaceRecommendation]
    schedule: list[ScheduleItem]
    transportation: Transportation

    travel_tips: list[str]
    packing_list: list[PackingItem]

    travel_warnings: list[str]

    budget_tips: list[BudgetTip]
TRAVEL_STYLES = [
    "맛집",
    "관광",
    "쇼핑",
    "자연",
    "휴양",
    "문화·역사",
    "액티비티",
    "카페"
]
MONTHS = [
    "1월", "2월", "3월", "4월",
    "5월", "6월", "7월", "8월",
    "9월", "10월", "11월", "12월"
]

def normalize_destination(destination):
    """한국 주요 도시명을 Geocoding에 적합한 이름으로 보정합니다."""

    destination = destination.strip()

    city_mapping = {
        "서울": "서울특별시",
        "부산": "부산광역시",
        "대구": "대구광역시",
        "인천": "인천광역시",
        "광주": "광주광역시",
        "대전": "대전광역시",
        "울산": "울산광역시",
        "세종": "세종특별자치시",
        "제주": "제주특별자치도",
    }

    return city_mapping.get(
        destination,
        destination
    )

def get_city_coordinates(destination):
    """Open-Meteo Geocoding API에서 여행지의 정확한 좌표를 가져옵니다."""

    destination = normalize_destination(destination)

    url = "https://geocoding-api.open-meteo.com/v1/search"

    params = {
        "name": destination,
        "count": 10,
        "language": "ko",
        "format": "json"
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if "results" not in data:
            return None

        results = data["results"]

        # 대한민국 결과만 우선 확인
        korean_results = [
            result
            for result in results
            if result.get("country_code") == "KR"
        ]

        if not korean_results:
            return None

        # 1순위: 도시명이 정확히 일치하는 결과
        exact_results = [
            result
            for result in korean_results
            if result.get("name", "").strip() == destination
        ]

        if exact_results:
            result = exact_results[0]

        else:
            # 2순위: 검색어가 도시명에 포함된 결과
            matching_results = [
                result
                for result in korean_results
                if destination in result.get("name", "")
            ]

            if matching_results:
                result = matching_results[0]
            else:
                result = korean_results[0]

        return {
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "name": result["name"],
            "country": result.get("country", ""),
            "country_code": result.get("country_code", ""),
            "admin1": result.get("admin1", "")
        }

    except (requests.RequestException, IndexError, KeyError):
        return None

def get_place_coordinates(place_name, destination):
    """관광지 이름을 OpenStreetMap에서 검색하여 좌표를 가져옵니다."""

    url = "https://nominatim.openstreetmap.org/search"

    # 관광지별 검색어 보정
    search_name_mapping = {
        "N 서울타워": "N서울타워",
        "N서울타워": "남산서울타워",
        "광화문광장": "Gwanghwamun Square",
    }

    search_name = search_name_mapping.get(
        place_name,
        place_name
    )

    search_query = f"{search_name}, {destination}"

    params = {
        "q": search_query,
        "format": "jsonv2",
        "limit": 5,
        "addressdetails": 1,
        "layer": "poi",
    }

    headers = {
        "User-Agent": "AI-Travel-Guide/1.0"
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if not data:
            return None

        result = data[0]

        return {
            "latitude": float(result["lat"]),
            "longitude": float(result["lon"]),
            "name": result.get(
                "display_name",
                place_name
            )
        }

    except (
        requests.RequestException,
        IndexError,
        KeyError,
        ValueError
    ):
        return None
    
def get_current_weather(destination):
    """도시명을 좌표로 변환한 후 현재 날씨를 가져옵니다."""

    location = get_city_coordinates(destination)

    if location is None:
        return None

    latitude = location["latitude"]
    longitude = location["longitude"]

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "weather_code"
        ),
        "timezone": "auto"
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        return data["current"]

    except (requests.RequestException, KeyError):
        return None

def get_weather_description(weather_code):

    weather_map = {
        0: "☀️ 맑음",
        1: "🌤️ 대체로 맑음",
        2: "⛅ 부분적으로 흐림",
        3: "☁️ 흐림",
        45: "🌫️ 안개",
        48: "🌫️ 짙은 안개",
        51: "🌦️ 약한 이슬비",
        53: "🌦️ 이슬비",
        55: "🌧️ 강한 이슬비",
        61: "🌧️ 약한 비",
        63: "🌧️ 비",
        65: "🌧️ 강한 비",
        71: "🌨️ 약한 눈",
        73: "🌨️ 눈",
        75: "❄️ 강한 눈",
        80: "🌦️ 약한 소나기",
        81: "🌧️ 소나기",
        82: "⛈️ 강한 소나기",
        95: "⛈️ 뇌우",
        96: "⛈️ 우박을 동반한 뇌우",
        99: "⛈️ 강한 우박을 동반한 뇌우"
    }

    return weather_map.get(
        weather_code,
        "🌤️ 날씨 정보 확인 필요"
    )
def create_travel_guide(
    destination,
    month,
    nights,
    travel_styles,
    additional_request
):
    prompt = f"""
        다음 여행 정보를 바탕으로 여행 가이드를 작성해주세요.

        여행지 : {destination}
        출발 시기 : {month}
        여행 기간 : {nights}박
        여행 스타일 : {", ".join(travel_styles)}
        추가 요청 : {additional_request}

        {weather_info}
        반드시 다음 정보를 포함해주세요.

        1. 여행지에 대한 요약
        2. 여행 시기의 일반적인 날씨와 현재 실제 날씨를 함께 고려한 날씨 정보
        3. 1인 기준 예상 에산
        4. 숙소 잡기 좋은 지역 3곳
        5. 맛집 추천
        6. 관광지 추천
        7. 숨은 명소 추천
        8. {nights}박 여행에 맞는 샘플 여행 일정
        해당 여행 시기의 평균적인 기온 범위를 제공해주세요.
        예: "-1~7℃"
        예상 예산은 1인 기준으로 계산해주세요.

        - min_budget: 현실적인 최소 예상 비용(원)
        - max_budget: 현실적인 최대 예상 비용(원)

        예를 들어 57만원~171만원이라면
        min_budget은 570000,
        max_budget은 1710000으로 반환해주세요.
        최신 정보가 필요한 항목은 웹 검색을 활용해주세요.
        각 관광지에 1.0~5.0 사이의 추천 점수를 부여해주세요.
        0.5 단위로 평가해주세요.
        추천 시즌은 해당 여행지에서 여행하기 좋은 시기와 그 이유를 설명해주세요.
        다음과 같은 형식으로 작성해주세요.

        예:
        "3월 말-4월 초의 벚꽃철이나 10월-11월 초의 선선한 가을이 가장 좋습니다.
        이 시기에는 걷기 편하고, 쇼핑과 맛집 동선도 쾌적합니다."

        여행지와 여행 스타일을 고려하여 실제 여행에 도움이 되는 내용으로 작성해주세요.
        현재 실제 날씨 정보가 제공된 경우 반드시 이를 참고하여 여행자에게 도움이 되는 날씨 분석을 작성해주세요.

        실제 날씨 정보와 해당 여행 시기의 일반적인 기후 정보는 구분해서 생각해주세요.

        - 실제 날씨 정보: 현재 시점의 기온, 체감온도, 습도, 날씨 상태
        - 일반적인 날씨 정보: 사용자가 선택한 출발 월의 평균적인 기온과 계절적 특징

        실제 날씨가 제공된 경우 다음 내용을 travel_forecast에 반영해주세요.

        - 현재 날씨가 야외 관광에 적합한지
        - 현재 기온과 체감온도를 고려한 옷차림
        - 비, 눈, 강수 가능성 등 현재 날씨와 관련된 주의사항
        - 현재 날씨에 적합한 여행 활동

        해당 여행지의 날씨 정보를 다음과 같이 작성해주세요.

        - temperature:
        해당 월의 일반적인 기온 범위
        예: "-1~7℃"

        - description:
        해당 여행지의 해당 월의 일반적인 날씨 특성을 설명해주세요.
        예: "6월의 도쿄는 초여름 날씨로 비교적 따뜻하고 습하며, 비가 자주 내리는 편입니다."

        - travel_forecast:
        travel_forecast에는 다음 내용을 포함해주세요.

        - 선택한 월의 해당 여행지에서 일반적으로 나타나는 날씨
        - 현재 실제 날씨 정보가 제공된 경우 현재 날씨를 함께 반영
        - 현재 기온과 체감온도에 따른 여행자의 체감
        - 현재 습도와 날씨 상태를 고려한 여행 적합성
        - 비, 눈, 흐림 등 현재 날씨에 따른 야외 활동 시 주의사항
        - 현재 날씨에 적합한 옷차림과 준비물

        예시:
        "6월 도쿄는 흐리거나 약한 비가 길게 이어지는 날이 많고,
        습도가 높습니다. 가벼운 옷차림과 접이식 우산이 유용합니다."
        
        숙소 잡기 좋은 지역은 정확히 3곳을 추천해주세요.

        각 지역은 다음 정보를 포함해야 합니다.

        - name: 지역 이름
        - reason: 해당 지역을 숙소로 추천하는 구체적인 이유
        - price_range: "저가", "중가", "고가" 중 하나
        - suitable_for: 이 지역이 잘 맞는 여행자 유형을 3개 정도

        reason은 다음과 같은 방식으로 작성해주세요.

        예:
        "도쿄 쇼핑의 중심축 중 하나로, 대형 상업시설과 트렌디한 브랜드,
        야간 식사 선택지가 모두 강합니다. 하라주쿠·오모테산도·다이칸야마로도
        이동이 쉬워 첫 방문자에게 특히 편합니다."

        suitable_for의 예시는 다음과 같습니다.

        - 첫 방문자
        - 쇼핑 동선
        - 야간 이동
        - 관광 중심
        - 맛집 탐방
        - 가족 여행
        - 가성비 여행
        - 조용한 숙박
        - 대중교통 중심

        여행지, 여행 스타일, 여행 기간을 고려하여
        각 지역의 특징에 맞게 적절한 항목을 선택해주세요.

        price_range은 반드시 다음 세 값 중 하나만 사용해주세요.

        "저가"
        "중가"
        "고가"

        맛집, 관광지, 숨은 명소를 각각 5곳씩 추천해주세요.

        각 추천 장소는 다음 정보를 포함해야 합니다.

        - name: 실제 존재하는 장소의 정확한 공식 명칭
        - description: 장소의 특징과 추천하는 이유를 1~2문장으로 작성
        - tips: 방문 팁 3개

        장소 이름은 지도 서비스나 공식 관광 안내에서 검색할 수 있는
        구체적인 명칭을 사용해주세요.

        관광지는 실제 존재하는 장소만 추천해주세요.
        설명을 임의로 조합한 장소명이나 여러 장소를 합친 이름을 사용하지 마세요.
        가능하면 관광지의 공식 명칭을 그대로 사용해주세요.
        tips는 반드시 3개의 짧고 실용적인 문장으로 작성해주세요.

        예:

        name:
        "야나카·네즈"

        description:
        "옛 도쿄의 분위기가 남아 있는 조용한 동네로,
        로컬 카페와 작은 상점, 산책하기 좋은 골목이 매력적입니다.
        재방문 여행자나 느린 여행을 선호하는 사람에게 특히 잘 맞습니다."

        tips:
        [
            "오후 산책 시간대에 방문하면 분위기가 좋습니다.",
            "네즈노타이야키 같은 현지 간식을 함께 즐겨보세요.",
            "우에노 관광지와 함께 묶어서 방문하기 좋습니다."
        ]

        다음 조건을 반드시 지켜주세요.

        - 맛집은 정확히 5곳
        - 관광지는 정확히 5곳
        - 숨은 명소는 정확히 5곳
        - 각 장소마다 name, description, tips를 모두 제공합니다.
        - 각 장소의 tips는 정확히 3개를 제공합니다.
        - 장소 이름은 실제 존재하는 장소를 기준으로 작성해주세요.
        - 여행지, 여행 기간, 출발 시기, 여행 스타일, 추가 요청을 고려하여 추천해주세요.
        - 관광지는 실제 존재하는 장소만 추천해주세요.
        - 관광지의 name은 실제 지도 서비스나 공식 관광 안내에서 사용하는 정확한 장소명을 사용해주세요.
        - 설명을 임의로 조합한 장소명이나 여러 장소를 합친 이름을 사용하지 마세요.
        - 관광지 이름에는 가능하면 대표적인 공식 명칭을 사용해주세요.
        - 관광지의 위치를 지도에서 검색할 수 있도록 구체적인 장소명을 사용해주세요.
        - 여행자의 취향과 요청에 잘 맞는 장소를 우선적으로 추천해주세요.
        - 최신 정보가 필요한 경우 웹 검색을 활용해주세요.
        - 관광지는 서로 다른 실제 장소를 추천해주세요.
        - 같은 장소를 다른 이름으로 중복 추천하지 마세요.
        - 예를 들어 '남산서울타워'와 'N서울타워'처럼 동일한 장소를 다른 명칭으로 중복해서 추천하지 마세요.
        - 관광지 5개는 반드시 서로 다른 실제 관광지여야 합니다.
        - 관광지 5개는 모두 서로 다른 장소여야 합니다.
        - 동일 장소의 다른 명칭, 약칭, 영어명, 별칭을 별도의 관광지로 취급하지 마세요.
        - 추천 전에 관광지 이름의 중복 여부를 확인해주세요.
        - 실제 여행자가 방문했을 때 도움이 되는 구체적인 정보를 우선해주세요.

        샘플 여행 일정을 여행 기간에 맞춰 작성해주세요.

        여행 기간이 3박이라면 Day 1부터 Day 4까지,
        4박이라면 Day 1부터 Day 5까지 작성해주세요.

        각 날짜는 다음 정보를 포함해야 합니다.

        - day: "Day 1", "Day 2"와 같은 형식
        - theme: 해당 날짜의 주요 지역이나 여행 테마
        - morning: 오전에 방문할 장소 또는 활동
        - afternoon: 오후에 방문할 장소 또는 활동
        - evening: 저녁에 방문할 장소 또는 활동

        여행지, 여행 기간, 출발 시기, 여행 스타일,
        추가 요청을 고려하여 현실적인 동선으로 구성해주세요.

        가능하면 같은 날에는 서로 가까운 지역을 묶어서
        불필요한 이동을 줄여주세요.

        맛집과 관광지뿐만 아니라 카페, 쇼핑, 산책 등의 활동도
        여행 스타일에 맞게 적절히 포함해주세요.

        각 시간대에는 너무 많은 장소를 넣지 말고,
        실제로 여행자가 이동하고 즐길 수 있는 정도의 일정으로 구성해주세요.

        교통 가이드를 작성해주세요.

        공항 또는 주요 도착 지점에서 시내로 이동하는 방법을 작성해주세요.

        - route: 대표적인 이동 경로
        - duration: 예상 소요 시간
        - cost: 해당 경로의 예상 편도 비용을 숫자만 입력
        - currency: 비용의 통화 단위
        - recommendation: 가장 추천하는 이동 방법과 그 이유

        cost는 반드시 숫자로만 작성해주세요.
        예를 들어 1240엔이라면 cost는 1240으로 작성하고,
        "약 1,240엔", "대중교통 기준 약 1,200엔"처럼 문장으로 작성하지 마세요.

        currency에는 "엔", "원", "달러" 등의 통화 단위를 작성해주세요.

        요금처럼 변경될 수 있는 정보는 웹 검색을 활용하여 최신 정보를 확인해주세요.
        
        여행 꿀팁을 5개 작성해주세요.

        여행지, 출발 시기, 여행 스타일, 여행 기간, 추가 요청을 고려하여
        실제 여행자가 바로 활용할 수 있는 실용적인 팁을 작성해주세요.

        다음과 같은 내용을 상황에 맞게 포함할 수 있습니다.

        - 현지 교통 이용 팁
        - 결제 및 현금 사용
        - 관광지 방문 시간
        - 식당 이용 팁
        - 편의점 이용
        - 날씨와 복장
        - 예약이 필요한 장소
        - 여행자가 주의해야 할 현지 문화
        - 여행 경비를 아끼는 방법

        단순하고 일반적인 여행 조언보다는
        해당 여행지에 실제로 도움이 되는 구체적인 정보를 우선해주세요.

        여행 꿀팁은 정확히 5개 작성해주세요.
        각 팁은 한 문장으로 작성해주세요.
        Markdown 기호나 번호를 붙이지 말고 일반 텍스트로 작성해주세요.

        여행 준비물 체크리스트를 작성해주세요.

        여행지, 출발 시기, 여행 기간, 여행 스타일, 추가 요청을 고려하여
        실제 여행에 필요한 준비물을 추천해주세요.

        각 준비물은 다음 정보를 포함해야 합니다.

        - item: 준비물 이름
        - reason: 해당 여행지와 여행 시기에 왜 필요한지 설명

        준비물은 정확히 5개 작성해주세요.

        단순히 모든 여행자에게 필요한 일반적인 준비물만 나열하지 말고,
        여행지와 출발 시기의 날씨, 현지 교통, 여행 스타일 등을 고려하여
        이번 여행에 특히 도움이 되는 준비물을 우선적으로 추천해주세요.

        reason은 한 문장으로 간결하고 구체적으로 작성해주세요.

        여행 전 확인해야 할 주의사항을 4~5개 작성해주세요.

        여행지, 출발 시기, 여행 기간, 여행 스타일을 고려하여
        실제 여행자가 출발 전에 확인하면 좋은 내용을 작성해주세요.

        특히 다음과 같이 최신 정보가 필요한 내용은 웹 검색을 활용해주세요.

        - 관광지 운영시간 및 휴무일
        - 인기 관광지의 예약 및 입장 정책
        - 식당 예약 및 영업 여부
        - 대중교통 운행 정보
        - 여행 시기의 날씨 및 기상 상황
        - 현지에서 주의해야 할 사항

        단순하고 일반적인 주의사항보다는
        해당 여행지에 실제로 도움이 되는 구체적인 내용을 우선해주세요.

        정확히 5개의 주의사항을 작성해주세요.
        각 항목은 한 문장으로 간결하게 작성해주세요.

        여행 예산을 절약할 수 있는 방법을 작성해주세요.

        앞에서 계산한 예상 예산과 여행지의 물가,
        여행 기간, 여행 스타일을 고려하여 실제로 비용을 줄이는 데 도움이 되는
        구체적인 방법을 추천해주세요.

        다음과 같은 카테고리를 활용해주세요.

        - 숙박
        - 식비
        - 교통
        - 관광
        - 쇼핑

        각 항목은 다음 정보를 포함해야 합니다.

        - category: 비용 카테고리
        - tip: 해당 카테고리에서 비용을 절약할 수 있는 구체적인 방법

        여행자의 여행 스타일과 일정에 맞지 않는 절약 방법은 추천하지 마세요.

        예를 들어 쇼핑을 중요하게 생각하는 여행자에게
        단순히 쇼핑을 하지 말라고 추천하지 마세요.

        예산 절약 팁은 4~5개 작성해주세요.
    """

    response = client.responses.parse(
        model=MODEL,
        tools=[
            {"type": "web_search"}
        ],
        input=prompt,
        text_format=TravelGuide
    )

    return response.output_parsed

st.title("AI 여행 도우미 ✈️")
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

data_path = DATA_DIR / "관광공사_지역별_방문자수_2026.csv"

travel_df = pd.read_csv(data_path)
travel_df["기준일"] = pd.to_datetime(travel_df["기준일"])
col1, col2 = st.columns([2.5, 2.5])
with col1:
    with st.container(border=True):
        st.subheader("🔎 여행지 검색")
        st.caption("관심 있는 지역을 검색해 방문자 수와 전국 순위를 확인해보세요.")

        search_keyword = st.text_input(
            "여행지를 검색하세요.",
            placeholder="예: 서울, 중구, 부산, 제주"
        )
        st.warning(
            "⚠️ 검색 결과는 한국관광공사의 실제 데이터를 기반으로 하며, "
            "현재 서비스에 저장된 CSV 데이터에 포함된 여행지(지역)를 기준으로 제공됩니다."
        )
with col2:
    with st.container(border=True):
        st.subheader("❤️ 내가 저장한 여행지")

        if st.session_state.favorite_places:

            # 지역별 누적 방문자 수 계산
            favorite_df = (
                travel_df.groupby("지역", as_index=False)["방문자수"]
                .sum()
                .sort_values("방문자수", ascending=False)
                .reset_index(drop=True)
            )

            # 전국 순위 계산
            favorite_df["순위"] = favorite_df.index + 1

            # 내가 저장한 지역만 선택
            favorite_df = favorite_df[
                favorite_df["지역"].isin(st.session_state.favorite_places)
            ]

            for _, row in favorite_df.iterrows():
                with st.container(border=True):
                    st.markdown(f"### 🗺️ {row['지역']}")

                    st.write(f"🏆 **전국 순위:** {row['순위']}위")
                    st.write(f"👥 **누적 방문자 수:** {row['방문자수']:,.0f}명")

if search_keyword:
    # 검색한 지역 키워드를 통해 지역에 따른 방분자수를 정렬 시킴
    region_summary = (
        travel_df.groupby("지역", as_index=False)["방문자수"]
        .sum()
        .sort_values("방문자수", ascending=False)
        .reset_index(drop=True)
    )
    # 순위를 계산
    region_summary["순위"] = region_summary.index + 1
    # 검색 결과를 저장시킴
    search_result = region_summary[
        region_summary["지역"].str.contains(
            search_keyword,
            case=False,
            na=False
        )
    ]
    # 검색결과가 비어있지 않다면
    if not search_result.empty:
        with st.container(border=True):
            st.markdown("### 📍 검색 결과")
            # 검색 결과를 카드형태로 출력되게 했습니다.
            for _, row in search_result.iterrows():
                with st.container(border=True):
                    region = row["지역"]

                    st.markdown(f"#### 📍 {region}")

                    col1, col2,  = st.columns([2, 2])

                    with col1:
                        st.metric(
                            "🏆 전국 순위",
                            f"{row['순위']}위"
                        )

                    
                        st.metric(
                            "👥 누적 방문자 수",
                            f"{row['방문자수']:,.0f}명"
                        )

                    with col2:
                        # 관심 여행지를 추가하거나 삭제가 가능합니다.
                        if region in st.session_state.favorite_places:
                            if st.button(
                                "💔 관심 여행지 삭제",
                                key=f"remove_{region}",
                                use_container_width=True
                            ):
                                st.session_state.favorite_places.remove(region)
                                st.rerun()
                        else:
                            if st.button(
                                "❤️ 관심 여행지 추가",
                                key=f"add_{region}",
                                use_container_width=True
                            ):
                                st.session_state.favorite_places.append(region)
                                st.rerun()
                        # 이 버튼을 누르면 자동으로 AI 여행 가이드 폼에 여행지 항목에 선택한 지역명이 기록됩니다.
                        if st.button(
                            "🤖 AI 여행 가이드",
                            key=f"guide_{region}",
                            use_container_width=True
                        ):
                            st.session_state.selected_destination = region
                            st.rerun()
                    

    else:
        st.info("검색 결과가 없습니다.")
st.caption(
    "여행지를 알려주시면 맛집, 관광지, 날씨, 예산까지 AI가 한 번에 정리해 드려요."
)

# 여행 정보를 입력받는 폼을 만드세요.
# - 여행 가이드를 만드는 데 필요한 정보를 모두 입력받도록 구성
# - 폼 제출 버튼도 포함
with st.form("form"):
    col1, col2 = st.columns([3, 3])

    with col1:
        if "selected_destination" not in st.session_state:
            st.session_state.selected_destination = ""

        destination = st.text_input(
            "여행지",
            value=st.session_state.selected_destination,
            placeholder="예: 도쿄"
        )

        if destination:

            current_weather = get_current_weather(destination)

            if current_weather:

                temperature = current_weather["temperature_2m"]
                apparent_temperature = current_weather["apparent_temperature"]
                humidity = current_weather["relative_humidity_2m"]
                weather_code = current_weather["weather_code"]

                weather_description = get_weather_description(
                    weather_code
                )

                weather_info = f"""
                현재 실제 날씨 정보:
                - 현재 기온: {current_weather["temperature_2m"]}℃
                - 체감온도: {current_weather["apparent_temperature"]}℃
                - 습도: {current_weather["relative_humidity_2m"]}%
                - 날씨 상태: {get_weather_description(current_weather["weather_code"])}

                주의:
                위 정보는 현재 시점의 실제 날씨 정보입니다.
                사용자가 선택한 여행 시기의 일반적인 날씨 정보와 구분하여 활용해주세요.
                현재 날씨 정보를 근거 없이 미래의 날씨로 단정하지 마세요.
                """
                with st.container(border=True):
                    st.markdown("## 🌤️ 현재 날씨")

                    weather_col1, weather_col2 = st.columns(2)

                    with weather_col1:
                        st.metric(
                            "🌡️ 현재 기온",
                            f"{temperature}℃"
                        )
                        st.metric(
                            "🧥 체감온도",
                            f"{apparent_temperature}℃"
                        )

                    with weather_col2:
                        st.metric(
                            "💧 습도",
                            f"{humidity}%"
                        )
                        st.metric(
                            "☁️ 날씨",
                            weather_description
                        )

            else:
                weather_info = """
                현재 실시간 날씨 정보를 가져올 수 없습니다.
                날씨 관련 내용은 일반적인 계절 정보를 기준으로 안내해주세요.
                """

                st.info(
                    "현재 입력한 여행지의 실시간 날씨 정보를 "
                    "불러올 수 없습니다."
                )


    # 👇 처음 만든 col2에서 출발 시기 선택
    with col2:

        month = st.selectbox(
            "출발 시기",
            options=MONTHS
        )

        with st.container(border=True):

            st.markdown("## 🧳 여행 준비")

            if destination and current_weather:

                temperature = current_weather["temperature_2m"]
                apparent_temperature = current_weather["apparent_temperature"]
                weather_code = current_weather["weather_code"]

                # 옷차림 추천
                if apparent_temperature <= 5:
                    clothing = "🧥 두꺼운 외투를 추천합니다."
                elif apparent_temperature <= 15:
                    clothing = "🧥 겉옷이나 재킷을 추천합니다."
                elif apparent_temperature <= 25:
                    clothing = "👕 가벼운 겉옷을 준비하면 좋습니다."
                else:
                    clothing = "👕 가벼운 옷차림을 추천합니다."

                # 우산/비 관련 안내
                rain_codes = {
                    51, 53, 55,
                    61, 63, 65,
                    80, 81, 82,
                    95, 96, 99
                }

                if weather_code in rain_codes:
                    umbrella = "☔ 우산을 준비하는 것이 좋습니다."
                else:
                    umbrella = "☀️ 현재 강수 관련 주의가 크지 않습니다."

                st.markdown("### 👕 옷차림")
                st.write(clothing)

                st.markdown("### ☔ 우천 대비")
                st.write(umbrella)

                st.markdown("### 🌡️ 체감온도 기준")
                st.write(
                    f"현재 체감온도는 **{apparent_temperature}℃**입니다."
                )

            else:

                st.info(
                    "여행지를 입력하면 현재 날씨를 기준으로 "
                    "여행 준비 정보를 안내합니다."
                )
        # 🗺️ 여행지 위치
    if destination:

        location = get_city_coordinates(destination)

        if location:

            latitude = location["latitude"]
            longitude = location["longitude"]

            map_df = pd.DataFrame({
                "lat": [latitude],
                "lon": [longitude]
            })

            st.markdown("## 🗺️ 여행지 위치")
            st.warning(
                "⚠️ 여행지 위치 안내\n\n"
                "본 지도는 한국관광공사의 실제 관광 데이터를 기반으로 "
                "여행지를 검색한 후 그 결과로 **AI 여행 가이드**버튼을 클릭했을 때 위치로 제공됩니다. "
                "지도는 선택된 여행지의 좌표 정보를 기준으로 표시되며, "
                "개별 관광지의 정확한 위치를 의미하지 않습니다."
            )
            with st.container(border=True):
                st.map(
                    map_df,
                    zoom=10
                )

        else:
            st.info(
                "입력한 여행지의 위치 정보를 찾을 수 없습니다."
            )
    
    col3, col4 = st.columns(2)
    with col3:
        nights = st.number_input(label="여행 기간 (박)", min_value=1, max_value=30, value=3, step=1)    
    with col4:
        travel_styles = st.multiselect(label="여행 스타일", options=TRAVEL_STYLES)
    additional_request = st.text_area(label="추가 요청 (선택)", placeholder="예:비건 식당 위주로 / 아이랑 같이 / 대중교통 중심")

    clicked = st.form_submit_button("AI 여행 가이드 만들기 ✨")
# 폼이 제출되었다면:
if clicked:
    if not destination:
        st.warning("여행지를 입력해주세요.")

    elif not travel_styles:
        st.warning("여행 스타일을 하나 이상 선택해주세요.")
    else:
        with st.spinner("최신 여행 정보를 검색하고 있어요... ✈️"):

            guide = create_travel_guide(
                destination=destination,
                month=month,
                nights=nights,
                travel_styles=travel_styles,
                additional_request=additional_request
            )

        
# 1) AI 여행 가이드를 생성하는 함수를 호출해 결과를 받으세요.
# 2) 결과를 화면에 섹션별로 그리세요.
# 제출되지 않았다면 사용법 안내 메시지를 표시하세요.
            with st.container(border=True):
                st.divider()
                st.header(f"🌍 {destination} 여행 가이드")

                st.subheader("여행 요약")
                st.write(guide.summary)

                st.caption(f"📅추천 시즌: {guide.recommended_season}")
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        "📅기간",
                        f"{nights}박 {nights + 1}일"
                    )

                with col2:
                    st.metric(
                        f"🌡️{month} 기온",
                        guide.weather.temperature
                    )
                budget_text = (
                    f"{guide.budget.min_budget // 10000:,}"
                    f"~"
                    f"{guide.budget.max_budget // 10000:,}만원"
                )
                with col3:
                    st.metric(
                        "💰 예상 예산 (1인)",
                        budget_text
                    )
                col4, col5 = st.columns(2)
                with col4:
                    with st.container(border=True):
                        st.subheader("☀️ 날씨")
                        st.write(guide.weather.description)

                        st.subheader(f"{month} 예상")
                        st.write(guide.weather.travel_forecast)
                with col5:
                    with st.container(border=True):
                        st.subheader("💰 예산 상세(1인 기준)")

                        st.write(
                            f"🏨숙박 (1박): {guide.budget.accommodation_min // 10000}~{guide.budget.accommodation_max // 10000}만원"
                        )

                        st.write(
                            f"🍽️식사 (하루): {guide.budget.food_min // 10000}~{guide.budget.food_max // 10000}원"
                        )

                        st.write(
                            f"🚃교통 (하루): {guide.budget.transportation_min // 10000}~{guide.budget.transportation_max // 10000}원"
                        )
                        st.write(
                            f"🎟️관광 / 입장료 (하루): {guide.budget.etc_min // 10000}~{guide.budget.etc_max // 10000}원"
                        )
                        st.warning(
                            "시즌/환율/개인 소비에 따라 달라질 수 있으니 참고용"
                        )

            with st.container(border=True):    
                st.header("🏨숙소 잡기 좋은 지역")
                st.caption("AI가 추천하는 동네와 그 이유예요. 실제 호텔 가격·예약 가능 여부는 예약 사이트에서 확인해주세요.")

                columns = st.columns(3)
                for col, area in zip(columns, guide.recommended_areas):
                    with col:
                        with st.container(border=True):

                            # 지역 이름
                            st.subheader(area.name)

                            # 추천 이유
                            st.write(area.reason)

                            # 가격대
                            st.write(f"가격대 · {area.price_range}")

                            # 이런 분께
                            st.caption("이런 분께")

                            # 추천 대상
                            st.write(" · ".join(area.suitable_for))

            with st.container():
                st.header("🧭 큐레이션")
                st.caption("각 장소를 클릭하면 방문 팁이 펼쳐져요.")

                tab1, tab2, tab3 = st.tabs([
                    "🍜 맛집",
                    "🏛️ 관광지",
                    "✨ 숨은 명소"
                ])

                with tab1:
                    for place in guide.restaurants:
                        with st.expander(place.name):
                            st.write(place.description)

                            for tip in place.tips:
                                st.write(f"· {tip}")

                with tab2:
                    for place in guide.attractions:
                        with st.expander(place.name):
                            st.write(place.description)

                            for tip in place.tips:
                                st.write(f"· {tip}")

                with tab3:
                    for place in guide.hidden_spots:
                        with st.expander(place.name):
                            st.write(place.description)

                            for tip in place.tips:
                                st.write(f"· {tip}")
                # 🗺️ 추천 관광지 위치
                with st.container(border=True):

                    st.header("🗺️ 추천 관광지 위치")

                    st.caption(
                        "AI 여행 가이드에서 추천한 관광지의 위치를 지도에 표시합니다."
                    )

                    attraction_locations = []

                    for attraction in guide.attractions:

                        location = get_place_coordinates(
                            attraction.name,
                            destination
                        )

                        if location:

                            # 이미 같은 좌표가 등록되어 있는지 확인
                            duplicate = any(
                                item["lat"] == location["latitude"]
                                and item["lon"] == location["longitude"]
                                for item in attraction_locations
                            )

                            if not duplicate:
                                attraction_locations.append({
                                    "관광지": attraction.name,
                                    "lat": location["latitude"],
                                    "lon": location["longitude"]
                                })

                        # Nominatim 공용 서버 요청 제한 준수
                        time.sleep(1)

                    if attraction_locations:

                        st.success(
                            f"총 {len(attraction_locations)}개의 "
                            "관광지 위치를 찾았습니다."
                        )

                        attraction_map_df = pd.DataFrame(attraction_locations)

                        # tooltip에서 사용할 영문 컬럼명
                        attraction_map_df["place_name"] = (
                            attraction_map_df["관광지"].astype(str)
                        )

                        layer = pdk.Layer(
                            "ScatterplotLayer",
                            data=attraction_map_df,
                            get_position="[lon, lat]",
                            get_radius=500,
                            get_fill_color=[255, 80, 80, 255],
                            get_line_color=[255, 255, 255, 255],
                            get_line_width=3,
                            pickable=True,
                            auto_highlight=True,
                            filled=True,
                            stroked=True,
                        )

                        view_state = pdk.ViewState(
                            latitude=attraction_map_df["lat"].mean(),
                            longitude=attraction_map_df["lon"].mean(),
                            zoom=11
                        )

                        deck = pdk.Deck(
                            layers=[layer],
                            initial_view_state=view_state,
                            tooltip={
                                "html": "<b>{place_name}</b>",
                                "style": {
                                    "backgroundColor": "white",
                                    "color": "black",
                                    "fontSize": "16px",
                                    "padding": "8px"
                                }
                            }
                        )

                        st.pydeck_chart(
                            deck,
                            use_container_width=True
                        )
                    else:

                        st.warning(
                            "추천 관광지의 위치 정보를 찾을 수 없습니다."
                        )
            with st.container():
                st.header("참고용 샘플 일정")
                st.caption("실제 일정이 아니라 '이렇게 보낼 수도 있어요.'라는 감을 드리기 위한 예시예요. 원하는 대로 자유롭게 바꿔 보세요.")
                schedule_data = [
                    {
                        "일자": item.day,
                        "테마": item.theme,
                        "오전": item.morning,
                        "오후": item.afternoon,
                        "저녁": item.evening
                    }
                    for item in guide.schedule
                ]

                st.table(schedule_data)
            with st.container(border=True):
                st.header("🚇 교통 가이드")
                st.caption("여행지에서 이동할 때 참고하세요.")
                with st.container(border=True):
                    st.subheader("✈️ 공항 → 시내")

                    st.write(
                        guide.transportation.airport_to_city.route
                    )

                    col1, col2 = st.columns([4,2])

                    with col1:
                        with st.container(border=True):
                            st.metric(
                                "예상 소요시간",
                                guide.transportation.airport_to_city.duration
                            )

                    with col2:
                        with st.container(border=True):
                            st.metric(
                                "예상 비용",
                                f"{guide.transportation.airport_to_city.cost:,}{guide.transportation.airport_to_city.currency}"
                            )

                    st.info(
                        guide.transportation.airport_to_city.recommendation
                    )

                col1, col2 = st.columns(2)

                with col1:
                    with st.container(border=True):
                        st.subheader("🚇 현지 대중교통")
                        st.write(guide.transportation.public_transport)

                with col2:
                    with st.container(border=True):
                        st.subheader("💳 교통카드 / 패스")
                        st.write(guide.transportation.transit_card)

                # 교통 팁
                with st.expander("💡 교통 이용 팁"):
                    for tip in guide.transportation.transportation_tips:
                        st.write(f"· {tip}")

            with st.container(border=True):
                st.header("💡 여행 꿀팁")
                st.caption("AI가 여행지와 여행 스타일을 고려해 추천하는 실용적인 팁이에요.")

                for tip in guide.travel_tips:
                    st.write(f"• {tip}")

            with st.container(border=True):
                st.header("🎒 여행 준비물")
                st.caption("이번 여행에 특히 도움이 되는 준비물이에요.")

                cols = st.columns(2)

                for i, packing in enumerate(guide.packing_list):
                    with cols[i % 2]:
                        with st.container(border=True):
                            st.write(f"☑ **{packing.item}**")
                            st.caption(packing.reason)

            with st.container(border=True):
                st.header("⚠️ 여행 전 확인사항")
                st.caption("출발 전에 확인하면 좋은 사항을 정리했어요.")

                for warning in guide.travel_warnings:
                    st.write(f"• {warning}")

            with st.container(border=True):
                st.header("💰 예산 절약 팁")
                st.caption("여행의 즐거움은 유지하면서 비용을 아낄 수 있는 방법이에요.")

                cols = st.columns(2)

                for i, tip in enumerate(guide.budget_tips):
                    with cols[i % 2]:
                        with st.container(border=True):
                            st.subheader(tip.category)
                            st.write(tip.tip)