콘텐츠로 건너뛰기
채팅 기록




나의 말:
function syncMemberInfoToSalesRaw() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const rawSh = ss.getSheetByName('전체매출_raw');
  const memSh = ss.getSheetByName('회원');
  if (!rawSh || !memSh) throw new Error('시트 이름 확인: 전체매출_raw / 회원');

  const raw = rawSh.getDataRange().getValues();
  const mem = memSh.getDataRange().getValues();
  if (raw.length < 2 || mem.length < 2) return;

  const rh = raw[0];
  const mh = mem[0];

  // ---- 전체매출_raw 헤더 ----
  const rSender = rh.indexOf('sender');
  const rPhone = rh.indexOf('phone');
  const rMemberId = rh.indexOf('member_id');     // ✅ 폴백 매칭용
  const rUser = rh.indexOf('user_name');
  const rRoleName = rh.indexOf('role_name');
  const rCompany = rh.indexOf('company_name');

  // ---- 회원 헤더 ----
  const mName = mh.indexOf('이름');
  const mRepPhone = mh.indexOf('대표 연락처');
  const mLoginId = mh.indexOf('로그인ID');       // ✅ 폴백 매칭용
  const mRole = mh.indexOf('역할명');
  const mCompany = mh.indexOf('회사명');

  // 필수 헤더 체크
  const miss = [];
  if (rSender < 0) miss.push('전체매출_raw: sender');
  if (rPhone < 0) miss.push('전체매출_raw: phone');
  if (rMemberId < 0) miss.push('전체매출_raw: member_id');
  if (rUser < 0) miss.push('전체매출_raw: user_name');
  if (rRoleName < 0) miss.push('전체매출_raw: role_name');
  if (rCompany < 0) miss.push('전체매출_raw: company_name');

  if (mName < 0) miss.push('회원: 이름');
  if (mRepPhone < 0) miss.push('회원: 대표 연락처');
  if (mLoginId < 0) miss.push('회원: 로그인ID');
  if (mRole < 0) miss.push('회원: 역할명');
  if (mCompany < 0) miss.push('회원: 회사명');

  if (miss.length) throw new Error('헤더를 못 찾음:\n- ' + miss.join('\n- '));

  // ---------- 정규화 ----------
  const normName = (v) => String(v ?? '').trim().toLowerCase();
  const normId = (v) => String(v ?? '').trim().toLowerCase();

  /**
   * 전화번호 정규화 + 0 보정
   * - 숫자만 추출
   * - 10자리 + 앞자리가 1이면 → 0 붙여서 11자리
   * - 11자리면 그대로
   * - 그 외는 null
   */
  const normPhone = (v) => {
    const digits = String(v ?? '').replace(/\D/g, '');
    if (digits.length === 11) return digits;
    if (digits.length === 10 && digits.startsWith('1')) return '0' + digits;
    return null;
  };

  const makeNamePhoneKey = (name, phone) => {
    const p = normPhone(phone);
    if (!p) return null;
    const n = normName(name);
    if (!n) return null;
    return ${n}|${p};
  };

  // ---------- 회원 맵 2개 생성 ----------
  // 1) 이름+대표연락처
  const mapByNamePhone = new Map();
  // 2) 로그인ID
  const mapByLoginId = new Map();

  for (let i = 1; i < mem.length; i++) {
    const row = mem[i];

    const namePhoneKey = makeNamePhoneKey(row[mName], row[mRepPhone]);
    if (namePhoneKey) {
      mapByNamePhone.set(namePhoneKey, {
        name: row[mName],
        roleName: row[mRole],
        company: row[mCompany],
      });
    }

    const loginId = normId(row[mLoginId]);
    if (loginId) {
      mapByLoginId.set(loginId, {
        name: row[mName],
        roleName: row[mRole],
        company: row[mCompany],
      });
    }
  }

  // ---------- 업데이트 ----------
  let updated1 = 0;
  let updated2 = 0;

  for (let i = 1; i < raw.length; i++) {
    const row = raw[i];

    // 1차: 이름+전화
    const key1 = makeNamePhoneKey(row[rSender], row[rPhone]);
    let memInfo = key1 ? mapByNamePhone.get(key1) : null;

    // 2차: member_id ↔ 로그인ID
    if (!memInfo) {
      const mid = normId(row[rMemberId]);
      memInfo = mid ? mapByLoginId.get(mid) : null;
      if (memInfo) updated2++;
    } else {
      updated1++;
    }

    if (!memInfo) continue;

    // ✅ 항상 덮어쓰기
    row[rUser] = memInfo.name;
    row[rRoleName] = memInfo.roleName;
    row[rCompany] = memInfo.company;
  }

  rawSh.getRange(1, 1, raw.length, raw[0].length).setValues(raw);
  SpreadsheetApp.getActive().toast(
    완료: 1차(이름+전화) ${updated1}행, 2차(member_id) ${updated2}행,
    '회원 정보 동기화',
    6
  );
}

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('자동화')
    .addItem('회원 → 전체매출_raw 덮어쓰기(전화+ID 폴백)', 'syncMemberInfoToSalesRaw')
    .addToUi();
}

데이터 업데이트를 2차까지 하잖아. 거기서 2차 후에 3차를 추가 해야 할 것 같아 
2차 후에도 company_name 컬럼에 미지정 건만 
회원 시트의 이름과 전체매출_raw 이름을 비교해서 company_name을 추가 해줘


ChatGPT의 말:
좋아. 지금 로직은 (1) 이름+전화 → (2) member_id(=로그인ID) 까지 매칭하고, 매칭되면 user_name/role_name/company_name을 “항상 덮어쓰기” 하고 있지.

너가 원하는 3차는:

2차까지 끝난 뒤에도 company_name이 비어있거나 “미지정”인 행만 대상

그 행에 대해 회원 시트 ‘이름’ ↔ 전체매출_raw ‘sender’(또는 user_name?) 를 비교해서

company_name만 채워넣기

아래처럼 “3차(이름만, company_name 미지정만)” 블록을 추가하면 돼. (기존 스타일 그대로 유지)

변경 포인트 요약
회원 맵에 이름만으로 company를 찾는 맵(mapByName) 추가

업데이트 루프에서 2차까지 실패했거나(혹은 성공했어도) company_name이 미지정이면

sender(우선) → 없으면 user_name 기준으로 이름 매칭해서 company_name만 세팅

수정된 코드 (그대로 교체해도 됨)
function syncMemberInfoToSalesRaw() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const rawSh = ss.getSheetByName('전체매출_raw');
  const memSh = ss.getSheetByName('회원');
  if (!rawSh || !memSh) throw new Error('시트 이름 확인: 전체매출_raw / 회원');

  const raw = rawSh.getDataRange().getValues();
  const mem = memSh.getDataRange().getValues();
  if (raw.length < 2 || mem.length < 2) return;

  const rh = raw[0];
  const mh = mem[0];

  // ---- 전체매출_raw 헤더 ----
  const rSender = rh.indexOf('sender');
  const rPhone = rh.indexOf('phone');
  const rMemberId = rh.indexOf('member_id');     // ✅ 폴백 매칭용
  const rUser = rh.indexOf('user_name');
  const rRoleName = rh.indexOf('role_name');
  const rCompany = rh.indexOf('company_name');

  // ---- 회원 헤더 ----
  const mName = mh.indexOf('이름');
  const mRepPhone = mh.indexOf('대표 연락처');
  const mLoginId = mh.indexOf('로그인ID');       // ✅ 폴백 매칭용
  const mRole = mh.indexOf('역할명');
  const mCompany = mh.indexOf('회사명');

  // 필수 헤더 체크
  const miss = [];
  if (rSender < 0) miss.push('전체매출_raw: sender');
  if (rPhone < 0) miss.push('전체매출_raw: phone');
  if (rMemberId < 0) miss.push('전체매출_raw: member_id');
  if (rUser < 0) miss.push('전체매출_raw: user_name');
  if (rRoleName < 0) miss.push('전체매출_raw: role_name');
  if (rCompany < 0) miss.push('전체매출_raw: company_name');

  if (mName < 0) miss.push('회원: 이름');
  if (mRepPhone < 0) miss.push('회원: 대표 연락처');
  if (mLoginId < 0) miss.push('회원: 로그인ID');
  if (mRole < 0) miss.push('회원: 역할명');
  if (mCompany < 0) miss.push('회원: 회사명');

  if (miss.length) throw new Error('헤더를 못 찾음:\n- ' + miss.join('\n- '));

  // ---------- 정규화 ----------
  const normName = (v) => String(v ?? '').trim().toLowerCase();
  const normId = (v) => String(v ?? '').trim().toLowerCase();

  /**
   * 전화번호 정규화 + 0 보정
   * - 숫자만 추출
   * - 10자리 + 앞자리가 1이면 → 0 붙여서 11자리
   * - 11자리면 그대로
   * - 그 외는 null
   */
  const normPhone = (v) => {
    const digits = String(v ?? '').replace(/\D/g, '');
    if (digits.length === 11) return digits;
    if (digits.length === 10 && digits.startsWith('1')) return '0' + digits;
    return null;
  };

  const makeNamePhoneKey = (name, phone) => {
    const p = normPhone(phone);
    if (!p) return null;
    const n = normName(name);
    if (!n) return null;
    return `${n}|${p}`;
  };

  // ---------- 회원 맵 3개 생성 ----------
  // 1) 이름+대표연락처
  const mapByNamePhone = new Map();
  // 2) 로그인ID
  const mapByLoginId = new Map();
  // 3) 이름만 (company_name 미지정 보정용)
  const mapByName = new Map();

  for (let i = 1; i < mem.length; i++) {
    const row = mem[i];

    const info = {
      name: row[mName],
      roleName: row[mRole],
      company: row[mCompany],
    };

    const namePhoneKey = makeNamePhoneKey(row[mName], row[mRepPhone]);
    if (namePhoneKey) mapByNamePhone.set(namePhoneKey, info);

    const loginId = normId(row[mLoginId]);
    if (loginId) mapByLoginId.set(loginId, info);

    const nameKey = normName(row[mName]);
    if (nameKey) mapByName.set(nameKey, info); // 동명이인 있으면 마지막 값으로 덮임
  }

  // ---------- 업데이트 ----------
  let updated1 = 0;
  let updated2 = 0;
  let updated3 = 0;

  const isUnassignedCompany = (v) => {
    const s = String(v ?? '').trim();
    if (!s) return true;
    // "미지정" / "미 지정" / "미정" 등 변형도 같이 처리
    const n = s.replace(/\s+/g, '');
    return n === '미지정' || n === '미정';
  };

  for (let i = 1; i < raw.length; i++) {
    const row = raw[i];

    // 1차: 이름+전화
    const key1 = makeNamePhoneKey(row[rSender], row[rPhone]);
    let memInfo = key1 ? mapByNamePhone.get(key1) : null;

    // 2차: member_id ↔ 로그인ID
    if (!memInfo) {
      const mid = normId(row[rMemberId]);
      memInfo = mid ? mapByLoginId.get(mid) : null;
      if (memInfo) updated2++;
    } else {
      updated1++;
    }

    // 1~2차 매칭 성공 시: ✅ 항상 덮어쓰기
    if (memInfo) {
      row[rUser] = memInfo.name;
      row[rRoleName] = memInfo.roleName;
      row[rCompany] = memInfo.company;
      continue;
    }

    // 3차: 2차까지 실패 + company_name이 "미지정(또는 빈값)"인 건만 이름으로 회사명 보정
    if (!isUnassignedCompany(row[rCompany])) continue;

    const nameFor3rd = normName(row[rSender]) || normName(row[rUser]);
    if (!nameFor3rd) continue;

    const memInfo3 = mapByName.get(nameFor3rd);
    if (!memInfo3 || !memInfo3.company) continue;

    row[rCompany] = memInfo3.company;
    updated3++;
  }

  rawSh.getRange(1, 1, raw.length, raw[0].length).setValues(raw);
  SpreadsheetApp.getActive().toast(
    `완료: 1차(이름+전화) ${updated1}행, 2차(member_id) ${updated2}행, 3차(이름→회사명) ${updated3}행`,
    '회원 정보 동기화',
    6
  );
}

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('자동화')
    .addItem('회원 → 전체매출_raw 덮어쓰기(전화+ID+이름 회사명 보정)', 'syncMemberInfoToSalesRaw')
    .addToUi();
}
참고(중요)
3차는 동명이인이 있으면 위험해. 지금 구현은 “마지막으로 나온 이름”이 덮어쓰는 구조라서 동명이인이 있으면 회사가 틀릴 수 있어.

동명이인 가능성이 있으면 3차에서 role_name도 같이 비어있을 때만 채운다거나, 회원 시트에 “지점/부서/이메일” 같은 보조키를 추가해서 안전장치를 거는 게 좋아.

원하면 “동명이인 감지(같은 이름이 2개 이상이면 3차에서 스킵하고 로그 남김)” 옵션까지 같이 넣어줄게.




선택된 파일 없음선택된 파일 없음
ChatGPT는 실수를 할 수 있습니다. 중요한 정보는 재차 확인하세요. 쿠키 기본 설정을 참고하세요.
