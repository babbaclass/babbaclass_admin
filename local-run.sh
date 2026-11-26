#!/bin/bash

##############################################################################
# Local Development Build & Run Script for babba-api
#
# 사용법:
#   ./local-run.sh              # 기본 모드: 컨테이너 빌드 및 실행
#   ./local-run.sh --stop       # 실행 중인 컨테이너 중지
#   ./local-run.sh --logs       # 컨테이너 로그 확인
#   ./local-run.sh --shell      # 컨테이너 내 셸 접속
#   ./local-run.sh --clean      # 컨테이너 및 이미지 제거
#
# 요구사항:
#   - Docker 설치 및 실행 중
#   - gcloud CLI 설치 및 인증 완료
#   - 애플리케이션 기본 자격증명(ADC) 준비: `gcloud auth application-default login`
#
##############################################################################

set -e

# 설정 변수
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="babba-local"
IMAGE_NAME="babba-api:local"
PORT="${LOCAL_PORT:-8080}"
TARGET_PORT="${TARGET_PORT:-8080}"

# .env 파일 초기화 (환경 변수 로딩 전에 실행)
if [ ! -f "${SCRIPT_DIR}/.env" ]; then
    if [ -f "${SCRIPT_DIR}/.env.example" ]; then
        cp "${SCRIPT_DIR}/.env.example" "${SCRIPT_DIR}/.env"
        echo "✅ .env 파일이 .env.example 에서 생성되었습니다"
        echo "⚠️  필요한 환경변수를 .env 에서 수정하세요"
    else
        echo "❌ .env.example 파일을 찾을 수 없습니다"
        exit 1
    fi
fi

# 환경 변수 설정 (.env 파일에서 읽기, 없으면 기본값)
# set -a / set +a 방식으로 특수문자(!, # 등)를 안전하게 처리
set -a
source <(grep -v '^#' "${SCRIPT_DIR}/.env" | grep -v '^$')
set +a

# 기본값 설정 (환경변수가 없을 경우만)
export CLOUD_SQL_INSTANCE="${CLOUD_SQL_INSTANCE:-}"
export CLOUD_SQL_HOST="${CLOUD_SQL_HOST:-127.0.0.1}"
export DB_USER="${DB_USER:-root}"
export DB_PASSWORD="${DB_PASSWORD:-}"
export DB_NAME="${DB_NAME:-babba}"
export RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 함수 정의
print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 실행 중인 컨테이너 확인
is_container_running() {
    docker ps --filter "name=${PROJECT_NAME}" --filter "status=running" -q | grep -q . && return 0 || return 1
}

# 컨테이너 중지
stop_container() {
    print_header "컨테이너 중지 중..."
    if is_container_running; then
        docker stop "${PROJECT_NAME}" > /dev/null 2>&1 || true
        print_success "컨테이너 중지 완료: ${PROJECT_NAME}"
    else
        print_warning "실행 중인 컨테이너가 없습니다"
    fi
}

# 기존 컨테이너 제거
remove_container() {
    docker rm "${PROJECT_NAME}" > /dev/null 2>&1 || true
}

# 이미지 빌드
build_image() {
    print_header "Docker 이미지 빌드 중..."
    cd "${SCRIPT_DIR}"
    
    if docker build -t "${IMAGE_NAME}" .; then
        print_success "이미지 빌드 완료: ${IMAGE_NAME}"
    else
        print_error "이미지 빌드 실패"
        exit 1
    fi
}

# 컨테이너 실행
run_container() {
    print_header "컨테이너 시작 중..."
    
    remove_container

    # Build docker run command with --env-file for reliable env passing
    local docker_cmd=(
        "docker" "run" "-d"
        "--name" "${PROJECT_NAME}"
        "--env-file" "${SCRIPT_DIR}/.env"
        "-e" "RUN_MIGRATIONS=${RUN_MIGRATIONS:-true}"
    )
    
    # Add volume mount if gcloud ADC exists
    if [ -d "${HOME}/.config/gcloud" ]; then
        docker_cmd+=("-v" "${HOME}/.config/gcloud:/root/.config/gcloud:ro")
    fi
    
    # Add port mapping and image name
    docker_cmd+=("-p" "${PORT}:${TARGET_PORT}" "${IMAGE_NAME}")
    
    # Execute docker run command
    "${docker_cmd[@]}"
    
    CONTAINER_ID=$(docker ps --filter "name=${PROJECT_NAME}" -q)
    print_success "컨테이너 시작: ${PROJECT_NAME} (${CONTAINER_ID:0:12})"
    
    # 서비스 초기화 대기 (Cloud SQL Proxy + Uvicorn 시작)
    print_header "서비스 초기화 대기 중... (약 20초)"
    sleep 20
    
    # 헬스 체크
    if check_health; then
        print_success "서비스가 정상 시작되었습니다"
        print_header "🎉 로컬 개발 서버 준비 완료"
        echo ""
        echo "📍 API 엔드포인트:"
        echo -e "   ${GREEN}http://127.0.0.1:${PORT}/${NC}"
        echo ""
        echo "📊 Admin 패널:"
        echo -e "   ${GREEN}http://127.0.0.1:${PORT}/admin/${NC}"
        echo ""
        echo "📚 API 문서 (Swagger):"
        echo -e "   ${GREEN}http://127.0.0.1:${PORT}/docs/${NC}"
        echo ""
        echo "🔍 로그 확인:"
        echo -e "   ${BLUE}./local-run.sh --logs${NC}"
        echo ""
        echo "🛑 중지:"
        echo -e "   ${BLUE}./local-run.sh --stop${NC}"
        echo ""
    else
        print_error "서비스 헬스 체크 실패"
        echo "로그 확인: docker logs ${PROJECT_NAME}"
        exit 1
    fi
}

# 헬스 체크
check_health() {
    local max_attempts=10
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf http://127.0.0.1:${PORT}/ > /dev/null 2>&1; then
            return 0
        fi
        
        attempt=$((attempt + 1))
        if [ $attempt -lt $max_attempts ]; then
            sleep 2
        fi
    done
    
    return 1
}

# 컨테이너 로그 확인
show_logs() {
    print_header "컨테이너 로그"
    docker logs -f "${PROJECT_NAME}"
}

# 컨테이너 셸 접속
shell_into_container() {
    print_header "컨테이너 셸 접속"
    docker exec -it "${PROJECT_NAME}" /bin/bash
}

# 컨테이너 및 이미지 정리
clean_all() {
    print_header "정리 중..."
    
    # 컨테이너 중지 및 제거
    if is_container_running; then
        docker stop "${PROJECT_NAME}" > /dev/null 2>&1 || true
    fi
    docker rm "${PROJECT_NAME}" > /dev/null 2>&1 || true
    print_success "컨테이너 제거 완료"
    
    # 이미지 제거
    docker rmi "${IMAGE_NAME}" > /dev/null 2>&1 || true
    print_success "이미지 제거 완료"
}

# 환경 정보 표시
show_config() {
    print_header "설정 정보"
    echo "프로젝트명:        ${PROJECT_NAME}"
    echo "이미지:            ${IMAGE_NAME}"
    echo "로컬 포트:         ${PORT}"
    echo "타겟 포트:         ${TARGET_PORT}"
    echo ""
    echo "Cloud SQL:"
    echo "  인스턴스:        ${CLOUD_SQL_INSTANCE}"
    echo "  데이터베이스:    ${DB_NAME}"
    echo "  사용자:          ${DB_USER}"
    echo ""
}

# 메인 로직
main() {
    case "${1:-run}" in
        run)
            show_config
            build_image
            run_container
            ;;
        stop)
            stop_container
            ;;
        logs)
            show_logs
            ;;
        shell)
            shell_into_container
            ;;
        clean)
            clean_all
            ;;
        *)
            print_error "알 수 없는 명령어: ${1}"
            echo ""
            echo "사용 가능한 명령어:"
            echo "  run              - 이미지 빌드 및 컨테이너 실행 (기본값)"
            echo "  stop             - 실행 중인 컨테이너 중지"
            echo "  logs             - 컨테이너 로그 실시간 확인"
            echo "  shell            - 컨테이너 셸 접속"
            echo "  clean            - 컨테이너 및 이미지 제거"
            exit 1
            ;;
    esac
}

main "$@"
