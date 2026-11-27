"""
Makeshop API Client Service

이 모듈은 Makeshop API와의 상호작용을 담당합니다.
상품, 주문, 회원 정보를 API를 통해 조회하고 동기화합니다.
"""

import os
import requests
import logging
from typing import List, Dict, Any, Optional, cast

logger = logging.getLogger(__name__)

# 메이크샵 API 에러 코드 매핑
MAKESHOP_ERROR_CODES = {
    "0000": "정상",
    "9000": "기본 요청 정보가 없습니다.",
    "9001": "상점키가 없습니다.",
    "9002": "검색된 상점키가 없습니다.",
    "9003": "라이센스키가 없습니다.",
    "9004": "검색된 라이센스키가 없습니다.",
    "9005": "허가된 업체가 아닙니다.",
    "9006": "API 연동이 초과되었습니다.",
    "9007": "API 조회 권한이 없습니다. 상점에 문의해 주시기 바랍니다.",
    "9008": "API 조회 권한이 없습니다. 메이크샵 담당자에게 문의해 주시기 바랍니다.",
    "9009": "허가된 IP가 아닙니다.",
    "9011": "검색된 내역이 없습니다.",
    "9012": "조회 시작일이 없습니다.",
    "9013": "조회 시작일 날짜의 형식이 맞지 않습니다.",
    "9014": "조회 시작일이 맞지 않습니다.",
    "9015": "조회 종료일 날짜의 형식이 맞지 않습니다.",
    "9016": "조회 종료일이 맞지 않습니다.",
    "9017": "조회 기간을 확인해 주세요.",
    "9018": "조회 기간은 30일을 초과할 수 없습니다.",
    "9019": "조회 날짜 형식이 맞지 않습니다.",
    "9021": "조회할 주문번호가 없습니다.",
    "9031": "조회할 아이디가 없습니다.",
    "9032": "조회는 1000개 이상 할 수 없습니다.",
    "9033": "다중 조회 횟수를 초과하였습니다.",
    "9034": "다중 검색 값이 배열이 아닙니다.",
    "9041": "숫자가 아닙니다.",
    "9051": "게시판 조회 코드가 필요합니다.",
    "9061": "쿠폰 코드가 필요합니다.",
    "9062": "쿠폰 검색타입이 필요합니다.",
    "9063": "스마트쿠폰 적용 상점은 사용할수 없습니다.",
    "9064": "스마트쿠폰 미적용 상점은 사용할수 없습니다.",
    "9071": "상품번호가 없습니다.",
    "9081": "서버 부하로 인한 조회 기간이 조정되었습니다.",
    "9101": "상점 관리자가 Open API 서비스 이용 동의를 하지 않았습니다.",
    "9102": "상점 관리자가 Open API 제 3자 제공 동의를 하지 않았습니다.",
    "9103": "API 처리 권한이 없습니다. 상점에 문의해 주시기 바랍니다.",
    "9104": "API 처리 권한이 없습니다. 메이크샵 담당자에게 문의해 주시기 바랍니다.",
    "9201": "datas 값이 없습니다.",
    "9202": "datas 값이 배열이 아닙니다.",
    "9203": "1회 최대 처리 한도를 초과하였습니다.",
    "9204": "POST로 전달받은 값이 없습니다.",
    "9221": "상품 준비중 리스트 미사용",
    "9401": "디자인 버전 D4를 사용해야 합니다.",
    "9901": "지원하지 않는 mode 입니다.",
    "9902": "해당 기능(포인트, emoney 등)이 사용 안함 상태입니다.",
    "9997": "DB 등록 실패",
    "9998": "상점 이용 기간이 만료되었습니다.",
    "9999": "fail, message가 출력됩니다."
}


class MakeshopAPIError(Exception):
    """메이크샵 API 오류"""
    def __init__(self, return_code: str, message: str):
        self.return_code = return_code
        self.message = message
        super().__init__(f"[Makeshop API Error] {return_code}: {message}")


class MakeshopAPIClient:
    """Makeshop API를 호출하기 위한 클라이언트"""

    def __init__(self):
        """Makeshop API 클라이언트 초기화 (레거시 Open API — 비활성)."""
        # 레거시 구 Open API 미사용. REST(MakeshopRestClient)만 사용.
        # self.shop_key = os.getenv("MAKESHOP_SHOPKEY")
        # self.license_key = os.getenv("MAKESHOP_LICENSEKEY")
        # shop_domain = os.getenv("MAKESHOP_API_URL")
        # if not shop_domain:
        #     raise ValueError("MAKESHOP_API_URL 환경변수가 설정되어 있지 않습니다.")
        # if not shop_domain.startswith("http://") and not shop_domain.startswith("https://"):
        #     self.shop_domain = f"http://{shop_domain}"
        # else:
        #     self.shop_domain = shop_domain
        # self.timeout = int(os.getenv("MAKESHOP_API_TIMEOUT", 60))
        # if not self.shop_key or not self.license_key:
        #     raise ValueError(
        #         "Makeshop API 인증 정보가 누락되었습니다. "
        #         "MAKESHOP_API_KEY(Shopkey)와 MAKESHOP_SHOP_ID(Licensekey)를 설정하세요."
        #     )
        # self.headers = {
        #     "Shopkey": self.shop_key,
        #     "Licensekey": self.license_key,
        # }
        raise RuntimeError(
            "Makeshop legacy Open API is disabled "
            "(MAKESHOP_SHOPKEY / MAKESHOP_LICENSEKEY / MAKESHOP_API_URL unused). "
            "Use REST via MakeshopRestClient."
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Makeshop API 요청을 실행합니다.
        
        예: http://www.babbasmartclass.com/list/open_api.html?mode=search&type=product&page=1

        Args:
            method: HTTP 메서드 (GET, POST)
            endpoint: API 엔드포인트 (예: /list/open_api.html)
            params: 쿼리 파라미터 (mode, type, page, limit 등)
            json_data: JSON 바디

        Returns:
            API 응답 데이터

        Raises:
            requests.RequestException: API 요청 실패 시
        """
        url = f"{self.shop_domain}{endpoint}"

        try:
            print(f"[MakeShop API 호출] {method} {url}")
            print(f"[MakeShop 요청 파라미터] {params}")

            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json_data,
                timeout=self.timeout
            )

            response.raise_for_status()

            # JSON 응답 시도
            try:
                data = response.json()
            except Exception:
                # JSON이 아닌 경우 텍스트로 반환
                print(f"[MakeShop 응답 (Text)] {response.text[:1000]}")
                data = {
                    "status": "success",
                    "data": response.text,
                    "content_type": response.headers.get('content-type')
                }
            
            # Makeshop API 응답 처리
            # HTTP 200으로 돌아오는 모든 응답 데이터를 그대로 반환
            # (성공/오류 판단은 클라이언트가 return_code 확인)
            if isinstance(data, dict):
                print(f"[MakeShop 응답 데이터] {data}")
                return data
            
            print(f"[MakeShop 응답] {data}")
            return data

        except requests.exceptions.Timeout:
            error_msg = f"[MakeShop API 오류] 요청 타임아웃 ({self.timeout}초): {url}"
            print(error_msg)
            raise Exception(error_msg)

        except requests.exceptions.ConnectionError:
            error_msg = f"[MakeShop API 오류] 연결 실패: {url}"
            print(error_msg)
            raise Exception(error_msg)

        except requests.exceptions.HTTPError as e:
            error_msg = f"[MakeShop API 오류] HTTP {e.response.status_code}: {e.response.text[:500]}"
            print(error_msg)
            raise Exception(error_msg)

        except Exception as e:
            error_msg = f"[MakeShop API 오류] {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def _get_error_message(self, return_code: Any) -> str:
        """
        Makeshop API 오류 코드를 해석합니다.
        
        Args:
            return_code: API 응답 코드
            
        Returns:
            오류 메시지
        """
        error_codes = {
            "9000": "요청 형식 오류",
            "9001": "필수 파라미터 누락",
            "9002": "잘못된 상점 정보",
            "9003": "인증 실패",
            "9004": "권한 없음",
            "9005": "존재하지 않는 리소스",
            "9006": "요청 실패",
            "9999": "시스템 오류"
        }
        return error_codes.get(str(return_code), f"알 수 없는 오류 (코드: {return_code})")

    def get_delivery_companies(self) -> List[Dict[str, Any]]:
        """
        Makeshop에서 사용 가능한 택배사 목록을 조회합니다.

        Returns:
            List[Dict[str, Any]]: 각 택배사 항목은 {'id': int, 'name': str} 형식입니다.

        Raises:
            MakeshopAPIError: API에서 오류 코드가 반환되는 경우
            Exception: 요청 실패 시
        """
        endpoint = "/list/open_api.html"
        params = {
            "mode": "search",
            "type": "delivery_company"
        }

        data = self._request("GET", endpoint, params=params)

        # Makeshop 응답의 return_code 확인
        return_code = None
        if isinstance(data, dict):
            return_code = data.get("return_code") or data.get("status")

        if str(return_code) not in {"0000", "0", "success", "OK"}:
            # 상세 오류 메시지 추출
            msg = data.get("message") if isinstance(data, dict) else str(data)
            raise MakeshopAPIError(str(return_code), msg or self._get_error_message(return_code))

        # 목록 리턴
        if isinstance(data, dict):
            lst = data.get("list") or data.get("data") or []
            # 표준화: 각 항목을 dict로 변환
            normalized: List[Dict[str, Any]] = []
            for item in lst:
                if isinstance(item, dict):
                    normalized.append(item)
                else:
                    # 경우에 따라 obj-like 응답일 수 있어 속성 접근 시도
                    try:
                        normalized.append({"id": getattr(item, "id", None), "name": getattr(item, "name", None)})
                    except Exception:
                        normalized.append({"raw": item})
            return normalized

        # 그 외 응답 형식은 그대로 반환
        return data

    # ========================================================================
    # 상품(Products) API 메서드
    # ========================================================================

    def get_products(
        self,
        page: int = 1,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Makeshop에서 상품 목록을 조회합니다.

        Args:
            page: 페이지 번호 (기본값: 1)
            limit: 페이지당 항목 수 (기본값: 100)
            status: 상품 상태 필터 (active, inactive, discontinued)

        Returns:
            상품 목록

        Example:
            >>> products = client.get_products(page=1, limit=50)
            >>> for product in products:
            ...     print(product['name'], product['price'])
        """
        params: Dict[str, Any] = {
            "page": page,
            "limit": limit
        }

        if status:
            params["status"] = status

        # Makeshop Open API 엔드포인트
        endpoint = "/list/open_api.html"
        params["mode"] = "search"
        params["type"] = "product"

        try:
            response = self._request("GET", endpoint, params=params)
            # API 응답 구조에 따라 처리
            products = response.get("data", response.get("products", []))
            print(f"[상품 조회 결과] 조회된 상품 수: {len(products)}")
            print(f"[상품 조회 상세] {response}")
            return products

        except Exception as e:
            print(f"[상품 조회 실패] {str(e)}")
            raise

    def get_product(self, product_id: str) -> Dict[str, Any]:
        """
        특정 상품 정보를 조회합니다.

        Args:
            product_id: Makeshop 상품 ID

        Returns:
            상품 정보

        Example:
            >>> product = client.get_product("PROD123456")
            >>> print(product['name'], product['price'])
        """
        endpoint = "/list/open_api.html"
        params = {
            "mode": "search",
            "type": "product",
            "product_id": product_id
        }

        try:
            response = self._request("GET", endpoint, params=params)
            product = response.get("data", response.get("product", {}))
            print(f"[상품 상세조회] {product.get('name')}")
            return product

        except Exception as e:
            print(f"[상품 상세조회 실패] (ID: {product_id}): {str(e)}")
            raise

    # ========================================================================
    # 주문(Orders) API 메서드
    # ========================================================================

    def get_orders(
        self,
        page: int = 1,
        limit: int = 100,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        주문 목록을 조회합니다.

        Args:
            page: 페이지 번호
            limit: 페이지당 항목 수
            status: 주문 상태 필터 (pending, processing, shipped, delivered)
            start_date: 조회 시작 날짜 (YYYY-MM-DD, 기본값: 2025-01-01)
            end_date: 조회 종료 날짜 (YYYY-MM-DD, 기본값: 오늘)

        Returns:
            주문 목록

        Example:
            >>> orders = client.get_orders(page=1, status="pending")
            >>> for order in orders:
            ...     print(order['order_id'], order['total_price'])
        """
        # 기본값 설정
        if start_date is None:
            # 검색 시작일: 2025년 1월 1일 00:00:00
            start_date = "2025-01-01 00:00:00"
        if end_date is None:
            # 검색 종료일: 오늘 23:59:59
            from datetime import datetime
            end_date = datetime.now().strftime("%Y-%m-%d 23:59:59")
        
        params: Dict[str, Any] = {
            "page": page,
            "limit": limit,
            "mode": "search",
            "type": "order",
            "InquiryTimeFrom": start_date,
            "InquiryTimeTo": end_date
        }

        if status:
            params["status"] = status

        endpoint = "/list/open_api.html"

        try:
            response = self._request("GET", endpoint, params=params)
            orders = response.get("data", response.get("orders", []))
            print(f"[주문 조회 결과] 조회된 주문 수: {len(orders)}, 기간: {start_date} ~ {end_date}")
            print(f"[주문 조회 상세] {response}")
            return orders

        except Exception as e:
            print(f"[주문 조회 실패] {str(e)}")
            raise

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        특정 주문 정보를 조회합니다.

        Args:
            order_id: Makeshop 주문 ID

        Returns:
            주문 정보 (상세)

        Example:
            >>> order = client.get_order("ORDER123456")
            >>> print(order['customer_name'], order['items'])
        """
        endpoint = "/list/open_api.html"
        params = {
            "mode": "search",
            "type": "order",
            "order_id": order_id
        }

        try:
            response = self._request("GET", endpoint, params=params)
            order = response.get("data", response.get("order", {}))
            print(f"[주문 상세조회] {order.get('order_id')}")
            return order

        except Exception as e:
            print(f"[주문 상세조회 실패] (ID: {order_id}): {str(e)}")
            raise

    def update_order_status(
        self,
        order_id: str,
        status: str
    ) -> Dict[str, Any]:
        """
        주문 상태를 업데이트합니다.

        Args:
            order_id: Makeshop 주문 ID
            status: 새로운 상태 (pending, processing, shipped, delivered, cancelled)

        Returns:
            업데이트 결과

        Example:
            >>> result = client.update_order_status("ORDER123456", "shipped")
        """
        endpoint = "/list/open_api.html"
        params = {
            "mode": "update",
            "type": "order_status",
            "order_id": order_id,
            "status": status
        }

        try:
            response = self._request("POST", endpoint, params=params)
            print(f"[주문 상태 업데이트] {order_id} -> {status}")
            return response

        except Exception as e:
            print(f"[주문 상태 업데이트 실패] {str(e)}")
            raise

    # ========================================================================
    # 회원정보(Members/Customers) API 메서드
    # ========================================================================

    def get_members(
        self,
        page: int = 1,
        limit: int = 100,
        search_text: Optional[str] = None
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Makeshop에서 회원 목록을 조회합니다.

        Args:
            page: 페이지 번호 (기본값: 1)
            limit: 페이지당 항목 수 (기본값: 100)
            search_text: 검색 텍스트 (회원명 또는 이메일)

        Returns:
            (회원 목록, 페이지네이션 정보)
            - 회원 목록: 회원 데이터 배열
            - 페이지네이션 정보: {totalCount, totalPage, page, count}

        Raises:
            MakeshopAPIError: API 오류 발생 시

        Example:
            >>> members, pagination = client.get_members(page=1, limit=5000)
            >>> for member in members:
            ...     print(member['name'], member['email'])
            >>> print(f"Total: {pagination['totalCount']}, Pages: {pagination['totalPage']}")
        """
        params: Dict[str, Any] = {
            "page": page,
            "limit": limit,
            "mode": "search",
            "type": "user"
        }

        if search_text:
            params["search_text"] = search_text

        endpoint = "/list/open_api.html"

        try:
            response = self._request("GET", endpoint, params=params)
            
            # return_code 검증 (0000이면 정상, 아니면 에러)
            return_code = response.get("return_code", "9999")
            if return_code != "0000":
                error_message = MAKESHOP_ERROR_CODES.get(return_code, "알 수 없는 오류")
                print(f"[회원 조회 오류] return_code={return_code}, message={error_message}")
                raise MakeshopAPIError(return_code, error_message)
            
            # API 응답 구조 (메이크샵 공식 가이드)
            # {
            #   "return_code": "0000",
            #   "totalCount": "5000",
            #   "totalPage": 1,
            #   "page": 1,
            #   "count": 100,
            #   "list": [{...}, {...}, ...]
            # }
            
            # 회원 데이터 추출
            members = response.get("list", [])
            
            # 페이지네이션 정보 추출
            pagination_info = {
                "totalCount": int(response.get("totalCount", "0")),
                "totalPage": int(response.get("totalPage", 1)),
                "page": int(response.get("page", 1)),
                "count": int(response.get("count", 0))
            }
            
            print(f"[회원 조회 성공] 페이지 {pagination_info['page']}: {pagination_info['count']}개 조회")
            print(f"[회원 조회 정보] 총 {pagination_info['totalCount']}개 중 {pagination_info['page']}/{pagination_info['totalPage']} 페이지")
            
            return members, pagination_info

        except MakeshopAPIError:
            # MakeshopAPIError는 그대로 전파
            raise
        except Exception as e:
            print(f"[회원 조회 실패] {str(e)}")
            raise

    def get_member(self, member_id: str) -> Dict[str, Any]:
        """
        특정 회원 정보를 조회합니다.

        Args:
            member_id: Makeshop 회원 ID

        Returns:
            회원 정보

        Example:
            >>> member = client.get_member("MEMBER123456")
            >>> print(member['name'], member['email'])
        """
        endpoint = "/list/open_api.html"
        params = {
            "mode": "search",
            "type": "user",
            "member_id": member_id
        }

        try:
            response = self._request("GET", endpoint, params=params)
            member = response.get("data", response.get("member", {}))
            print(f"[회원 상세조회] {member.get('name')}")
            return member

        except Exception as e:
            print(f"[회원 상세조회 실패] (ID: {member_id}): {str(e)}")
            raise

    # ========================================================================
    # 헬스 체크
    # ========================================================================

    def health_check(self) -> bool:
        """
        Makeshop API 연결 상태를 확인합니다.

        Returns:
            연결 성공 여부

        Example:
            >>> is_healthy = client.health_check()
            >>> if is_healthy:
            ...     print("API는 정상입니다")
        """
        try:
            # 간단한 상품 조회로 헬스 체크
            endpoint = "/list/open_api.html"
            params = {
                "mode": "search",
                "type": "product",
                "page": 1,
                "limit": 1
            }
            self._request("GET", endpoint, params=params)
            print("[MakeShop API 헬스 체크] 정상")
            return True

        except Exception as e:
            print(f"[MakeShop API 헬스 체크 실패] {str(e)}")
            return False

    def register_tracking(
        self,
        order_num: str,
        item_nums: List[int],
        delicom: int,
        delinum: str
    ) -> Dict[str, Any]:
        """
        메이크샵에 송장 정보 등록
        
        Args:
            order_num: 주문번호 (예: 20200615094333-59376948941)
            item_nums: 상품 번호 리스트 (예: [1, 2, 3])
            delicom: 배송사 코드 (예: 14=CJ대한통운)
            delinum: 송장번호 (예: 1111)
        
        Returns:
            {
                'success': bool,
                'results': [
                    {
                        'num': 1,
                        'delicom': 14,
                        'delinum': '1111',
                        'ordernum': '20200615094333-59376948941',
                        'result': True/False
                    },
                    ...
                ],
                'error': str (if any)
            }
        """
        try:
            if not self.shop_domain or not self.shop_key or not self.license_key:
                logger.error("[MakeshopService] 메이크샵 설정 누락: domain, shopkey, licensekey")
                return {
                    'success': False,
                    'error': 'Makeshop configuration missing',
                    'results': []
                }

            # 요청 데이터 구성
            request_data: Dict[str, Any] = {}
            for idx, item_num in enumerate(item_nums):
                request_data[f'datas[{idx}][num]'] = item_num
                request_data[f'datas[{idx}][delicom]'] = delicom
                request_data[f'datas[{idx}][delinum]'] = delinum
                request_data[f'datas[{idx}][ordernum]'] = order_num

            # Makeshop API 호출 URL
            url = f"{self.shop_domain}/list/open_api_process.html"
            params = {
                'mode': 'save',
                'type': 'order',
                'process': 'invoice'
            }
            headers = {
                'Shopkey': self.shop_key,
                'Licensekey': self.license_key
            }

            logger.info(f"[MakeshopService] Calling tracking registration: order={order_num}, items={item_nums}, delinum={delinum}")
            

            response = requests.post(
                url,
                params=params,
                data=request_data,
                headers=headers,
                timeout=10
            )

            # Makeshop 응답에서 return_code 추출 및 로그
            return_code = None
            try:
                resp_json = response.json()
                return_code = resp_json.get('return_code')
            except Exception:
                pass
            logger.info(f"[MakeshopService] Response return_code: {return_code}")

            # 응답 처리
            if response.status_code != 200:
                logger.error(f"[MakeshopService] API error: status={response.status_code}, body={response.text[:500]}")
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'results': []
                }

            return_code_key = return_code if isinstance(return_code, str) else None
            return_code_value = return_code_key or str(return_code)
            if return_code_value != "0000":
                message = MAKESHOP_ERROR_CODES.get(return_code_value, f"Unknown return_code {return_code_value}")
                logger.error(f"[MakeshopService] API error: return_code={return_code_value}, message={message}")
                return {
                    'success': False,
                    'error': f'return_code {return_code_value}: {message}',
                    'results': []
                }

            logger.info(f"[MakeshopService] Tracking registration successful for order {order_num}")

            # 결과 데이터 구성
            results: List[Dict[str, Any]] = []
            for idx, item_num in enumerate(item_nums):
                results.append({
                    'num': item_num,
                    'delicom': delicom,
                    'delinum': delinum,
                    'ordernum': order_num,
                    'result': True
                })

            # 배송 처리 자동 호출
            shipping_items: List[Dict[str, Any]] = [
                {'order_num': order_num, 'item_num': res['num']}
                for res in results
            ]
            shipping_result = self.process_shipping(shipping_items)
            if not shipping_result.get('success'):
                logger.warning("[MakeshopService] Shipping processing reported failure")

            response_payload: Dict[str, Any] = {
                'success': True,
                'results': results,
                'shipping': shipping_result,
                'error': None
            }
            if not shipping_result.get('success'):
                response_payload['success'] = False
                response_payload['error'] = shipping_result.get('error')

            return response_payload

        except requests.exceptions.Timeout:
            logger.error(f"[MakeshopService] Timeout: order={order_num}")
            return {
                'success': False,
                'error': 'Request timeout',
                'results': []
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"[MakeshopService] Request error: {str(e)}, order={order_num}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }

    def process_shipping(
        self,
        shipment_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Makeshop에 배송 처리(발송 상태 반영)를 요청합니다.

        Args:
            shipment_items: 배송 처리할 항목 리스트 (각 항목은 order_num과 item_num 필요)

        Returns:
            {
                'success': bool,
                'results': [
                    {
                        'num': 1,
                        'ordernum': '20200615094333-59376948941',
                        'result': True
                    },
                    ...
                ],
                'error': str (if any)
            }
        """
        try:
            if not self.shop_domain or not self.shop_key or not self.license_key:
                logger.error("[MakeshopService] 메이크샵 설정 누락: domain, shopkey, licensekey")
                return {
                    'success': False,
                    'error': 'Makeshop configuration missing',
                    'results': []
                }

            if not shipment_items:
                logger.warning("[MakeshopService] 배송 처리 요청: 항목 없음")
                return {
                    'success': False,
                    'error': 'No shipment items provided',
                    'results': []
                }

            request_data: Dict[str, Any] = {}
            valid_items: List[Dict[str, Any]] = []
            for item in shipment_items:
                order_num_value = item.get('order_num')
                item_num_value = item.get('item_num')
                if not order_num_value or item_num_value is None:
                    logger.warning(f"[MakeshopService] Invalid shipment item skipped: {item}")
                    continue

                idx = len(valid_items)
                request_data[f'datas[{idx}][num]'] = item_num_value
                request_data[f'datas[{idx}][ordernum]'] = order_num_value
                valid_items.append({'order_num': order_num_value, 'num': item_num_value})

            if not valid_items:
                logger.error("[MakeshopService] 배송 처리 요청: 유효한 항목 없음")
                return {
                    'success': False,
                    'error': 'No valid shipment items provided',
                    'results': []
                }

            url = f"{self.shop_domain}/list/open_api_process.html"
            params = {
                'mode': 'save',
                'type': 'order',
                'process': 'delivery'
            }
            headers = {
                'Shopkey': self.shop_key,
                'Licensekey': self.license_key
            }

            logger.info(f"[MakeshopService] Calling shipping process: items={len(valid_items)}")

            response = requests.post(
                url,
                params=params,
                data=request_data,
                headers=headers,
                timeout=10
            )

            return_code = None
            try:
                resp_json = response.json()
                return_code = resp_json.get('return_code')
            except Exception:
                pass
            logger.info(f"[MakeshopService] Response return_code: {return_code}")

            if response.status_code != 200:
                logger.error(f"[MakeshopService] API error: status={response.status_code}, body={response.text[:500]}")
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'results': []
                }

            return_code_key = return_code if isinstance(return_code, str) else None
            return_code_value = return_code_key or str(return_code)
            if return_code_value != "0000":
                message = MAKESHOP_ERROR_CODES.get(return_code_value, f"Unknown return_code {return_code_value}")
                logger.error(f"[MakeshopService] API error: return_code={return_code_value}, message={message}")
                return {
                    'success': False,
                    'error': f'return_code {return_code_value}: {message}',
                    'results': []
                }

            results: List[Dict[str, Any]] = []
            for entry in valid_items:
                results.append({
                    'num': entry['num'],
                    'ordernum': entry['order_num'],
                    'result': True
                })

            return {
                'success': True,
                'results': results,
                'error': None
            }

        except requests.exceptions.Timeout:
            logger.error("[MakeshopService] Timeout during shipping process")
            return {
                'success': False,
                'error': 'Request timeout',
                'results': []
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"[MakeshopService] Request error: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
        except Exception as e:
            logger.error(f"[MakeshopService] Unexpected error: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'results': []
            }

    def batch_register_tracking(
        self,
        tracking_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        여러 주문의 송장 정보를 일괄 등록
        
        Args:
            tracking_data: [
                {
                    'order_num': '20200615094333-59376948941',
                    'item_nums': [1, 2, 3],
                    'delicom': 14,
                    'delinum': '1111'
                },
                ...
            ]
        
        Returns:
            [
                {
                    'order_num': '20200615094333-59376948941',
                    'success': True/False,
                    'results': [...],
                    'error': str (if any)
                },
                ...
            ]
        """
        results: List[Dict[str, Any]] = []
        for data in tracking_data:
            order_num_value = data.get('order_num')
            item_nums_value = data.get('item_nums', [])
            delicom_value = data.get('delicom')
            delinum_value = data.get('delinum')

            result = self.register_tracking(
                order_num=cast(str, order_num_value),
                item_nums=cast(List[int], item_nums_value),
                delicom=cast(int, delicom_value),
                delinum=cast(str, delinum_value)
            )
            result['order_num'] = order_num_value
            results.append(result)

        return results

    def register_tracking_by_order(
        self,
        order_id: int,
        delicom: int,
        delinum: str
    ) -> Dict[str, Any]:
        """
        Order ID를 기반으로 메이크샵에 송장 정보 등록
        
        send_number가 있으면 ordernum으로 사용하고,
        order_items의 num 값을 item_nums로 사용합니다.
        
        Args:
            order_id: Order 테이블의 ID
            delicom: 배송사 코드 (예: 3=CJ대한통운)
            delinum: 송장번호
        
        Returns:
            {
                'success': bool,
                'results': [...],
                'error': str (if any)
            }
        """
        try:
            from app.database import SessionLocal
            from app.models import Order, OrderItem

            db = SessionLocal()
            
            # Order 조회
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                logger.error(f"[register_tracking_by_order] Order not found: id={order_id}")
                db.close()
                return {
                    'success': False,
                    'error': f'Order not found: id={order_id}',
                    'results': []
                }

            # 송장 등록에 사용할 ordernum 추출
            order_num: str = order.ordernum  # type: ignore
            
            # 해당 order의 order_items 조회하여 num 값 추출
            order_items = (
                db.query(OrderItem)
                .filter(OrderItem.ordernum == order.ordernum)
                .filter(OrderItem.basket_status.isnot(None))
                .filter(OrderItem.basket_status.like('D%'))
                .all()
            )
            item_nums: List[int] = []
            for item in order_items:
                item_num_val = getattr(item, 'num', None)
                if item_num_val is not None and str(item_num_val).strip():
                    try:
                        item_nums.append(int(str(item_num_val)))
                    except (ValueError, TypeError):
                        logger.warning(f"[register_tracking_by_order] Invalid item.num: {item_num_val}")
            
            db.close()

            if not item_nums:
                logger.warning(f"[register_tracking_by_order] No items found for order: {order.ordernum}")
                return {
                    'success': False,
                    'error': 'No items found for this order',
                    'results': []
                }

            logger.info(f"[register_tracking_by_order] Order ID: {order_id}, OrderNum: {order_num}, Items: {item_nums}")

            # 송장 등록 수행
            return self.register_tracking(
                order_num=order_num,
                item_nums=item_nums,
                delicom=delicom,
                delinum=delinum
            )

        except Exception as e:
            logger.error(f"[register_tracking_by_order] Error: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'results': []
            }


# Backwards compatibility: older code imports `MakeshopService` from this module.
# The implementation was originally called `MakeshopAPIClient`; expose the
# legacy name as an alias so existing imports continue to work.
MakeshopService = MakeshopAPIClient
