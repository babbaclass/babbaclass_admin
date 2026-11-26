"""
Makeshop Developer Center REST API client.

구 Open API(`makeshop_service.MakeshopAPIClient`)와 별도로 동작합니다.
현재 지원 범위:
  - OAuth 토큰 발급
  - 주문 2.0 조회 (+ legacy adapter)
  - 상품 조회 (+ legacy adapter)
  - 회원 조회 (+ legacy adapter)
  - 송장 등록 / 배송 처리
  - 택배사 목록
"""

from __future__ import annotations

import base64
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import requests

logger = logging.getLogger(__name__)

DEFAULT_REST_BASE_URL = "https://connect.makeshop.co.kr"
TOKEN_PATH = "/oauth/token"
ORDER_V2_PATH_TEMPLATE = "/api/v1/{shop_uid}/order/2"
PRODUCT_PATH_TEMPLATE = "/api/v1/{shop_uid}/product"
USER_PATH_TEMPLATE = "/api/v1/{shop_uid}/user"
ORDER_INVOICE_PATH_TEMPLATE = "/api/v1/{shop_uid}/order/invoice"
ORDER_DELIVERY_PATH_TEMPLATE = "/api/v1/{shop_uid}/order/delivery"
DELIVERY_COMPANY_PATH_TEMPLATE = "/api/v1/{shop_uid}/delivery_company"
INSTALLED_APP_PATH_TEMPLATE = "/api/application/{shop_id}/apps"
TOKEN_REFRESH_BUFFER_SECONDS = 30
# MakeShop: shop_uid+IP 조합당 토큰 요청 분당 최대 5회, 토큰 유효 5분
TOKEN_MAX_ATTEMPTS = 5
TOKEN_RETRY_BASE_SECONDS = 12.0
EMPTY_RESULT_RETURN_CODES = {"9011"}  # 검색된 내역이 없습니다.

# 프로세스 전역 토큰 캐시 (gateway가 요청마다 새 클라이언트를 만들어도 재사용)
# key: (client_id, shop_uid) -> {access_token, expires_at}
_TOKEN_CACHE: Dict[Tuple[str, str], Dict[str, Any]] = {}
_TOKEN_CACHE_LOCK = threading.Lock()
_TOKEN_ISSUE_LOCKS: Dict[Tuple[str, str], threading.Lock] = {}
_TOKEN_ISSUE_LOCKS_GUARD = threading.Lock()


def _token_cache_key(client_id: str, shop_uid: str) -> Tuple[str, str]:
    return (client_id, shop_uid)


def _get_issue_lock(cache_key: Tuple[str, str]) -> threading.Lock:
    with _TOKEN_ISSUE_LOCKS_GUARD:
        lock = _TOKEN_ISSUE_LOCKS.get(cache_key)
        if lock is None:
            lock = threading.Lock()
            _TOKEN_ISSUE_LOCKS[cache_key] = lock
        return lock


def _read_cached_token(cache_key: Tuple[str, str]) -> Optional[Dict[str, Any]]:
    with _TOKEN_CACHE_LOCK:
        entry = _TOKEN_CACHE.get(cache_key)
        if not entry:
            return None
        if time.time() >= float(entry["expires_at"]):
            return None
        return {
            "access_token": str(entry["access_token"]),
            "token_type": entry.get("token_type") or "Bearer",
            "expires_in": max(0, int(float(entry["expires_at"]) - time.time())),
            "cached": True,
        }


def _store_cached_token(
    cache_key: Tuple[str, str],
    *,
    access_token: str,
    token_type: str,
    expires_at: float,
) -> None:
    with _TOKEN_CACHE_LOCK:
        _TOKEN_CACHE[cache_key] = {
            "access_token": access_token,
            "token_type": token_type,
            "expires_at": expires_at,
        }


class MakeshopRestAPIError(Exception):
    """Makeshop REST API 오류"""

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
    ):
        self.code = code
        self.status_code = status_code
        self.payload = payload or {}
        detail = f"[Makeshop REST API Error]"
        if status_code is not None:
            detail += f" HTTP {status_code}"
        if code:
            detail += f" {code}"
        detail += f": {message}"
        super().__init__(detail)


def _is_rate_limit_error(exc: BaseException) -> bool:
    if isinstance(exc, MakeshopRestAPIError):
        if exc.status_code == 429:
            return True
        code = (exc.code or "").lower()
        if "too_many" in code:
            return True
    msg = str(exc).lower()
    return "429" in msg or "too_many" in msg


class MakeshopRestClient:
    """Makeshop Developer Center REST API 클라이언트"""

    def __init__(self, shop_uid: Optional[str] = None, *, require_shop_uid: bool = True) -> None:
        self.client_id = os.getenv("MAKESHOP_CLIENT_ID")
        self.client_secret = os.getenv("MAKESHOP_CLIENT_SECRET")
        self.shop_uid = shop_uid or os.getenv("MAKESHOP_SHOP_UID")
        self.base_url = os.getenv("MAKESHOP_REST_BASE_URL", DEFAULT_REST_BASE_URL).rstrip("/")
        self.timeout = int(os.getenv("MAKESHOP_API_TIMEOUT", "60"))

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Makeshop REST API 인증 정보가 누락되었습니다. "
                "MAKESHOP_CLIENT_ID, MAKESHOP_CLIENT_SECRET를 설정하세요."
            )
        if require_shop_uid and not self.shop_uid:
            raise ValueError(
                "Makeshop REST API shop_uid가 누락되었습니다. "
                "MAKESHOP_SHOP_UID를 설정하거나 shop_uid 인자를 전달하세요."
            )

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._token_shop_uid: Optional[str] = None

    def _basic_auth_header(self) -> str:
        credentials = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        encoded = base64.b64encode(credentials).decode("ascii")
        return f"Basic {encoded}"

    def _parse_json_response(self, response: requests.Response) -> Dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise MakeshopRestAPIError(
                "응답 JSON 파싱에 실패했습니다.",
                status_code=response.status_code,
                payload={"raw": response.text[:500]},
            ) from exc

        if not isinstance(payload, dict):
            raise MakeshopRestAPIError(
                "예상하지 못한 응답 형식입니다.",
                status_code=response.status_code,
                payload={"raw": payload},
            )
        return payload

    def _raise_for_error_payload(
        self,
        payload: Dict[str, Any],
        *,
        status_code: Optional[int] = None,
    ) -> None:
        if payload.get("success") is False:
            raise MakeshopRestAPIError(
                str(payload.get("message") or "API 요청이 실패했습니다."),
                code=str(payload.get("code") or ""),
                status_code=status_code,
                payload=payload,
            )

        if "error" in payload:
            description = payload.get("error_description") or payload.get("error")
            raise MakeshopRestAPIError(
                str(description),
                code=str(payload.get("error")),
                status_code=status_code,
                payload=payload,
            )

        return_code = payload.get("return_code")
        if return_code is not None:
            code = str(return_code)
            if code not in {"0000", "0", "OK", "success"} | EMPTY_RESULT_RETURN_CODES:
                raise MakeshopRestAPIError(
                    str(payload.get("message") or f"return_code={code}"),
                    code=code,
                    status_code=status_code,
                    payload=payload,
                )

        if status_code is not None and status_code >= 400:
            raise MakeshopRestAPIError(
                str(payload.get("message") or "HTTP 요청이 실패했습니다."),
                code=str(payload.get("code") or payload.get("return_code") or ""),
                status_code=status_code,
                payload=payload,
            )

    def _apply_token(
        self,
        *,
        uid: str,
        access_token: str,
        token_type: str,
        expires_at: float,
    ) -> None:
        self._access_token = access_token
        self._token_shop_uid = uid
        self._token_expires_at = expires_at
        _store_cached_token(
            _token_cache_key(str(self.client_id), uid),
            access_token=access_token,
            token_type=token_type,
            expires_at=expires_at,
        )

    def issue_access_token(
        self,
        *,
        shop_uid: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Client Credentials 방식으로 액세스 토큰을 발급합니다.

        MakeShop 제한: shop_uid+IP 당 분당 최대 5회, 토큰 유효 5분.
        인스턴스/프로세스 캐시로 재사용하고, 429는 백오프 재시도합니다.

        Docs: https://developer.makeshop.co.kr/docs/guide/app/access-token
        """
        uid = shop_uid or self.shop_uid
        if not uid:
            raise ValueError("토큰 발급에는 shop_uid가 필요합니다.")

        cache_key = _token_cache_key(str(self.client_id), uid)

        if not force_refresh:
            if (
                self._access_token
                and self._token_shop_uid == uid
                and time.time() < self._token_expires_at
            ):
                return {
                    "access_token": self._access_token,
                    "token_type": "Bearer",
                    "expires_in": max(0, int(self._token_expires_at - time.time())),
                    "cached": True,
                }
            shared = _read_cached_token(cache_key)
            if shared:
                self._access_token = shared["access_token"]
                self._token_shop_uid = uid
                self._token_expires_at = time.time() + shared["expires_in"]
                return shared

        issue_lock = _get_issue_lock(cache_key)
        with issue_lock:
            if not force_refresh:
                shared = _read_cached_token(cache_key)
                if shared:
                    self._access_token = shared["access_token"]
                    self._token_shop_uid = uid
                    self._token_expires_at = time.time() + shared["expires_in"]
                    return shared

            url = f"{self.base_url}{TOKEN_PATH}"
            headers = {
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            }
            data = {
                "grant_type": "client_credentials",
                "shop_uid": uid,
            }

            started = time.time()
            last_error: Optional[BaseException] = None
            response: Optional[requests.Response] = None

            for attempt in range(1, TOKEN_MAX_ATTEMPTS + 1):
                logger.info(
                    "[MakeShop REST] POST %s (shop_uid=%s attempt=%s/%s)",
                    url,
                    uid,
                    attempt,
                    TOKEN_MAX_ATTEMPTS,
                )
                try:
                    response = requests.post(
                        url,
                        headers=headers,
                        data=data,
                        timeout=self.timeout,
                    )
                    payload = self._parse_json_response(response)
                    self._raise_for_error_payload(
                        payload, status_code=response.status_code
                    )

                    token_data = payload.get("data") or {}
                    access_token = token_data.get("access_token")
                    if not access_token:
                        raise MakeshopRestAPIError(
                            "토큰 응답에 access_token이 없습니다.",
                            status_code=response.status_code,
                            payload=payload,
                        )

                    expires_in = int(token_data.get("expires_in") or 300)
                    expires_at = time.time() + max(
                        0, expires_in - TOKEN_REFRESH_BUFFER_SECONDS
                    )
                    token_type = str(token_data.get("token_type") or "Bearer")
                    self._apply_token(
                        uid=uid,
                        access_token=str(access_token),
                        token_type=token_type,
                        expires_at=expires_at,
                    )

                    self._notify_rest(
                        success=True,
                        method="POST",
                        path=TOKEN_PATH,
                        shop_uid=uid,
                        status_code=response.status_code,
                        elapsed_ms=int((time.time() - started) * 1000),
                        extra=f"expires_in={expires_in}s",
                    )

                    logger.info(
                        "[MakeShop REST] access token issued (expires_in=%s)",
                        expires_in,
                    )
                    return {
                        "access_token": self._access_token,
                        "token_type": token_type,
                        "expires_in": expires_in,
                        "cached": False,
                        "raw": payload,
                    }
                except requests.RequestException as exc:
                    last_error = MakeshopRestAPIError(f"토큰 발급 요청 실패: {exc}")
                except MakeshopRestAPIError as exc:
                    last_error = exc

                if last_error is not None and _is_rate_limit_error(last_error):
                    # 발급 경합 중 다른 워커가 캐시한 토큰이 있으면 재사용
                    shared = _read_cached_token(cache_key)
                    if shared and not force_refresh:
                        self._access_token = shared["access_token"]
                        self._token_shop_uid = uid
                        self._token_expires_at = time.time() + shared["expires_in"]
                        logger.warning(
                            "[MakeShop REST] token rate-limited; using shared cache"
                        )
                        return shared
                    if attempt < TOKEN_MAX_ATTEMPTS:
                        wait = TOKEN_RETRY_BASE_SECONDS * attempt
                        logger.warning(
                            "[MakeShop REST] token 429, retry in %.1fs (%s/%s)",
                            wait,
                            attempt,
                            TOKEN_MAX_ATTEMPTS,
                        )
                        time.sleep(wait)
                        continue

                # rate-limit이 아니면 즉시 실패 (재시도 없이 Chat 알림)
                break

            status_code = None
            code = None
            if isinstance(last_error, MakeshopRestAPIError):
                status_code = last_error.status_code
                code = last_error.code
            elif response is not None:
                status_code = response.status_code

            self._notify_rest(
                success=False,
                method="POST",
                path=TOKEN_PATH,
                shop_uid=uid,
                status_code=status_code,
                code=code,
                detail=str(last_error) if last_error else "토큰 발급 실패",
                elapsed_ms=int((time.time() - started) * 1000),
                extra=f"attempts={TOKEN_MAX_ATTEMPTS}",
            )
            if isinstance(last_error, MakeshopRestAPIError):
                raise last_error
            raise MakeshopRestAPIError(
                str(last_error) if last_error else "토큰 발급 실패"
            )

    def _authorized_headers(self, *, shop_uid: Optional[str] = None) -> Dict[str, str]:
        token = self.issue_access_token(shop_uid=shop_uid)
        return {
            "Authorization": f"Bearer {token['access_token']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _notify_rest(
        self,
        *,
        success: bool,
        method: str,
        path: str,
        shop_uid: Optional[str] = None,
        status_code: Optional[int] = None,
        code: Optional[str] = None,
        detail: Optional[str] = None,
        elapsed_ms: Optional[int] = None,
        params: Optional[Dict[str, Any]] = None,
        extra: Optional[str] = None,
    ) -> None:
        from app.services.google_chat import notify_makeshop_rest_call

        notify_makeshop_rest_call(
            success=success,
            method=method,
            path=path,
            shop_uid=shop_uid or self.shop_uid,
            status_code=status_code,
            code=code,
            detail=detail,
            elapsed_ms=elapsed_ms,
            params=params,
            extra=extra,
        )

    @staticmethod
    def _summarize_payload(payload: Dict[str, Any]) -> Optional[str]:
        count = payload.get("count")
        total = payload.get("totalCount", payload.get("total_count"))
        parts = []
        if count is not None:
            parts.append(f"count={count}")
        if total is not None:
            parts.append(f"totalCount={total}")
        list_data = payload.get("list")
        if isinstance(list_data, (list, dict)):
            parts.append(f"list={len(list_data)}")
        return ", ".join(parts) if parts else None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        shop_uid: Optional[str] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        logger.info("[MakeShop REST] %s %s params=%s", method, url, params)
        started = time.time()
        uid = shop_uid or self.shop_uid

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._authorized_headers(shop_uid=shop_uid),
                params=params,
                json=json_data,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            self._notify_rest(
                success=False,
                method=method,
                path=path,
                shop_uid=uid,
                detail=str(exc),
                elapsed_ms=int((time.time() - started) * 1000),
                params=params,
            )
            raise MakeshopRestAPIError(f"API 요청 실패: {exc}") from exc

        try:
            payload = self._parse_json_response(response)
            self._raise_for_error_payload(payload, status_code=response.status_code)
        except MakeshopRestAPIError as exc:
            self._notify_rest(
                success=False,
                method=method,
                path=path,
                shop_uid=uid,
                status_code=exc.status_code or response.status_code,
                code=exc.code,
                detail=str(exc),
                elapsed_ms=int((time.time() - started) * 1000),
                params=params,
            )
            raise

        self._notify_rest(
            success=True,
            method=method,
            path=path,
            shop_uid=uid,
            status_code=response.status_code,
            code=str(payload.get("return_code") or "") or None,
            elapsed_ms=int((time.time() - started) * 1000),
            params=params,
            extra=self._summarize_payload(payload),
        )
        return payload

    def get_installed_app(self, shop_id: Optional[str] = None) -> Dict[str, Any]:
        """
        상점 설치 앱 정보 조회.

        Docs: https://developer.makeshop.co.kr/docs/guide/app/install
        GET /api/application/{shopId}/apps?client_id=...
        """
        uid = shop_id or self.shop_uid
        if not uid:
            raise ValueError("설치 앱 조회에는 shop_id가 필요합니다.")

        path = INSTALLED_APP_PATH_TEMPLATE.format(shop_id=uid)
        payload = self._request(
            "GET",
            path,
            params={"client_id": self.client_id},
            shop_uid=uid,
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise MakeshopRestAPIError(
                "설치 앱 응답에 data가 없습니다.",
                payload=payload,
            )
        return data

    @staticmethod
    def _default_inquiry_window() -> tuple[str, str]:
        """주문 2.0 조회 기본 기간: 어제 00:00:00 ~ 오늘 23:59:59"""
        now = datetime.now()
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=0)
        return (
            start.strftime("%Y-%m-%d %H:%M:%S"),
            end.strftime("%Y-%m-%d %H:%M:%S"),
        )

    @staticmethod
    def _build_order_v2_params(
        *,
        inquiry_time_from: Optional[str],
        inquiry_time_to: Optional[str],
        page: int,
        limit: int,
        fields: Optional[str],
        format: Optional[str],
        extra_params: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "page": page,
            "limit": limit,
        }
        if inquiry_time_from:
            params["InquiryTimeFrom"] = inquiry_time_from
        if inquiry_time_to:
            params["InquiryTimeTo"] = inquiry_time_to
        if fields:
            params["fields"] = fields
        # 기본값 order: 구 Open API와 동일한 주문 단위 list 구조
        if format:
            params["format"] = format
        if extra_params:
            params.update(extra_params)
        return params

    def get_orders_v2(
        self,
        *,
        inquiry_time_from: Optional[str] = None,
        inquiry_time_to: Optional[str] = None,
        page: int = 1,
        limit: int = 100,
        fields: Optional[str] = None,
        format: str = "order",
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        주문 2.0 목록을 조회합니다.

        Docs: https://developer.makeshop.co.kr/docs/api/order/get-order-2

        Args:
            inquiry_time_from: 조회 시작일시 (예: 2025-01-01 00:00:00). 최대 30일 범위.
            inquiry_time_to: 조회 종료일시 (예: 2025-01-31 23:59:59).
            page: 페이지 번호.
            limit: 페이지당 건수 (1000개 초과 비권장).
            fields: 응답 필드 제한 (쉼표 구분).
            format: 출력방식. babba 동기화 호환을 위해 기본값 ``order``.
            extra_params: 문서에 추가된 쿼리 파라미터 전달용.

        Returns:
            REST API 원본 응답(JSON).
        """
        if not inquiry_time_from or not inquiry_time_to:
            default_from, default_to = self._default_inquiry_window()
            inquiry_time_from = inquiry_time_from or default_from
            inquiry_time_to = inquiry_time_to or default_to

        params = self._build_order_v2_params(
            inquiry_time_from=inquiry_time_from,
            inquiry_time_to=inquiry_time_to,
            page=page,
            limit=limit,
            fields=fields,
            format=format,
            extra_params=extra_params,
        )

        path = ORDER_V2_PATH_TEMPLATE.format(shop_uid=self.shop_uid)
        payload = self._request("GET", path, params=params)
        logger.info(
            "[MakeShop REST] order/2 fetched page=%s limit=%s format=%s period=%s~%s",
            page,
            limit,
            format,
            inquiry_time_from,
            inquiry_time_to,
        )
        return payload

    def get_orders_v2_legacy(
        self,
        *,
        inquiry_time_from: Optional[str] = None,
        inquiry_time_to: Optional[str] = None,
        page: int = 1,
        limit: int = 100,
        fields: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        주문 2.0을 조회한 뒤 구 Open API 주문 동기화 payload로 변환합니다.

        Returns:
            ``{"return_code": "0000", "list": {...}, "totalCount": N, ...}``
        """
        from app.services.makeshop_rest_order_adapter import adapt_orders_v2_to_legacy

        payload = self.get_orders_v2(
            inquiry_time_from=inquiry_time_from,
            inquiry_time_to=inquiry_time_to,
            page=page,
            limit=limit,
            fields=fields,
            format="order",
            extra_params=extra_params,
        )
        return adapt_orders_v2_to_legacy(payload)

    def get_products(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        inquiry_time_from: Optional[str] = None,
        inquiry_time_to: Optional[str] = None,
        uid: Optional[str] = None,
        fields: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        상품 목록을 조회합니다.

        Docs: https://developer.makeshop.co.kr/docs/api/product/get-product
        """
        params: Dict[str, Any] = {"page": page, "limit": limit}
        if inquiry_time_from:
            params["InquiryTimeFrom"] = inquiry_time_from
        if inquiry_time_to:
            params["InquiryTimeTo"] = inquiry_time_to
        if uid:
            params["uid"] = uid
        if fields:
            params["fields"] = fields
        if extra_params:
            params.update(extra_params)

        path = PRODUCT_PATH_TEMPLATE.format(shop_uid=self.shop_uid)
        payload = self._request("GET", path, params=params)
        logger.info("[MakeShop REST] product fetched page=%s limit=%s", page, limit)
        return payload

    def get_products_legacy(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        inquiry_time_from: Optional[str] = None,
        inquiry_time_to: Optional[str] = None,
        uid: Optional[str] = None,
        fields: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from app.services.makeshop_rest_product_adapter import adapt_products_to_legacy

        payload = self.get_products(
            page=page,
            limit=limit,
            inquiry_time_from=inquiry_time_from,
            inquiry_time_to=inquiry_time_to,
            uid=uid,
            fields=fields,
            extra_params=extra_params,
        )
        return adapt_products_to_legacy(payload)

    def get_users(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        inquiry_time_from: Optional[str] = None,
        inquiry_time_to: Optional[str] = None,
        userid: Optional[str] = None,
        fields: Optional[str] = None,
        next_userid: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        회원 목록을 조회합니다.

        Docs: https://developer.makeshop.co.kr/docs/api/member/get-user
        """
        params: Dict[str, Any] = {"page": page, "limit": limit}
        if inquiry_time_from:
            params["InquiryTimeFrom"] = inquiry_time_from
        if inquiry_time_to:
            params["InquiryTimeTo"] = inquiry_time_to
        if userid:
            params["userid"] = userid
        if fields:
            params["fields"] = fields
        if next_userid:
            params["next_userid"] = next_userid
        if extra_params:
            params.update(extra_params)

        path = USER_PATH_TEMPLATE.format(shop_uid=self.shop_uid)
        payload = self._request("GET", path, params=params)
        logger.info("[MakeShop REST] user fetched page=%s limit=%s", page, limit)
        return payload

    def get_members_legacy(
        self,
        *,
        page: int = 1,
        limit: int = 100,
        inquiry_time_from: Optional[str] = None,
        inquiry_time_to: Optional[str] = None,
        userid: Optional[str] = None,
        fields: Optional[str] = None,
        next_userid: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from app.services.makeshop_rest_member_adapter import adapt_members_to_legacy

        payload = self.get_users(
            page=page,
            limit=limit,
            inquiry_time_from=inquiry_time_from,
            inquiry_time_to=inquiry_time_to,
            userid=userid,
            fields=fields,
            next_userid=next_userid,
            extra_params=extra_params,
        )
        return adapt_members_to_legacy(payload)

    def get_delivery_companies(self) -> Dict[str, Any]:
        """
        택배사 목록을 조회합니다.

        Docs: https://developer.makeshop.co.kr/docs/api/shop/get-delivery-company
        """
        path = DELIVERY_COMPANY_PATH_TEMPLATE.format(shop_uid=self.shop_uid)
        payload = self._request("GET", path)
        logger.info("[MakeShop REST] delivery_company fetched")
        return payload

    def register_invoice(
        self,
        datas: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        송장번호를 등록합니다.

        Docs: https://developer.makeshop.co.kr/docs/api/order/post-order-invoice

        Args:
            datas: ``[{ordernum, num, delicom, delinum}, ...]``
        """
        body = {"datas": [dict(item) for item in datas]}
        path = ORDER_INVOICE_PATH_TEMPLATE.format(shop_uid=self.shop_uid)
        payload = self._request("POST", path, json_data=body)
        logger.info("[MakeShop REST] order/invoice posted count=%s", len(body["datas"]))
        return payload

    def process_delivery(
        self,
        datas: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        배송 처리(발송)를 요청합니다.

        Docs: https://developer.makeshop.co.kr/docs/api/order/post-order-delivery

        Args:
            datas: ``[{ordernum, num}, ...]``
        """
        body = {"datas": [dict(item) for item in datas]}
        path = ORDER_DELIVERY_PATH_TEMPLATE.format(shop_uid=self.shop_uid)
        payload = self._request("POST", path, json_data=body)
        logger.info("[MakeShop REST] order/delivery posted count=%s", len(body["datas"]))
        return payload

    def register_tracking(
        self,
        *,
        ordernum: str,
        item_nums: Sequence[Union[str, int]],
        delicom: Union[str, int],
        delinum: str,
        auto_process_delivery: bool = True,
    ) -> Dict[str, Any]:
        """
        구 `MakeshopAPIClient.register_tracking`에 대응.
        송장 등록 후 기본적으로 배송 처리까지 호출한다.
        """
        invoice_datas = [
            {
                "ordernum": ordernum,
                "num": str(num),
                "delicom": str(delicom),
                "delinum": delinum,
            }
            for num in item_nums
        ]
        invoice_result = self.register_invoice(invoice_datas)

        results: List[Dict[str, Any]] = []
        for item in invoice_datas:
            results.append(
                {
                    "num": item["num"],
                    "delicom": item["delicom"],
                    "delinum": item["delinum"],
                    "ordernum": ordernum,
                    "result": True,
                }
            )

        response: Dict[str, Any] = {
            "success": True,
            "results": results,
            "invoice": invoice_result,
            "error": None,
        }

        if auto_process_delivery:
            delivery_datas = [
                {"ordernum": ordernum, "num": str(num)} for num in item_nums
            ]
            delivery_result = self.process_delivery(delivery_datas)
            response["shipping"] = delivery_result
            delivery_rows = delivery_result.get("datas") or []
            if isinstance(delivery_rows, list) and any(
                isinstance(row, dict) and row.get("result") is False for row in delivery_rows
            ):
                response["success"] = False
                response["error"] = "delivery processing reported failure"

        return response
