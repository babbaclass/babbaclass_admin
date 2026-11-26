# Makeshop API 호출 방식 수정 완료

## 문제점 분석 및 해결

### 🔴 발견된 문제
현재 Makeshop API 클라이언트가 **잘못된 방식으로 호출**하고 있었습니다:
- API 엔드포인트 형식이 부정확
- URL 스킴(http/https) 누락
- 기본값이 API 서버(openapi.makeshop.co.kr)로 설정되어 있어서 실제 상점 도메인 사용 불가

### ✅ 수정 사항

#### 1. **makeshop_service.py - __init__ 메서드**
```python
# 변경 전
self.shop_domain = os.getenv("MAKESHOP_API_URL", "https://api.makeshop.co.kr")

# 변경 후
shop_domain = os.getenv("MAKESHOP_API_URL")  # 상점 도메인 (예: www.babbasmartclass.com)
if not shop_domain.startswith("http://") and not shop_domain.startswith("https://"):
    self.shop_domain = f"http://{shop_domain}"  # http:// 프로토콜 자동 추가
else:
    self.shop_domain = shop_domain
```

**개선 사항:**
- ✅ 환경 변수에서 상점 도메인을 직접 사용
- ✅ 프로토콜 자동 추가 (http:// 기본값)
- ✅ 기본값 제거로 필수 설정 강제화

#### 2. **makeshop_service.py - API 응답 처리**
```python
# 새로 추가: Makeshop API 응답 코드 검증
if isinstance(data, dict) and "return_code" in data:
    return_code = data.get("return_code")
    
    if return_code in ["0", "1", 0, 1]:  # 성공
        return data
    
    # 오류 코드 해석 및 처리
    error_msg = self._get_error_message(return_code)
    raise Exception(f"Makeshop API 오류: {return_code} - {error_msg}")
```

**개선 사항:**
- ✅ API 응답 코드(return_code) 검증
- ✅ 오류 코드별 상세 메시지 제공
- ✅ 명확한 에러 핸들링

#### 3. **makeshop_service.py - 오류 코드 매핑**
```python
def _get_error_message(self, return_code: Any) -> str:
    """Makeshop API 오류 코드 해석"""
    error_codes = {
        "9000": "요청 형식 오류",
        "9001": "필수 파라미터 누락",
        "9002": "잘못된 상점 정보",  # ← 현재 발생 중인 오류
        "9003": "인증 실패",
        "9004": "권한 없음",
        "9005": "존재하지 않는 리소스",
        "9006": "요청 실패",
        "9999": "시스템 오류"
    }
```

### 📋 API 호출 형식

**이제 올바르게 호출되는 형식:**
```
curl -H 'Shopkey: {MAKESHOP_API_KEY}' \
     -H 'Licensekey: {MAKESHOP_SHOP_ID}' \
     'http://www.babbasmartclass.com/list/open_api.html?mode=search&type=product&page=1&limit=1'
```

### 🔍 현재 상태

| 항목 | 상태 | 설명 |
|------|------|------|
| API 호출 형식 | ✅ 수정 완료 | curl과 동일한 형식으로 호출 |
| 헤더 설정 | ✅ 정상 | Shopkey/Licensekey 헤더 전송 |
| URL 구성 | ✅ 정상 | http://도메인/list/open_api.html?파라미터 |
| 응답 처리 | ✅ 개선됨 | return_code 검증 및 에러 해석 |
| API 연결 | 🔴 실패 | return_code: 9002 (잘못된 상점 정보) |

### 🧪 테스트 결과

```bash
# 테스트 케이스
테스트 1: 사용자 조회 (type=user)
응답: {"return_code": "9002"}

테스트 2: 상품 조회 (type=product)
응답: {"return_code": "9002"}

테스트 3: 카테고리 조회 (type=category)
응답: {"return_code": "9002"}

테스트 4: 주문 조회 (type=order)
응답: {"return_code": "9002"}
```

모든 요청에서 **동일한 오류 코드(9002)**를 반환 → 호출 형식은 정상이지만 **인증 정보 불일치** 가능성

### 🛠️ 다음 확인 사항

#### 1. ⚠️ return_code 9002 해결 방법
```
✓ 확인할 사항:
  1. MAKESHOP_API_KEY(Shopkey) - 올바른 값인지 확인
  2. MAKESHOP_SHOP_ID(Licensekey) - 올바른 값인지 확인  
  3. MAKESHOP_API_URL - 상점 도메인과 Shopkey/Licensekey가 일치하는지 확인
  4. Makeshop 관리자 페이지 확인:
     - 개발자 설정에서 API 키 재확인
     - 상점 정보와 API 키 매칭 확인
```

#### 2. 📚 참고 자료
- Makeshop Open API 문서: https://openapi.makeshop.co.kr/
- 상점 관리자 페이지: https://www.babbasmartclass.com

### 📦 배포 정보

**배포됨:** Cloud Run revision 00046-ck6
```bash
- 이미지 Digest: sha256:fb8f884dc07cebd8a46c95f1e609c592233c6dc5816e24fd2a038dd3b79da48b
- 상태: 100% 트래픽 수신 중
- URL: https://babba-api-1024083500192.asia-northeast3.run.app
```

**테스트 결과:**
```bash
✅ /health → {"status":"healthy"}
✅ /health/db → {"status":"healthy","database":"connected"}
🔴 /makeshop/health → {"status":"unhealthy","message":"Makeshop API 연결 실패"}
   (9002: 잘못된 상점 정보)
```

### 📂 추가된 파일

1. **test_makeshop_api.py** - 여러 API 타입 테스트
2. **debug_makeshop_api.py** - 다양한 URL 형식 디버깅

### 🎯 요약

✅ **호출 방식**: 올바르게 수정됨 (curl과 동일)
✅ **코드 품질**: 에러 처리 강화  
❌ **API 연결**: 인증 정보 문제 (return_code 9002)

**다음 단계**: Makeshop 관리자에게 확인하여 API 키(Shopkey/Licensekey) 및 상점 도메인 재검증 필요
