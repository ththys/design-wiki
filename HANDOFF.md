# 디자인 위키 — 인수인계 (다른 LLM·새 세션용)

이 문서만 읽고 이어서 작업할 수 있게 썼습니다. 작성: 2026-11-27, 기준 커밋 `ec0602c` (main, 배포 완료).
그 뒤 바뀐 것은 `git log ec0602c..HEAD`로 보세요.

---

## 1. 한 줄 요약

게임 **전투 기획자(사용자, 관리자)** 와 팀원이 같이 쓰는 **컨플루언스 비슷한 위키**. 빌드 없는 HTML 한 파일 + Firebase(Firestore·Auth) + Cloudinary.

- 사이트: https://ththys.github.io/design-wiki/ (GitHub Pages, `main` 브랜치 루트, `.nojekyll`)
- 저장소: https://github.com/ththys/design-wiki — **공개 저장소**. 이메일·실명·비밀번호를 커밋하지 말 것
- Firebase 프로젝트: `monster-ref` (사용자의 다른 앱 "레퍼런스 아카이브" https://github.com/ththys/monster-ref 와 **같은 프로젝트를 공유**, 컬렉션 이름만 `wiki_` 로 분리)
- Cloudinary: cloud `evqhgyll`, preset `monster_ref` (Unsigned), 위키 업로드는 `wiki` 폴더

## 2. 사용자와 소통하는 방식

- 한국어, 짧은 반말 요청("해줘", "이거 왜 이래")이 많음. 답은 **쉬운 한국어, 기술 용어 없이**.
- 콘솔 작업처럼 사용자가 직접 해야 하는 일은 **붙여 넣을 내용을 통째로** 준다. 사용자가 "나 못 넣겠다, 통째로 줘"라고 한 적 있음 → 일부만 끼워 넣으라고 하지 말 것.
- 바뀐 점을 알릴 때 **Ctrl+Shift+R(강력 새로고침)** 안내.

## 3. 실행·테스트·배포

| 할 일 | 명령 |
|---|---|
| 로컬로 보기 | `python3 -m http.server` 후 `http://localhost:8000/index.html?local` (`?local` = 클라우드 없이 이 브라우저에만 저장) |
| 문법 확인 | `node -e "const s=require('fs').readFileSync('index.html','utf8');[...s.matchAll(/<script>([\s\S]*?)<\/script>/g)].forEach(x=>new Function(x[1]));console.log('ok')"` |
| 스모크 테스트 | `python3 tests/smoke_test.py` (Playwright + Chromium 필요, 47개 항목, 로컬 모드. 마지막 줄 `OK`) |
| 배포 | `git push` → GitHub Pages가 자동 배포. 확인: `gh api "repos/ththys/design-wiki/actions/runs?per_page=1" --jq '.workflow_runs[0]\|.head_sha+" "+.status+" "+(.conclusion//"")'` |

- 커밋 메시지: 한국어 한 줄로 무엇이 바뀌었는지.
- 환경 변수 없음. 설정은 `config.js` (`window.WIKI_CONFIG`).

## 4. 파일 구조

| 파일 | 내용 |
|---|---|
| `index.html` | 앱 전체 (약 1,200줄, CSS+JS 한 파일). 외부 로드: Google Fonts, Firebase compat SDK 10.12.2(gstatic) |
| `config.js` | `spaceName`, `firebase`(웹 설정, 공개돼도 되는 값), `cloudinary[]`(새 업로드는 마지막 계정), `notify.emailjs`(비어 있음 — 안 씀) |
| `firestore.rules.wiki.txt` | 위키 부분 규칙 **견본** (관리자 이메일은 `me@example.com` 자리표시자). 실제 규칙은 Firebase 콘솔에 있음 |
| `tests/smoke_test.py` | Playwright 스모크 테스트 |
| `README.md` | 짧은 소개 |

## 5. 동작 구조

### 저장 모드
- `config.js`에 Firebase가 있고 주소에 `?local`이 없으면 **클라우드**, 아니면 **로컬**(localStorage `wiki-v1` = `{pages, history, comments}`).
- 코드의 `store` 객체가 두 모드를 같은 모양으로 감쌈 (`savePage`, `batchPages`, `deletePages`, `addHistory`, `history`, `comments`, `addComment`, `delComment`). 클라우드에서 페이지는 `onSnapshot`으로 **전부** 받아 `pages` 배열에 둠.

### 로그인·권한 (클라우드)
- 로그인 안 함 → 로그인 화면(`showGate`). 탭 2개: **로그인**(구글 / 이메일·비밀번호), **가입 요청**(이름·이메일·비밀번호로 계정 만들기, 또는 구글 계정으로 요청).
- 로그인했는데 `wiki_pages` 읽기가 권한 오류 → **승인 대기 화면**(`showPending`). 요청이 없으면 "가입 요청 보내기" 버튼.
- **관리자**: Firestore 규칙의 `isAdmin()` 이메일 목록(콘솔에만 있음, 사용자의 구글 계정 하나). 관리자는 가입 없이 바로 들어옴.
- **팀원**: 관리자가 위키 **팀원 관리** 화면(`#/members`)에서 **승인** → `wiki_members/{소문자 이메일}` 문서 생성 → 규칙 `isWikiTeam()`이 통과.
- 관리자인지는 앱이 `wiki_requests`를 구독해 보고 판단(읽히면 관리자) → 왼쪽 메뉴에 "팀원 관리"와 빨간 요청 개수 표시.
- **가입 요청은 하루 3개까지**(`DAY_MAX`): `wiki_meta/signup {day, count}`를 트랜잭션으로 올림. 넘으면 만든 계정을 지우고 "오늘 가입 요청이 가득 찼어요" 표시.
- **가입 막기**: 팀원 관리 맨 위 토글 → `wiki_meta/settings {signupClosed}`. 막혀 있으면 가입 탭에 안내만 보이고, 규칙(`wikiSignupOpen()`)도 요청 생성을 거절.
- 이메일 인증 단계 **없음**(관리자 승인만으로 충분하다고 사용자가 정함). 관리자 알림 메일 **없음**.

### Firestore 데이터 (모두 `monster-ref` 프로젝트)
| 위치 | 필드 |
|---|---|
| `wiki_pages/{id}` | `title, html(정리된 HTML), text(검색용 글자, 2만 자까지), parent(id\|null), order(숫자), links[](본문 속 [[링크]] 페이지 id), createdAt, createdBy{email,name}, updatedAt, updatedBy{email,name}, version`, trashedAt·trashedBy·trashGroup(휴지통, 없으면 null)` |
| `wiki_history/{자동}` | `pageId, title, html, version, at, by` — 저장할 때마다 **이전** 내용을 남김 |
| `wiki_comments/{자동}` | `pageId, html(서식 댓글, 없으면 옛 댓글이라 text만), text(글자), at, by{email,name}, parent(답글이면 원 댓글 id), editedAt, re{"👍":[{e,n}]}(반응)` |
| `wiki_notes/{자동}` | 알림: `to(소문자 이메일), from{email,name}, kind(mc 댓글 멘션·mp 페이지 멘션·rp 답글·cm 내 페이지에 댓글), pageId, cid, title, text, at, read`. 읽은 지 30일 지나면 받는 사람 화면이 지움 |
| `wiki_meta/people` | `{소문자 이메일: {name, at}}` — 로그인할 때 자기 이름을 올림. @멘션 사람 목록 |
| `wiki_members/{email}` | `name, at, by` (승인된 팀원) |
| `wiki_requests/{uid}` | `email, name, at, verified(지금은 안 씀), provider` |
| `wiki_meta/signup` | `day("YYYY-MM-DD"), count` |
| `wiki_meta/settings` | `signupClosed, glossary(용어 설명집 페이지 id), at, by` — 관리자만 씀, 누구나 읽음 |

- 히스토리·댓글은 `where("pageId","==",id)`만 쓰고 정렬은 브라우저에서 함 → **복합 색인 필요 없음**. `orderBy`를 추가하면 색인을 만들어야 하니 주의.

### 브라우저 저장 키
`wiki-v1`(로컬 모드 데이터), `wiki-open`(트리에서 펼친 페이지), `wiki-theme`(테마: auto·light·paper·mint·dark·night·forest·grape — `html[data-theme]`, 어두운 계열은 `html[data-tone="dark"]`. 어두운 테마 전용 CSS는 data-tone으로 쓸 것), `wiki-width`(본문 너비 n 800·w 1200·x 1600·f 전체, 예전 `wiki-full`도 읽음), `wiki-sidew`(왼쪽 메뉴 너비, 끌어서 조절), `wiki-draft:<페이지id>`(편집 임시 저장), `wiki-side`(왼쪽 메뉴 접힘)

### 본문 HTML
- 저장·보기·붙여 넣기 모두 `sanitize()`를 거침. 허용 태그: `P H1~H6 B I U S SUB SUP MARK A UL OL LI BLOCKQUOTE PRE CODE HR BR TABLE THEAD TBODY TR TH TD FIGURE FIGCAPTION IMG VIDEO DIV` + `TIME.date`, `SPAN.status`. 글 속 `\u200b`(커서 빼기용)는 저장할 때 지움.
- 특별한 모양: 패널 `div.panel.(info|note|warn|ok|err)`, 할 일 `ul.check > li(.done)`, 페이지 링크 `a.plink[data-page=id]`, 그림 크기 `figure.w-s|w-m`. 이미지·영상 주소는 `https://` 또는 `data:image/`만.
- **용어 설명집**: 상단 `📖 용어` → 오른쪽 옆 패널(`#gloss`, 넓은 화면이면 본문을 밀어서 나란히, 왼쪽 경계 끌어 너비 조절 `wiki-glossw`). 찾기(Enter 다음), ↗ 새 창, ⇱ 이동. 어떤 페이지를 쓸지는 관리자가 페이지 ⋯ 메뉴 ‘용어 설명집으로 지정’ (로컬 모드는 `wiki-glossary`).
- **목록·들여쓰기 키** (`listKeys()`, 페이지·댓글 공용): Tab=목록 항목 한 칸 들여쓰기(앞 항목 아래 하위 목록) / 보통 줄 `in-1~6` / 표 다음 칸(끝이면 줄 추가), Shift+Tab=반대(빈 항목은 그 항목만 지움), 첫 항목 맨 앞 Backspace=번호·글머리 없애기(`liftLi`), 빈 항목 Enter=내어쓰기·목록 끝내기.
- **되돌리기**: 브라우저 기본 되돌리기를 안 씀. 편집기(페이지·댓글 상자)마다 `ed.__u` 기록, `snapNow()`=바꾸기 직전 상태 저장, `doUndo()`. 글자 입력은 `beforeinput`에서 0.8초 덩어리로 기록. **DOM을 직접 바꾸는 새 기능을 넣으면 그 앞에 `snapNow()`를 꼭 부를 것**(안 그러면 Ctrl+Z로 안 돌아감). 키: Ctrl+Z·Alt+Z 되돌리기, Ctrl+Y·Ctrl+Shift+Z 다시.
- 도구 막대 메뉴(패널·더 넣기)는 `showMenu`로 여는데, 문서 클릭이 메뉴를 닫으므로 여는 단추는 닫기 예외 목록(`[data-act]`, `[data-r]` 등)에 있어야 함.
- **할 일 기한**: `ul.check>li` 안의 `time.date`는 `markDue()`가 지난 날짜=`.late`(빨강), 오늘=`.today`(노랑), 끝낸 일=`.doneD`(회색 줄)로 칠함(저장 안 되는 보기용 클래스). 줄 **중간**에서 `[] ` 쳐도 그 줄 전체가 할 일이 됨(`blockAuto`).
- **댓글**: `richBox()` = 서식 댓글 상자(페이지 편집기와 같은 빠른 입력 `richInput()`, 위쪽 작은 도구 막대). 포커스하면 전역 `ed`를 그 상자로 바꿔서 공용 함수(날짜·멘션·선택기)를 그대로 씀(페이지 편집 중이 아닐 때만). 답글 한 단계, 편집(본인), 반응 6개, 할 일 체크는 보기에서 바로 저장, 댓글 링크. @멘션 = `span.mention[data-email]`, 사람 목록은 `people()`. 상단 🔔 = `wiki_notes` 실시간 구독.
- **차트 블록** (본문에 JSON을 속성으로 저장, 보기 때 그림):
  - 플로우차트 `div.flow[data-flow]` = `{dir:"h"|"v", title, lanes[], nodes:[{id,t,s(모양 proc|start|dec|io|sub|doc|note),sub,d,note,tags[],c(색),lp(페이지id)|lu(주소),col(단계 1~),ord}], edges:[{a,b,l(글자),st:"dash",c}]}`. `cleanFlow()`로 정리, `layoutFlow()`가 자동 배치(가장 긴 경로로 단계, 무게중심으로 줄 순서, 뒤로 가는 선은 DFS로 찾아 아래/오른쪽으로 돌려 그림), `mountFlow()`가 그림(보기: 마우스 오버 설명·눌러서 고정·경로 강조·설명 모두 보기·확대·크게 보기 / 편집: 점 끌어 연결). 편집기 `openFlowEditor()`(Tab 다음 상자, 글로 한꺼번에 넣기 `A -> B : 글자`, `-.->` 점선, `{판단}`, `(시작)`).
  - 간트 `div.gantt[data-gantt]` = `{title, items:[{id,g(구분),n,s,e(YYYY-MM-DD),o(담당),p(진행%),c,ms(마일스톤),note,lp|lu}]}`. `mountGantt()`, 편집기 `openGanttEditor()`(표 입력, 엑셀 붙여 넣기: 구분·이름·시작·끝·담당).
  - 검색 글자(`plainOf`)·링크한 곳(`linksOf`)에 차트 안 글자·링크도 들어감. 편집 창은 `.modal.lock`이라 Esc·바깥 누르기로 안 닫힘.
- 컨플루언스식 요소: 상태 `span.status.(grey|blue|green|yellow|red|purple)`, 날짜 `time.date[datetime=YYYY-MM-DD]`, 결정 `ul.decision>li`, 접기 `div.expand>p.xtitle+div.xbody`(보기에서 `.open` 토글), 단 `div.cols.c2|c3>div.col`, 목차 `div.toc`(빈 상자, 보기 때 `renderExtras()`가 채움), 페이지 불러오기 `div.include[data-page]`(빈 상자, 보기 때 채움, 한 단계만), 정렬 `p/h*.al-c|al-r`. 편집기에서는 `prepEditor()`가 상자들을 `contenteditable=false`로 바꿈.

## 6. 화면 (주소 해시)

| 주소 | 화면 | 사용자가 부르는 이름 |
|---|---|---|
| `#/` | 개요: 소개·통계·최근 수정 10개·최상위 페이지 | 홈, 개요 |
| `#/p/<id>` | 페이지 보기: 경로·제목·작성자·본문·하위 페이지·"이 페이지를 링크한 곳"·댓글 | 페이지 |
| `#/p/<id>/c/<댓글id>` | 페이지 보기 + 그 댓글로 이동·반짝 (댓글 링크·알림에서) | 댓글 링크 |
| `#/p/<id>/edit` | 편집 (위쪽 도구 막대, 제목 칸, 본문) | 편집, 글쓰기 |
| `#/new` / `#/new/<부모id>` | 새 페이지 (부모 아래). 상단 **+ 만들기**는 페이지를 열어 둔 상태면 그 페이지의 **하위**로 만듦 | 만들기 |
| `#/recent` | 최근 수정 100개 | 최근 수정 |
| `#/search/<검색어>` | 검색 결과 | 검색 |
| `#/trash` | 휴지통: 지운 페이지(하위 포함 묶음) 보기·되살리기·영구 삭제. 7일 지나면 누가 위키를 열 때 `purgeOld()`가 영구 삭제 | 휴지통 |
| `#/members` | 팀원 관리 (관리자만): 가입 막기 토글, 가입 요청 승인/거절, 팀원 내보내기 | 팀원 관리 |

- 왼쪽 **페이지 트리**: 펼치기/접기, 끌어 놓기(상자 가운데=그 아래로, 위·아래 가장자리=앞뒤 순서, 빈 곳=최상위, 자기 하위로는 막힘, 알림에서 되돌리기), 우클릭·⋯ 메뉴(열기·편집·하위 만들기·복제·링크 복사·위로·아래로·최상위로·삭제).
- **편집기**(`contenteditable`): 컨플루언스와 같은 입력·키 (전체 목록은 `showKeys()` 단축키 창 = `?`, `Ctrl+/`, 상단 ⌨). 줄 맨 앞 `# ~ ###### * - 1. > ``` --- [] <>` + 띄어쓰기, 글 중간 `**굵게** *기울임* ~~취소~~ \`코드\` [제목](주소)`, `//` 날짜, `:` 이모지, `/` 넣기 메뉴(`/expand /status /date /decision /toc /layout /include` 등), `[[` 페이지 링크(우리만). 빠른 서식은 **keydown이 아니라 input 이벤트**에서 처리(한글 입력기 때문) — `blockAuto()`, `inlineAuto()`. 자동 서식 직후 Ctrl+Z는 `autoUndo`로 되돌림. 편집 단축키는 `editKeys()`(e.code 기준). 4초마다 임시 저장, Ctrl+S 저장, Ctrl+Enter 게시.
- 전역 단축키(`wireKeys()`): `E` 편집, `/`·Alt+Shift+Z 검색, `C`·Win+Alt+C 새 페이지, `[`·Ctrl+[ 왼쪽 메뉴 접기(`wiki-side`), `?` 단축키 창, Ctrl+Alt+H 홈, Ctrl+Alt+G 최근, Ctrl+Alt+C 댓글, Ctrl+Alt+S 링크 복사, G→R / G→D.
- 보기 화면에서 할 일 체크박스를 누르면 편집 없이 바로 저장.
- 남이 편집 중에 먼저 저장했으면 덮어쓰기 전에 묻기(이전 버전은 기록에 남음).
- 다크/라이트 전환 버튼(상단 오른쪽).

## 7. 사용자가 정한 규칙 (뒤집지 말 것)

1. **주소는 ththys.github.io/design-wiki/** 로 따로 둔다 (아카이브 안 하위 폴더 방식은 거절).
2. **화면 배치는 아틀라시안 컨플루언스와 비슷하게** (상단 바·왼쪽 공간/트리·가운데 본문). 단, 아틀라시안 로고·이름은 쓰지 않는다.
3. **여러 팀원이 같이 쓴다.** 팀원은 **스스로 가입 요청**하고, **관리자가 위키 안에서 승인**한다 (규칙에 이메일을 하나씩 적는 방식에서 바뀜).
4. **관리자 알림 메일은 안 보낸다** — 사용자가 "위키에서 내가 수락 누르는 게 낫다"고 함. EmailJS 코드는 남아 있지만 설정을 비워 둠.
5. **이메일 인증 단계는 없앤다** — 인증 메일이 안 와서 막혔고, 관리자 승인이면 충분하다고 판단.
6. **가입 요청은 하루 3개까지**, 넘으면 "가입 막혔다"고 보여 준다.
7. **관리자가 가입 자체를 막을 수 있는 버튼**을 팀원 관리에 둔다.
8. **데이터는 아카이브와 같은 Firebase·Cloudinary**를 쓰되 컬렉션은 `wiki_`로 분리.
9. 공개 저장소이므로 **관리자 이메일은 저장소에 넣지 않는다** (콘솔 규칙에만).
10. 무료로 운영 (Firebase Spark, Cloudinary Free, GitHub Pages).

## 8. Firestore 규칙 다룰 때 (중요)

- 규칙은 **아카이브와 위키가 한 파일**을 같이 씀. 사용자에게 줄 때는 **아카이브 부분(monsters·portfolio·site)까지 포함한 전체**를 줘야 한다. 위키 부분만 주면 사용자가 합치기 어려워 함.
- 관리자 이메일 목록은 `isAdmin()` 하나로 **아카이브·위키 공통**. 실제 이메일은 사용자가 대화에서 알려 줌 — 저장소엔 적지 말고, 필요하면 사용자에게 다시 물을 것.
- Firestore 규칙에서 `조건 ? a : b` 삼항식을 썼다가 게시가 안 됐을 가능성이 있었음 → `||`, `&&`로만 쓴다.
- 최신 전체 규칙의 위키 부분 = `firestore.rules.wiki.txt`(관리자 이메일만 자리표시자). 아카이브 부분은 아래와 같음:
  ```
  match /monsters/{id}  { allow read, write: if isAdmin(); }
  match /portfolio/{id} { allow read: if resource.data.published == true || isAdmin(); allow write: if isAdmin(); }
  match /site/{id}      { allow read: if true; allow write: if isAdmin(); }
  ```

## 9. 지금 상태와 다음 할 일

- 마지막으로 사용자에게 **새 전체 규칙(가입 막기 + 이메일 인증 제거 반영)** 을 줬고, 게시했다는 답은 아직 못 받음.
- 팀원 "이영호"님의 가입 요청이 팀원 관리에 1건 떠 있음. 사용자가 승인 버튼이 반응 없다고 해서 고쳤고(브라우저 `confirm()` → 화면 안 창), 승인 성공 여부는 확인 못 받음.

**다음 순서**
1. 사용자에게 규칙을 게시했는지, 이영호님 승인·입장이 됐는지 확인.
2. 안 되면: 규칙 화면 캡처를 받아 확인 → 팀원 관리에서 승인 시 뜨는 오류 문구 확인.
3. 그 뒤로는 사용자의 새 요청을 받음.

## 10. 사용자에게 먼저 물어볼 것

- 최신 규칙을 게시했는지 (아니면 승인·가입 막기 모두 안 됨).
- 아카이브에 이메일·비밀번호로 로그인하던 **두 번째 관리자 이메일**이 있는지 — 예전 규칙엔 관리자 이메일이 2개였는데, 지금 준 규칙엔 사용자 구글 계정 1개만 있음. 회사에서 아카이브 로그인이 막혔다면 이게 원인.
- 위키 이름 "디자인 위키"를 그대로 쓸지.

## 11. 검수가 더 필요한 것

**실제 서비스로 확인 안 된 것** (테스트는 전부 로컬 모드)
- [ ] 최신 규칙 게시 후 관리자 바로 입장
- [ ] 가입 요청 → 승인 → 팀원 입장 전체 흐름
- [ ] 하루 3개 제한(`wiki_meta/signup` 트랜잭션)과 넘었을 때 계정 지우기
- [ ] 가입 막기 토글과 막혔을 때 가입 탭 안내
- [ ] 클라우드에서 수정 기록·댓글 불러오기·삭제(본인 댓글만)
- [ ] Cloudinary 이미지·영상 업로드 (위키에서 한 번도 안 해 봄)
- [ ] 회사망에서 이메일 로그인

**알려진 한계·정리하면 좋은 것**
- [ ] 페이지를 영구 삭제해도 그 페이지의 `wiki_history`·`wiki_comments`는 남음(고아 문서). 지우려면 규칙에 history·comments delete 권한을 더해야 해서 보류
- 삭제는 휴지통 방식: `pages`=휴지통 아닌 것만, `allPages`=전부. 화면 코드는 `pages`만 쓰면 됨
- [ ] 페이지 본문을 전부 실시간으로 받음 → 페이지가 수백 개·본문이 크면 느려질 수 있음
- [ ] 수정 기록이 끝없이 쌓임(개수 제한 없음)
- [ ] `wiki_meta/signup` 숫자는 로그인한 누구나 올릴 수 있어, 장난으로 그날 가입을 막을 수 있음
- [ ] 안 쓰는 코드: `notifyAdmin()`과 `config.js`의 `notify.emailjs`(메일 안 쓰기로 함), `wiki_requests.verified` 갱신 코드(인증 단계 없앰), `route()` 안의 빈 `if (editing && !force) {}`
- [ ] 페이지 권한(일부 페이지만 보기 제한), 라벨, 첨부 파일(이미지 외), 템플릿, @멘션은 없음

## 12. 실수했던 곳

- 저장소 생성·Pages 켜기 API는 이 환경에서 막혀 있었음 → 사용자가 직접 만들고 Settings → Pages에서 켬. (사용자가 `settings/page`로 잘못 들어가 404를 본 적 있음 → 정확한 주소 `…/settings/pages`)
- `contenteditable`에서 Enter 후 새 줄이 `<div>`로 생겨 빠른 서식이 안 먹음 → `defaultParagraphSeparator`를 `p`로.
- 브라우저 `confirm()`·`prompt()`가 사용자 브라우저에서 막혀 있음 → 승인 버튼, 편집 중 로고·만들기(이동이 조용히 취소됨), 링크·그림 설명 입력이 안 됐음. 전부 화면 안 창(`askModal()`, `askText()`, `modal()`)으로 바꿈. **`confirm()`·`prompt()`·`alert()`는 절대 쓰지 말 것.**
- 가입 도중 실패하면 Auth 계정만 남는 문제 → 실패 시 `user.delete()`, 다시 시도 가능.
- 처음 가입 흐름 중 일부 경로는 인증 메일을 안 보내 팀원이 막힘 → 인증 단계 자체를 없앰.

## 13. 작업 히스토리 (2026-11-27, 커밋 7개)

1. 첫 버전: 트리·편집기·검색·최근 수정·수정 기록·댓글·페이지 링크 (`63b68ca`)
2. 가입 요청·관리자 승인·하루 3명 제한·EmailJS 알림·팀원 관리 (`81571fd`)
3. 가입 실패 이유 표시, 실패한 계정 지우기 (`2595e13`)
4. 승인·거절·내보내기 확인을 화면 안 창으로 (`2e432b1`)
5. 안내 문구: 메일 대신 위키에서 승인 (`8784245`)
6. 가입 막기/다시 받기 (`602858f`)
7. 이메일 인증 단계 없앰 (`ec0602c`)

---

항목을 끝내면 체크하고, 다 끝나면 이 파일을 지운다. 계속 지킬 내용(1~8절)은 `CLAUDE.md`(또는 그 도구의 규칙 파일)로 옮긴다.
