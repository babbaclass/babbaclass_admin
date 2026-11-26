"""
Admin panel sidebar customization middleware
SQLAdmin 사이드바에 커스텀 메뉴 항목 추가 및 정산 페이지 통합
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, StreamingResponse, RedirectResponse
from urllib.parse import urlparse, parse_qs
import re
import logging
import sys

logger = logging.getLogger(__name__)
# 전역 로그 레벨을 INFO로 설정 (python-multipart 등의 과도한 DEBUG 로그 방지)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
# 필요한 경우 특정 로거만 DEBUG로 설정
logger.setLevel(logging.DEBUG)


class AdminSidebarMiddleware(BaseHTTPMiddleware):
    """
    SQLAdmin 페이지에 커스텀 사이드바 메뉴 추가
    정산 개요, 소속 원장별 월매출/일별 매출, 정산서, 소속 원장 리스트 링크 주입
    정산 페이지는 SQLAdmin 레이아웃 내에 embedded
    """
    
    async def dispatch(self, request, call_next):
        # role_id=1(본사 관리자)이 /admin/ 또는 /admin 접근 시 회원 관리 페이지로 리다이렉트
        # role_id=2(지사장)이 /admin/ 또는 /admin 접근 시 정산 개요 페이지로 리다이렉트
        if request.url.path in ["/admin/", "/admin"]:
            role_id = request.session.get('role_id', None)
            if role_id == 1:
                logger.info(f"[AdminSidebarMiddleware] role_id=1 detected, redirecting to /admin/user/list")
                return RedirectResponse(url="/admin/user/list", status_code=302)
            elif role_id == 2:
                logger.info(f"[AdminSidebarMiddleware] role_id=2 detected, redirecting to /admin/settlement-overview")
                return RedirectResponse(url="/admin/settlement-overview", status_code=302)
        
        response = await call_next(request)
        
        # SQLAdmin 페이지 처리 (/admin/로 시작)
        is_admin_path = request.url.path.startswith("/admin/")
        
        # 정적 파일은 처리하지 않음 (CSS, JS, 이미지 등)
        if is_admin_path and not request.url.path.endswith((".css", ".js", ".png", ".jpg", ".gif", ".svg", ".woff", ".woff2", ".ttf", ".eot")):
            try:
                logger.info(f"[AdminSidebarMiddleware] Processing admin path: {request.url.path}")
                
                # StreamingResponse 처리: body를 버퍼링하여 읽기
                body = b""
                try:
                    async for chunk in response.body_iterator:
                        body += chunk
                except Exception as e:
                    logger.warning(f"[AdminSidebarMiddleware] Could not read body: {e}")
                    return response
                
                # body가 비어있으면 원본 반환
                if not body:
                    logger.warning("[AdminSidebarMiddleware] Empty body, returning original response")
                    return response
                
                body_str = body.decode("utf-8", errors="ignore")
                logger.info(f"[AdminSidebarMiddleware] Body length: {len(body_str)} bytes, Has </body>: {'</body>' in body_str}")
                
                if "</body>" in body_str:
                    # 세션에서 role_id 가져오기
                    role_id = request.session.get('role_id', None)
                    logger.info(f"[AdminSidebarMiddleware] User role_id: {role_id}, type: {type(role_id)}")
                    
                    # role_id를 JavaScript 변수로 주입
                    role_id_value = role_id if role_id is not None else "null"
                    
                    # 모든 admin 페이지에 JavaScript 주입 (메뉴 동적 추가용)
                    js_code = """
<style>
  #adminLoadingOverlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    display: none;
    justify-content: center;
    align-items: center;
    z-index: 99999;
  }
  
  #adminLoadingOverlay.show {
    display: flex !important;
  }
  
  .admin-spinner {
    border: 4px solid rgba(255, 255, 255, 0.3);
    border-top: 4px solid #fff;
    border-radius: 50%;
    width: 50px;
    height: 50px;
    animation: adminSpin 1s linear infinite;
  }
  
  @keyframes adminSpin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .admin-loading-text {
    color: white;
    margin-left: 20px;
    font-size: 18px;
    font-weight: 500;
  }
</style>

<div id="adminLoadingOverlay">
  <div style="display: flex; align-items: center;">
    <div class="admin-spinner"></div>
    <span class="admin-loading-text">로딩 중...</span>
  </div>
</div>

<script>
  // 로딩 오버레이 관리 (인라인 실행)
  (function() {
    const AdminLoadingMgr = {
      show: function() {
        const overlay = document.getElementById('adminLoadingOverlay');
        if (overlay) {
          overlay.classList.add('show');
          overlay.style.display = 'flex';
        }
      },
      
      hide: function() {
        const overlay = document.getElementById('adminLoadingOverlay');
        if (overlay) {
          overlay.classList.remove('show');
          overlay.style.display = 'none';
        }
      }
    };
    
    // 전역 객체로 노출
    window.AdminLoading = AdminLoadingMgr;
    
    // 모든 링크 클릭 감지
    document.addEventListener('click', function(e) {
      const link = e.target.closest('a');
      if (link && !e.defaultPrevented) {
        const href = link.getAttribute('href') || '';
        if (href && !href.startsWith('http') && !href.startsWith('#') && 
            !href.startsWith('javascript:') && href !== '/admin/logout' &&
            !href.includes('download') && !href.includes('export')) {
          if (!e.ctrlKey && !e.metaKey && !e.shiftKey && link.target !== '_blank') {
            AdminLoadingMgr.show();
          }
        }
      }
    }, true);
    
    // 폼 제출 감지
    document.addEventListener('submit', function(e) {
      const form = e.target;
      if (form && !form.hasAttribute('data-ajax')) {
        const action = form.getAttribute('action') || '';
        if (!action.includes('download') && !action.includes('export')) {
          AdminLoadingMgr.show();
        }
      }
    }, true);
    
    // 페이지 언로드 시 로딩 표시
    window.addEventListener('beforeunload', function() {
      AdminLoadingMgr.show();
    });
    
    // 브라우저 뒤로가기/앞으로가기 시 로딩 숨기기 (bfcache 복원 대응)
    window.addEventListener('pageshow', function(event) {
      // 항상 로딩 숨기기 (persisted 여부와 관계없이)
      AdminLoadingMgr.hide();
    });
    
    // DOMContentLoaded에서도 로딩 숨기기 (안전장치)
    document.addEventListener('DOMContentLoaded', function() {
      AdminLoadingMgr.hide();
    });
  })();
  
  // Settlement, Commission, Data Tools 메뉴 추가 (동적)
  // DISABLED: Custom menu injection - use sqladmin's default menu instead
  // sqladmin의 기본 메뉴로 자동 등록되므로 custom menu 주입 불필요
  /*
  const userRoleId = """ + str(role_id_value) + """;
  
  document.addEventListener('DOMContentLoaded', function() {
    console.log('[AdminSidebar] DOMContentLoaded fired');
    console.log('[AdminSidebar] userRoleId:', userRoleId, 'type:', typeof userRoleId);
    
    const navFlex = document.querySelector('.navbar-nav');
    console.log('[AdminSidebar] .navbar-nav found:', !!navFlex);
    
    const alreadyInjected = document.querySelector('[data-view="settlement-status"]');
    console.log('[AdminSidebar] Already injected:', !!alreadyInjected);
    
    // role_id가 2인 경우에만 커스텀 메뉴 추가
    if (userRoleId === 2 && navFlex && !alreadyInjected) {
  /*
      console.log('[AdminSidebar] Injecting custom menus for role_id=2');
      console.log('[AdminSidebar] navFlex children:', navFlex.children.length);
      
      const customMenuHtml = `
        <li class="nav-item">
          <a class="nav-link" href="#" data-view="settlement-overview">
            <span class="nav-link-icon d-md-none d-lg-inline-block">
              <i class="fa-solid fa-chart-pie"></i>
            </span>
            <span class="nav-link-title">정산 개요</span>
          </a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="#" data-view="settlement-status">
            <span class="nav-link-icon d-md-none d-lg-inline-block">
              <i class="fa-solid fa-chart-line"></i>
            </span>
            <span class="nav-link-title">소속 원장별 월매출</span>
          </a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="#" data-view="settlement-statement">
            <span class="nav-link-icon d-md-none d-lg-inline-block">
              <i class="fa-solid fa-file-invoice-dollar"></i>
            </span>
            <span class="nav-link-title">정산서</span>
          </a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="#" data-view="teachers-list">
            <span class="nav-link-icon d-md-none d-lg-inline-block">
              <i class="fa-solid fa-users"></i>
            </span>
            <span class="nav-link-title">소속 원장 리스트</span>
          </a>
        </li>
      `;
      
      console.log('[AdminSidebar] Inserting menus directly into .navbar-nav');
      navFlex.innerHTML = customMenuHtml;
      console.log('[AdminSidebar] Menus inserted, new children count:', navFlex.children.length);
      
      // 삽입 확인
      const checkInjected = document.querySelector('[data-view="settlement-overview"]');
      console.log('[AdminSidebar] Menu injection verified:', !!checkInjected);
      
      // 새로 추가된 메뉴 링크에 이벤트 리스너 추가
      setupCustomMenuListeners();
      
      // 첫 페이지 로드 시 정산 개요 자동 로드
      // (정산 개요 메뉴에 active 클래스 추가 + 콘텐츠 로드)
      setTimeout(() => {
        // sessionStorage에서 자동 로드할 뷰 확인 (직접 URL 접근 시)
        const autoLoadView = sessionStorage.getItem('autoLoadView');
        if (autoLoadView) {
          console.log('[Admin Init] Auto-loading view from sessionStorage:', autoLoadView);
          sessionStorage.removeItem('autoLoadView'); // 사용 후 삭제
          
          const targetLink = document.querySelector('[data-view="' + autoLoadView + '"]');
          if (targetLink) {
            targetLink.classList.add('active');
            document.querySelectorAll('.navbar-nav .nav-link').forEach(el => {
              if (!el.hasAttribute('data-view')) {
                el.classList.remove('active');
              }
            });
            loadCustomContent(autoLoadView);
          }
          return; // autoLoadView가 있으면 기본 로드 로직 스킵
        }
        
        // localStorage에서 첫 로드 여부 확인
        const isFirstLoad = !localStorage.getItem('admin_loaded');
        console.log('[Admin Init] isFirstLoad:', isFirstLoad);
        
        if (isFirstLoad) {
          // 첫 로드인 경우에만 정산 개요 자동 로드
          localStorage.setItem('admin_loaded', 'true');
          console.log('[Admin Init] Setting admin_loaded flag');
          
          const settlementOverviewLink = document.querySelector('[data-view="settlement-overview"]');
          console.log('[Admin Init] settlementOverviewLink found:', !!settlementOverviewLink);
          
          if (settlementOverviewLink) {
            console.log('[Admin Init] Adding active class to settlement-overview');
            settlementOverviewLink.classList.add('active');
            
            // 현재 활성 메뉴 비활성화
            document.querySelectorAll('.navbar-nav .nav-link').forEach(el => {
              if (!el.hasAttribute('data-view')) {
                el.classList.remove('active');
              }
            });
            
            console.log('[Admin Init] Loading settlement-overview content');
            // 정산 개요 콘텐츠 로드
            loadCustomContent('settlement-overview');
          }
        }
      }, 500);
    }
  });
  
  /*
  function setupCustomMenuListeners() {
    document.querySelectorAll('[data-view]').forEach(link => {
      link.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        // 이전 활성 메뉴에서 active 클래스 제거
        document.querySelectorAll('[data-view]').forEach(el => {
          el.classList.remove('active');
        });
        // SQLAdmin 기본 메뉴에서도 active 제거
        document.querySelectorAll('.navbar-nav .nav-link').forEach(el => {
          if (!el.hasAttribute('data-view')) {
            el.classList.remove('active');
          }
        });
        
        // 현재 링크에 active 클래스 추가
        this.classList.add('active');
        
        const viewName = this.getAttribute('data-view');
        loadCustomContent(viewName);
      });
    });
  }
  
  function loadCustomContent(viewName) {
    window.AdminLoading.show();
    
    const url = '/api/admin/settlement-content/' + viewName;
    fetch(url)
      .then(response => response.json())
      .then(data => {
        if (data.html) {
          const mainContent = document.querySelector('[role="main"]');
          if (mainContent) {
            mainContent.innerHTML = data.html;
            // 동적 콘텐츠 로드 후 필요한 초기화 수행
            if (viewName === 'teachers-list') {
              initTeachersList();
            } else if (viewName === 'settlement-status') {
              initSettlementStatus();
            } else if (viewName === 'settlement-overview') {
              initSettlementOverview();
            }
          } else {
            const wrapper = document.querySelector('.navbar-expand-md ~ div');
            if (wrapper) {
              wrapper.innerHTML = data.html;
              if (viewName === 'teachers-list') {
                initTeachersList();
              } else if (viewName === 'settlement-status') {
                initSettlementStatus();
              } else if (viewName === 'settlement-overview') {
                initSettlementOverview();
              }
            }
          }
          // URL 변경 (History API 사용) - data-tools는 제외 (이미 ToolsAdmin이 처리)
          if (viewName !== 'data-tools') {
            window.history.pushState({ view: viewName }, '', '/admin/' + viewName + '/');
          }
        }
      })
      .catch(error => {
        console.error('Error loading content:', error);
        alert('콘텐츠를 불러오는 중 오류가 발생했습니다.');
      })
      .finally(() => {
        window.AdminLoading.hide();
      });
  }
  */

  // 정산 개요 초기화
  function initSettlementOverview() {
    const filter = document.getElementById('settlementOverviewYearFilter');
    const tbody = document.getElementById('settlementOverviewTableBody');
    
    if (!filter || !tbody) {
      console.error('정산 개요 요소를 찾을 수 없습니다.');
      return;
    }
    
    // 연도 목록 로드
    function loadYearOptions() {
      fetch('/api/admin/settlement/overview-years')
        .then(response => response.json())
        .then(result => {
          if (result.status === 'success' && result.years) {
            filter.innerHTML = result.years.map(year => 
              `<option value="${year}">${year}</option>`
            ).join('');
            // 첫 번째 옵션(전체) 선택 후 데이터 로드
            loadOverviewData(filter.value);
          }
        })
        .catch(error => {
          console.error('연도 목록 로드 오류:', error);
          filter.innerHTML = '<option value="전체">전체</option>';
          loadOverviewData('전체');
        });
    }
    
    // 데이터 로드 함수
    function loadOverviewData(year) {
      // 로딩 표시
      window.AdminLoading.show();
      
      const url = '/api/admin/settlement/overview-data?year=' + encodeURIComponent(year);
      fetch(url)
        .then(response => response.json())
        .then(result => {
          if (result.status === 'success' && result.data) {
            renderOverviewTable(result.data, result.summary);
          } else {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:2rem; color:#999;">데이터를 불러올 수 없습니다.</td></tr>';
          }
        })
        .catch(error => {
          console.error('정산 개요 로드 오류:', error);
          tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:2rem; color:#dc3545;">오류: ' + error.message + '</td></tr>';
        })
        .finally(() => {
          window.AdminLoading.hide();
        });
    }
    
    // 테이블 렌더링 함수
    function renderOverviewTable(data, summary) {
      if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:2rem; color:#999;">데이터가 없습니다.</td></tr>';
        return;
      }
      
      tbody.innerHTML = '';
      
      // 합계 행 추가
      if (summary) {
        const summaryRow = document.createElement('tr');
        summaryRow.style.backgroundColor = '#fffacd';
        summaryRow.style.fontWeight = 'bold';
        summaryRow.style.borderBottom = '1px solid #eee';
        summaryRow.innerHTML = `
          <td style="padding:1rem; border:1px solid #dee2e6;">합계</td>
          <td style="padding:1rem; text-align:right; border:1px solid #dee2e6;">${summary.sell_price_total.toLocaleString()} 원</td>
          <td style="padding:1rem; text-align:right; border:1px solid #dee2e6;">${summary.used_reserve_total.toLocaleString()} 원</td>
          <td style="padding:1rem; text-align:right; border:1px solid #dee2e6;">${summary.actual_payment_total.toLocaleString()} 원</td>
          <td style="padding:1rem; text-align:right; border:1px solid #dee2e6;">${summary.commission_total.toLocaleString()} 원</td>
          <td style="padding:1rem; text-align:right; border:1px solid #dee2e6;">${summary.net_settlement_total.toLocaleString()} 원</td>
        `;
        tbody.appendChild(summaryRow);
      }
      
      // 데이터 행 추가
      data.forEach((row) => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid #eee';
        tr.style.cursor = 'pointer';
        tr.dataset.year = row.settlement_date.split('-')[0];
        tr.dataset.month = row.settlement_date.split('-')[1];
        tr.innerHTML = `
          <td style="padding:1rem; border:1px solid #dee2e6;">${row.settlement_date}</td>
          <td style="padding:1rem; text-align:right; border:1px solid #dee2e6;">${row.sell_price_total.toLocaleString()} 원</td>
          <td style="padding:1rem; text-align:right; border:1px solid #dee2e6;">${row.used_reserve_total.toLocaleString()} 원</td>
          <td style="padding:1rem; text-align:right; border:1px solid #dee2e6;">${row.actual_payment_total.toLocaleString()} 원</td>
          <td style="padding:1rem; text-align:right; border:1px solid #dee2e6;">${row.commission_total.toLocaleString()} 원</td>
          <td style="padding:1rem; text-align:right; border:1px solid #dee2e6;">${row.net_settlement_total.toLocaleString()} 원</td>
        `;
        // 행 클릭 시 정산서 상세 페이지로 이동
        tr.addEventListener('click', function() {
          const year = this.dataset.year;
          const month = this.dataset.month;
          window.location.href = '/admin/settlement-statement-detail?year=' + year + '&month=' + parseInt(month, 10);
        });
        // 호버 효과
        tr.addEventListener('mouseenter', function() {
          this.style.backgroundColor = '#f5f5f5';
        });
        tr.addEventListener('mouseleave', function() {
          this.style.backgroundColor = '';
        });
        tbody.appendChild(tr);
      });
    }
    
    // 필터 변경 이벤트
    filter.addEventListener('change', function() {
      loadOverviewData(this.value);
    });
    
    // 초기 로드: 연도 목록 먼저 로드
    loadYearOptions();
  }

  // 정산 현황 초기화
  function initSettlementStatus() {
    const filter = document.getElementById('settlementStatusMonthFilter');
    const tbody = document.getElementById('settlementStatusTableBody');
    
    if (!filter || !tbody) {
      console.error('정산 현황 요소를 찾을 수 없습니다.');
      return;
    }
    
    // 데이터 로드 함수
    function loadStatusData(month) {
      // 로딩 표시
      window.AdminLoading.show();
      
      const url = '/api/admin/settlement/status-data?month=' + encodeURIComponent(month);
      fetch(url)
        .then(response => response.json())
        .then(result => {
          if (result.status === 'success' && result.data) {
            renderStatusTable(result.data, result.summary);
          } else {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:2rem; color:#999;">데이터를 불러올 수 없습니다.</td></tr>';
          }
        })
        .catch(error => {
          console.error('정산 현황 로드 오류:', error);
          tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:2rem; color:#dc3545;">오류: ' + error.message + '</td></tr>';
        })
        .finally(() => {
          window.AdminLoading.hide();
        });
    }
    
    // 테이블 렌더링 함수
    function renderStatusTable(data, summary) {
      if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:2rem; color:#999;">데이터가 없습니다.</td></tr>';
        return;
      }
      
      tbody.innerHTML = '';
      
      // 합계 행 추가
      if (summary) {
        const summaryRow = document.createElement('tr');
        summaryRow.style.backgroundColor = '#fffacd';
        summaryRow.style.fontWeight = 'bold';
        summaryRow.innerHTML = `
          <td style="text-align: center; border: 1px solid #dee2e6;">합계</td>
          <td style="border: 1px solid #dee2e6;"></td>
          <td style="border: 1px solid #dee2e6;"></td>
          <td style="text-align: right; border: 1px solid #dee2e6;">${summary.consumer_price_total.toLocaleString()} 원</td>
          <td style="text-align: right; border: 1px solid #dee2e6;">${summary.sell_price_total.toLocaleString()} 원</td>
          <td style="text-align: right; border: 1px solid #dee2e6;">${summary.delivery_total.toLocaleString()} 원</td>
          <td style="text-align: right; border: 1px solid #dee2e6;">${summary.used_reserve_total.toLocaleString()} 원</td>
          <td style="text-align: right; border: 1px solid #dee2e6;">${summary.actual_payment_total.toLocaleString()} 원</td>
        `;
        tbody.appendChild(summaryRow);
      }
      
      // 데이터 행 추가
      data.forEach((row) => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.style.transition = 'background-color 0.2s';
        tr.dataset.userId = row.user_id;
        tr.innerHTML = `
          <td style="text-align: center; border: 1px solid #dee2e6;">${row.no}</td>
          <td style="border: 1px solid #dee2e6;">${row.name}</td>
          <td style="border: 1px solid #dee2e6;">${row.nickname}</td>
          <td style="text-align: right; border: 1px solid #dee2e6;">${row.consumer_price_total.toLocaleString()} 원</td>
          <td style="text-align: right; border: 1px solid #dee2e6;">${row.sell_price_total.toLocaleString()} 원</td>
          <td style="text-align: right; border: 1px solid #dee2e6;">${row.delivery_total.toLocaleString()} 원</td>
          <td style="text-align: right; border: 1px solid #dee2e6;">${row.used_reserve_total.toLocaleString()} 원</td>
          <td style="text-align: right; border: 1px solid #dee2e6;">${row.actual_payment_total.toLocaleString()} 원</td>
        `;
        
        // 호버 효과
        tr.addEventListener('mouseenter', function() {
          this.style.backgroundColor = '#f0f9ff';
        });
        tr.addEventListener('mouseleave', function() {
          this.style.backgroundColor = '';
        });
        
        // 클릭 이벤트
        tr.addEventListener('click', function() {
          const userId = this.dataset.userId;
          const currentMonth = filter.value;
          showSettlementDetail(userId, currentMonth, row.name);
        });
        
        tbody.appendChild(tr);
      });
    }
    
    // 상세 내역 표시 함수
    function showSettlementDetail(userId, month, userName) {
      window.AdminLoading.show();
      
      const url = `/api/admin/settlement/status-detail/${userId}?month=${encodeURIComponent(month)}`;
      fetch(url)
        .then(response => response.json())
        .then(result => {
          window.AdminLoading.hide();
          
          if (result.status === 'success') {
            renderDetailModal(result.data, userName, month);
          } else {
            alert('상세 내역을 불러오는데 실패했습니다: ' + (result.message || ''));
          }
        })
        .catch(error => {
          window.AdminLoading.hide();
          console.error('Error loading detail:', error);
          alert('상세 내역을 불러오는데 실패했습니다.');
        });
    }
    
    // 상세 내역 모달 렌더링
    function renderDetailModal(data, userName, month) {
      // 기존 모달 제거
      const existingModal = document.getElementById('settlementDetailModal');
      if (existingModal) {
        existingModal.remove();
      }
      
      // 결제종류별 그룹화 및 합계
      const typeGroups = {};
      let grandTotal = 0;
      
      data.forEach(item => {
        const typeName = item.type_name || '기타';
        if (!typeGroups[typeName]) {
          typeGroups[typeName] = {
            items: [],
            total: 0
          };
        }
        typeGroups[typeName].items.push(item);
        typeGroups[typeName].total += item.commission;
        grandTotal += item.commission;
      });
      
      // 테이블 행 생성
      let tableRows = '';
      Object.keys(typeGroups).sort().forEach(typeName => {
        const group = typeGroups[typeName];
        
        group.items.forEach(item => {
          const orderDate = item.order_date;
          const formattedDate = orderDate.length === 8 
            ? `${orderDate.substr(0,4)}-${orderDate.substr(4,2)}-${orderDate.substr(6,2)}`
            : orderDate;
          
          tableRows += `
            <tr>
              <td style="padding:0.5rem; border:1px solid #dee2e6;">${formattedDate}</td>
              <td style="padding:0.5rem; border:1px solid #dee2e6;">${typeName}</td>
              <td style="padding:0.5rem; border:1px solid #dee2e6;">${item.product_name}</td>
              <td style="padding:0.5rem; border:1px solid #dee2e6; text-align:right;">${item.quantity}</td>
              <td style="padding:0.5rem; border:1px solid #dee2e6; text-align:right;">${item.payment_amount.toLocaleString()} 원</td>
              <td style="padding:0.5rem; border:1px solid #dee2e6; text-align:right;">${item.actual_payment.toLocaleString()} 원</td>
              <td style="padding:0.5rem; border:1px solid #dee2e6; text-align:center;">${Math.round(item.rate)}%</td>
              <td style="padding:0.5rem; border:1px solid #dee2e6; text-align:right;">${item.commission.toLocaleString()} 원</td>
            </tr>
          `;
        });
        
        // 소계 행
        tableRows += `
          <tr style="background-color:#fffacd; font-weight:bold;">
            <td colspan="7" style="padding:0.5rem; border:1px solid #dee2e6; text-align:right;">${typeName} 소계</td>
            <td style="padding:0.5rem; border:1px solid #dee2e6; text-align:right;">${group.total.toLocaleString()} 원</td>
          </tr>
        `;
      });
      
      // 총합계 행
      tableRows += `
        <tr style="background-color:#e6f3ff; font-weight:bold;">
          <td colspan="7" style="padding:0.5rem; border:1px solid #dee2e6; text-align:right;">총 합계</td>
          <td style="padding:0.5rem; border:1px solid #dee2e6; text-align:right;">${grandTotal.toLocaleString()} 원</td>
        </tr>
      `;
      
      const modalHtml = `
        <div id="settlementDetailModal" style="position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.5); z-index:9999; display:flex; align-items:center; justify-content:center; padding:2rem;">
          <div style="background:white; border-radius:8px; max-width:1200px; width:100%; max-height:90vh; overflow:auto; box-shadow:0 4px 20px rgba(0,0,0,0.15);">
            <div style="padding:1.5rem; border-bottom:1px solid #dee2e6; display:flex; justify-content:space-between; align-items:center; background:#f8f9fa;">
              <h3 style="margin:0;">${userName} - 정산 상세 내역 ${month === '전체' ? '(전체)' : '(' + month + ')'}</h3>
              <button onclick="document.getElementById('settlementDetailModal').remove()" style="background:none; border:none; font-size:1.5rem; cursor:pointer; padding:0; width:30px; height:30px; display:flex; align-items:center; justify-content:center;">&times;</button>
            </div>
            <div style="padding:1.5rem; overflow:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:0.9rem;">
                <thead style="background:#f8f9fa;">
                  <tr>
                    <th style="padding:0.75rem; border:1px solid #dee2e6;">주문일</th>
                    <th style="padding:0.75rem; border:1px solid #dee2e6;">결제종류</th>
                    <th style="padding:0.75rem; border:1px solid #dee2e6;">상품명</th>
                    <th style="padding:0.75rem; border:1px solid #dee2e6;">수량</th>
                    <th style="padding:0.75rem; border:1px solid #dee2e6;">결제액</th>
                    <th style="padding:0.75rem; border:1px solid #dee2e6;">실결제액</th>
                    <th style="padding:0.75rem; border:1px solid #dee2e6;">수수료율</th>
                    <th style="padding:0.75rem; border:1px solid #dee2e6;">정산액</th>
                  </tr>
                </thead>
                <tbody>
                  ${tableRows}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      `;
      
      document.body.insertAdjacentHTML('beforeend', modalHtml);
      
      // ESC 키로 모달 닫기
      const closeOnEsc = (e) => {
        if (e.key === 'Escape') {
          const modal = document.getElementById('settlementDetailModal');
          if (modal) {
            modal.remove();
            document.removeEventListener('keydown', closeOnEsc);
          }
        }
      };
      document.addEventListener('keydown', closeOnEsc);
      
      // 모달 배경 클릭 시 닫기
      document.getElementById('settlementDetailModal').addEventListener('click', function(e) {
        if (e.target === this) {
          this.remove();
          document.removeEventListener('keydown', closeOnEsc);
        }
      });
    }
    
    // 월 필터 변경 이벤트
    filter.addEventListener('change', function() {
      loadStatusData(this.value);
    });
    
    // 초기 로드 (전체)
    loadStatusData('전체');
  }


  // 소속 원장 리스트 정렬 초기화 (동적으로 로드된 후 호출)
  function initTeachersList() {
    const table = document.getElementById('teachersTable');
    const filter = document.getElementById('teachersSortFilter');
    const tbody = document.getElementById('teachersTableBody');
    if (!table || !filter || !tbody) {
      return;
    }
    let raw = table.getAttribute('data-teachers') || '[]';
    let data;
    try { data = JSON.parse(raw); } catch(e) { data = []; }

    function render(rows) {
      tbody.innerHTML = '';
      rows.forEach((t, idx) => {
        const dDayStyle = t.d_day_color ? `color:${t.d_day_color};` : '';
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="padding:0.7rem; text-align:center; border:1px solid #dee2e6;">${idx+1}</td>
          <td style="padding:0.7rem; border:1px solid #dee2e6; text-align:left;">${t.name}</td>
          <td style="padding:0.7rem; text-align:center; border:1px solid #dee2e6;">${t.purchase_count}</td>
          <td style="padding:0.7rem; text-align:right; border:1px solid #dee2e6;">${t.yearly_payment_display || ''}</td>
          <td style="padding:0.7rem; text-align:center; border:1px solid #dee2e6; font-weight:bold; ${dDayStyle}">${t.d_day}</td>
          <td style="padding:0.7rem; border:1px solid #dee2e6; text-align:left;">${t.join_date}</td>
          <td style="padding:0.7rem; border:1px solid #dee2e6; text-align:left;">${t.contact}</td>`;
        tbody.appendChild(tr);
      });
    }

    function sortAndRender(type) {
      let copy = data.slice();
      if (type === 'name') {
        copy.sort((a,b) => a.name.localeCompare(b.name, 'ko-KR'));
      } else if (type === 'join_date') {
        copy.sort((a,b) => {
          const ad = a.join_date_sort || (a.join_date === '-' ? '0000-00-00' : a.join_date);
          const bd = b.join_date_sort || (b.join_date === '-' ? '0000-00-00' : b.join_date);
          return bd.localeCompare(ad); // 최신 우선
        });
      } else if (type === 'purchase_count') {
        copy.sort((a,b) => b.purchase_count - a.purchase_count);
      } else if (type === 'yearly_payment') {
        copy.sort((a,b) => (b.yearly_payment || 0) - (a.yearly_payment || 0));
      } else if (type === 'd_day') {
        copy.sort((a,b) => (a.d_day_sort ?? 999999) - (b.d_day_sort ?? 999999));
      }
      render(copy);
    }

    filter.addEventListener('change', () => sortAndRender(filter.value));
    // 초기 렌더(서버에서 기본 순서 제공) - 이미 tbody 채워져 있으므로 필요시만 재렌더
  }
  
  // 정산서 전용 함수들 (전역 스코프)
  
  // 정산서 확인 함수 (전역으로 미리 정의)
  window.confirmSettlement = async function() {
    try {
      // 버튼 찾기 (클릭된 버튼 또는 이벤트 타겟에서 찾기)
      const button = event && event.target ? event.target : document.querySelector('.btn-success');
      
      // 버튼 비활성화 및 텍스트 변경
      if (button) {
        button.disabled = true;
        button.textContent = '확인 중...';
      }
      
      // URL에서 year, month 파라미터 추출
      const urlParams = new URLSearchParams(window.location.search);
      const yearParam = urlParams.get('year');
      const monthParam = urlParams.get('month');
      
      console.log('URL params - year:', yearParam, 'month:', monthParam);
      
      if (!yearParam || !monthParam) {
        alert('정산서 년도와 월 정보가 없습니다.');
        if (button) {
          button.disabled = false;
          button.textContent = '정산서를 확인하였습니다.';
        }
        return;
      }
      
      const year = parseInt(yearParam);
      const month = parseInt(monthParam);
      
      console.log('Sending to API - year:', year, 'month:', month);
      
      const response = await fetch('/api/admin/settlement/confirm-statement', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ year, month })
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        const popup = data.popup_message || '정산서 확인이 저장되었습니다.';
        alert(popup);
        
        // 버튼 상태 변경
        if (button) {
          button.textContent = '확인 완료';
          button.classList.remove('btn-success');
          button.classList.add('btn-secondary');
        }
        
        // 페이지 유지 (리다이렉트 하지 않음)
      } else {
        alert('오류: ' + (data.message || '정산서 확인 저장 실패'));
        // 실패 시 버튼 다시 활성화
        if (button) {
          button.disabled = false;
          button.textContent = '정산서를 확인하였습니다.';
        }
      }
    } catch (error) {
      alert('오류 발생: ' + error.message);
      // 에러 시 버튼 다시 활성화
      const button = event && event.target ? event.target : document.querySelector('.btn-success');
      if (button) {
        button.disabled = false;
        button.textContent = '정산서를 확인하였습니다.';
      }
    }
  };
  
  window.loadSettlementDetail = function(year, month) {
    console.log('loadSettlementDetail called with year=' + year + ', month=' + month);
    window.AdminLoading.show();
    
    // URL 업데이트 (브라우저 히스토리에 추가하지 않고 현재 URL만 변경)
    const newUrl = window.location.pathname + '?year=' + year + '&month=' + month;
    window.history.replaceState({year: year, month: month}, '', newUrl);
    console.log('URL updated to:', newUrl);
    
    const url = '/api/admin/settlement-content/settlement-statement-detail?year=' + year + '&month=' + month;
    console.log('Fetching URL:', url);
    fetch(url)
      .then(response => {
        console.log('Response status:', response.status);
        return response.json();
      })
      .then(data => {
        console.log('Data received:', data);
        if (data.html) {
          // page-body, page-wrapper 등 다양한 선택자 시도
          let mainContent = document.querySelector('[role="main"]') || 
                           document.querySelector('.page-body') || 
                           document.querySelector('.page-wrapper') ||
                           document.querySelector('main');
          console.log('Main content element:', mainContent);
          
          if (mainContent) {
            mainContent.innerHTML = data.html;
          } else {
            // 마지막 수단: 첫 번째 .container-xl 찾기
            const container = document.querySelector('.container-xl');
            if (container) {
              container.innerHTML = data.html;
            }
          }
          
          // HTML 삽입 후 확인 상태 조회하여 버튼 비활성화
          setTimeout(async () => {
            try {
              console.log('확인 상태 조회 시작:', year, month);
              const checkResponse = await fetch(`/api/admin/settlement/check-statement-confirmation?year=${year}&month=${month}`);
              const checkData = await checkResponse.json();
              console.log('확인 상태 조회 결과:', checkData);
              
              if (checkData.is_confirmed) {
                const button = document.querySelector('.btn-success');
                console.log('버튼 찾음:', button);
                if (button) {
                  button.disabled = true;
                  button.textContent = '확인 완료';
                  button.classList.remove('btn-success');
                  button.classList.add('btn-secondary');
                  console.log('버튼 비활성화 완료');
                }
              } else if (checkData.is_issued === false) {
                const button = document.querySelector('.btn-success');
                if (button) {
                  button.disabled = true;
                  button.textContent = '발행 후 확인 가능';
                  button.classList.remove('btn-success');
                  button.classList.add('btn-secondary');
                }
              }
            } catch (error) {
              console.error('확인 상태 조회 실패:', error);
            }
          }, 100);
        }
      })
      .catch(error => {
        console.error('Error:', error);
        alert('콘텐츠를 불러오는 중 오류가 발생했습니다: ' + error.message);
      })
      .finally(() => {
        window.AdminLoading.hide();
      });
  };
  
  window.loadSettlementList = function() {
    console.log('loadSettlementList called');
    window.AdminLoading.show();
    const url = '/api/admin/settlement-content/settlement-statement';
    fetch(url)
      .then(response => {
        console.log('Response status:', response.status);
        return response.json();
      })
      .then(data => {
        console.log('Data received:', data);
        if (data.html) {
          let mainContent = document.querySelector('[role="main"]') || 
                           document.querySelector('.page-body') || 
                           document.querySelector('.page-wrapper') ||
                           document.querySelector('main');
          console.log('Main content element:', mainContent);
          
          if (mainContent) {
            mainContent.innerHTML = data.html;
          } else {
            const container = document.querySelector('.container-xl');
            if (container) {
              container.innerHTML = data.html;
            }
          }
        }
      })
      .catch(error => {
        console.error('Error:', error);
        alert('콘텐츠를 불러오는 중 오류가 발생했습니다: ' + error.message);
      })
      .finally(() => {
        window.AdminLoading.hide();
      });
  };
</script>
"""
                    
                    # </body> 태그 직전에 JavaScript 주입
                    body_str = body_str.replace("</body>", js_code + "\n</body>")
                    logger.info("[AdminSidebarMiddleware] JavaScript injected successfully")
                    
                    # 수정된 HTML로 응답 생성
                    # 새로운 깨끗한 헤더 세트 생성 (response.headers 복사 사용 안 함)
                    new_headers = {
                        "content-type": "text/html; charset=utf-8"
                    }
                    
                    # 필요한 다른 헤더만 추가 (캐시, CORS 등)
                    for key in ["cache-control", "x-content-type-options", "x-frame-options"]:
                        if key in response.headers:
                            new_headers[key] = response.headers[key]
                    
                    return Response(
                        content=body_str.encode("utf-8"),
                        status_code=response.status_code,
                        headers=new_headers,
                        media_type="text/html"
                    )
            except Exception as e:
                logger.error(f"[AdminSidebarMiddleware] ERROR: {e}", exc_info=True)
                # 에러 발생 시 원본 응답 반환
                return response
        
        return response
