"""디자인 위키 스모크 테스트 (이 브라우저 저장 모드: 주소 뒤 ?local)
실행: python tests/smoke_test.py
"""
import http.server, threading, functools, os, sys, json, tempfile
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_address[1]}/index.html?local"
fails = []
def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))
    if not ok: fails.append(name)

def type_ko(pg, text):
    pg.keyboard.insert_text(text)

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 900})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL); pg.evaluate("localStorage.clear()"); pg.reload(); pg.wait_for_timeout(300)
    check("처음 화면: 개요·빈 트리", "첫 페이지를 만들어 보세요" in pg.inner_text("#main") and "아직 페이지가 없어요" in pg.inner_text("#tree"))

    # 1) 페이지 만들기 + 서식
    pg.click("#createBtn"); pg.wait_for_timeout(200)
    pg.fill("#edTitle", "전투 기획 개요"); pg.click("#ed")
    type_ko(pg, "## "); pg.keyboard.press("Backspace"); pg.keyboard.type(" "); pg.wait_for_timeout(50)
    pg.evaluate("document.querySelector('#ed').innerHTML='<p><br></p>'")
    pg.click("#ed"); pg.keyboard.type("## "); type_ko(pg, "핵심 규칙"); pg.keyboard.press("Enter")
    type_ko(pg, "공격은 가드로 막는다."); pg.keyboard.press("Enter")
    pg.keyboard.type("[] "); type_ko(pg, "보스 패턴 정리"); pg.keyboard.press("Enter"); type_ko(pg, "밸런스 확인"); pg.keyboard.press("Enter"); pg.keyboard.press("Enter")
    pg.click('[data-act="table"]'); pg.wait_for_timeout(100); type_ko(pg, "이름")
    has_tbl_bar = pg.locator(".tblbar").count() == 1
    pg.click('.tblbar [data-t="ra"]'); pg.wait_for_timeout(50)
    rows = pg.evaluate("document.querySelector('#ed table').rows.length")
    pg.click("#edSave"); pg.wait_for_timeout(300)
    doc = pg.inner_html("#pDoc")
    check("새 페이지 게시: 제목·소제목·할 일·표", "#/p/" in pg.evaluate("location.hash") and ">핵심 규칙</h2>" in doc and 'class="check"' in doc and "<table" in doc and rows == 4 and has_tbl_bar, f"{rows},{has_tbl_bar},{doc[:300]}")
    pid = pg.evaluate("location.hash.split('/')[2]")
    check("트리에 표시", pg.locator(f'.trow[data-row="{pid}"]').count() == 1)

    # 2) 하위 페이지 + [[링크]]
    pg.locator(f'.trow[data-row="{pid}"]').hover(); pg.click(f'[data-tadd="{pid}"]'); pg.wait_for_timeout(200)
    pg.fill("#edTitle", "보스 A"); pg.click("#ed"); type_ko(pg, "참고: "); pg.keyboard.type("[["); pg.wait_for_timeout(100)
    picker = pg.locator("#pick button").count() >= 1
    type_ko(pg, "전투"); pg.wait_for_timeout(100); pg.keyboard.press("Enter"); pg.wait_for_timeout(100)
    link_ok = pg.locator('#ed a.plink[data-page="%s"]' % pid).count() == 1
    pg.click("#edSave"); pg.wait_for_timeout(300)
    cid = pg.evaluate("location.hash.split('/')[2]")
    crumbs = pg.inner_text(".crumbs")
    check("하위 페이지·경로·[[링크]]", picker and link_ok and "전투 기획 개요" in crumbs, f"{picker},{link_ok},{crumbs}")
    pg.click(f'#pDoc a.plink'); pg.wait_for_timeout(300)
    check("링크한 곳 목록", "이 페이지를 링크한 곳" in pg.inner_text("#main") and "보스 A" in pg.inner_text(".blinks:has(h4:text('링크한 곳'))"))
    check("하위 페이지 목록", "보스 A" in pg.inner_text("#main"))

    # 3) 수정 → 기록 → 되돌리기
    pg.click("#pEdit"); pg.wait_for_timeout(200)
    pg.fill("#edTitle", "전투 기획 개요 v2"); pg.click("#edSave"); pg.wait_for_timeout(300)
    check("수정 저장·버전", "버전 2" in pg.inner_text(".byline") and pg.inner_text(".ptitle") == "전투 기획 개요 v2")
    pg.click("#pMore"); pg.locator(".menu button", has_text="수정 기록").click(); pg.wait_for_timeout(300)
    n = pg.locator("#hl button").count()
    pg.locator("#hl button").nth(1).click(); pg.click("#hRestore"); pg.wait_for_timeout(300)
    check("수정 기록·되돌리기", n == 2 and pg.inner_text(".ptitle") == "전투 기획 개요" and "버전 3" in pg.inner_text(".byline"), str(n))

    # 4) 댓글
    pg.click("#cIn"); pg.keyboard.type("좋아요 확인했어요"); pg.click("[data-cadd]"); pg.wait_for_timeout(300)
    check("댓글 등록", "좋아요 확인했어요" in pg.inner_text("#cmtList"))
    pg.click("[data-cdel]"); pg.wait_for_timeout(100); pg.click("#askOk"); pg.wait_for_timeout(300)
    check("댓글 삭제", "좋아요 확인했어요" not in pg.inner_text("#cmtList"))

    # 5) 검색
    pg.fill("#q", "가드"); pg.wait_for_timeout(150)
    sr = pg.inner_text("#sres")
    pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    check("검색(본문 글자)", "전투 기획 개요" in sr and "검색 결과" in pg.inner_text("#main"), sr)

    # 6) 트리 끌어 옮기기: 보스 A를 최상위 뒤로
    pg.goto(URL + "#/"); pg.wait_for_timeout(200)
    pg.locator(f'[data-tw="{pid}"]').click(); pg.wait_for_timeout(100)
    if pg.locator(f'.trow[data-row="{cid}"]').count() == 0: pg.locator(f'[data-tw="{pid}"]').click(); pg.wait_for_timeout(100)
    src = pg.locator(f'.trow[data-row="{cid}"]'); dst = pg.locator(f'.trow[data-row="{pid}"]')
    bb = dst.bounding_box()
    src.drag_to(dst, target_position={"x": 40, "y": bb["height"] - 3}); pg.wait_for_timeout(300)
    par = pg.evaluate(f"(JSON.parse(localStorage.getItem('wiki-v1')).pages.find(p=>p.id==='{cid}')||{{}}).parent")
    check("트리 끌어서 옮기기(최상위로)", par is None, str(par))

    # 7) 임시 저장 + 나가기 확인
    pg.goto(URL + f"#/p/{pid}/edit"); pg.wait_for_timeout(200)
    pg.click("#ed"); pg.keyboard.press("End"); type_ko(pg, "임시 글"); pg.wait_for_timeout(4300)
    draft = pg.evaluate(f"!!localStorage.getItem('wiki-draft:{pid}')")
    check("4초마다 임시 저장", draft)
    pg.click("#edCancel"); pg.wait_for_timeout(200); asked = pg.locator("#askOk").count() == 1
    pg.click("[data-close]"); pg.wait_for_timeout(100)
    check("저장 안 하고 닫으면 묻기 (화면 안 창)", asked and pg.locator("#ed").count() == 1)

    # 8) 패널 · / 명령
    pg.evaluate("document.querySelector('#ed').innerHTML='<ul class=\"check\"><li>할 일</li></ul><p><br></p>'")
    pg.locator("#ed > p").last.click()
    pg.keyboard.type("/"); pg.wait_for_timeout(100); type_ko(pg, "주의"); pg.wait_for_timeout(100)
    slash = pg.locator("#pick button").count() >= 1
    pg.keyboard.press("Enter"); pg.wait_for_timeout(100); type_ko(pg, "조심")
    check("/ 명령으로 주의 패널", slash and pg.locator("#ed .panel.warn").count() == 1 and "조심" in pg.inner_text("#ed .panel.warn"))
    pg.click("#edSave"); pg.wait_for_timeout(300)

    # 9) 이미지 붙여 넣기(로컬: 작은 이미지)
    pg.goto(URL + f"#/p/{cid}/edit"); pg.wait_for_timeout(200); pg.locator("#ed > p").last.click(); pg.keyboard.press("End"); pg.keyboard.press("Enter")
    png = os.path.join(tempfile.mkdtemp(), "a.png")
    import base64; open(png, "wb").write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))
    pg.set_input_files("#edFile", png); pg.wait_for_timeout(300)
    img = pg.locator("#ed figure img").count() == 1
    pg.locator("#ed figure img").click(); pg.wait_for_timeout(100); pg.click('.figbar [data-w="s"]'); pg.wait_for_timeout(50)
    pg.click("#edSave"); pg.wait_for_timeout(300)
    check("이미지 넣기·크기", img and pg.locator("#pDoc figure.w-s img").count() == 1)

    # 10) 보기 화면 체크리스트 누르기 → 저장
    pg.goto(URL + f"#/p/{pid}"); pg.wait_for_timeout(200)
    li = pg.locator("#pDoc ul.check li").first; bb = li.bounding_box()
    pg.mouse.click(bb["x"] + 8, bb["y"] + bb["height"] / 2); pg.wait_for_timeout(300)
    done = pg.evaluate(f"(JSON.parse(localStorage.getItem('wiki-v1')).pages.find(p=>p.id==='{pid}')||{{}}).html.includes('class=\"done\"')")
    check("보기 화면에서 할 일 체크 저장", done)

    # 11) 최근 수정·다크 모드·삭제
    pg.click('[data-nav="recent"]'); pg.wait_for_timeout(200)
    check("최근 수정", pg.locator(".plist a").count() == 2)
    pg.click("#themeBtn"); n_th = pg.locator(".menu.thm [data-th]").count(); pg.click('.menu.thm [data-th="forest"]'); pg.wait_for_timeout(50)
    t1 = pg.evaluate("[document.documentElement.dataset.theme, document.documentElement.dataset.tone, getComputedStyle(document.body).backgroundColor]")
    pg.reload(); pg.wait_for_timeout(300); t2 = pg.evaluate("[document.documentElement.dataset.theme, document.documentElement.dataset.tone]")
    pg.click("#themeBtn"); pg.click('.menu.thm [data-th="paper"]'); t3 = pg.evaluate("document.documentElement.dataset.tone"); pg.click("#themeBtn"); pg.click('.menu.thm [data-th="light"]'); pg.mouse.click(700, 600)
    check("테마 8개 고르기·새로고침해도 유지", n_th == 8 and t1[:2] == ["forest", "dark"] and t1[2] == "rgb(20, 28, 24)" and t2 == ["forest", "dark"] and t3 == "light", f"{n_th},{t1},{t2},{t3}")
    pg.goto(URL + f"#/p/{cid}"); pg.wait_for_timeout(200)
    pg.click("#pMore"); pg.locator(".menu button", has_text="삭제").click(); pg.click("#askOk"); pg.wait_for_timeout(300)
    gone = pg.locator(f'.trow[data-row="{cid}"]').count() == 0
    kept = pg.evaluate(f"!!(JSON.parse(localStorage.getItem('wiki-v1')).pages.find(p=>p.id==='{cid}')||{{}}).trashedAt")
    pg.click('[data-nav="trash"]'); pg.wait_for_timeout(200)
    listed = pg.locator(".trow2", has_text="보스 A").count() == 1 and "7일 뒤 삭제" in pg.inner_text("#main") and pg.inner_text("#nTrash") == "1"
    pg.click(f'[data-tr="{cid}"]'); pg.wait_for_timeout(300)
    back = pg.locator(f'.trow[data-row="{cid}"]').count() == 1 and pg.inner_text("#nTrash") == ""
    check("삭제 → 휴지통 → 되살리기", gone and kept and listed and back, f"{gone},{kept},{listed},{back}")
    pg.goto(URL + f"#/p/{cid}"); pg.wait_for_timeout(200)
    pg.click("#pMore"); pg.locator(".menu button", has_text="삭제").click(); pg.click("#askOk"); pg.wait_for_timeout(200)
    pg.goto(URL + "#/trash"); pg.wait_for_timeout(200); pg.click(f'[data-td="{cid}"]'); pg.click("#askOk"); pg.wait_for_timeout(300)
    check("휴지통에서 영구 삭제", pg.evaluate("JSON.parse(localStorage.getItem('wiki-v1')).pages.length") == 1 and "비어 있어요" in pg.inner_text("#main"))

    # 12) 붙여 넣은 HTML 정리(스크립트 제거)
    clean = pg.evaluate("sanitize('<p onclick=x>a<script>alert(1)</script><img src=x onerror=y><a href=\"javascript:z\">b</a></p>')") if pg.evaluate("typeof sanitize") == "function" else None
    check("HTML 정리", clean is None or ("script" not in clean and "onerror" not in clean and "javascript" not in clean), str(clean))


    # 13) 컨플루언스식 빠른 입력·요소·단축키
    def fresh(title):
        pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.goto(URL + "#/new"); pg.wait_for_timeout(250); pg.fill("#edTitle", title); pg.click("#ed")
    def edh(): return pg.inner_html("#ed")
    def clear_ed(html="<p><br></p>"):
        pg.evaluate("h => { const e = document.querySelector('#ed'); e.innerHTML = h; e.focus(); const r = document.createRange(); r.selectNodeContents(e.querySelector('p') || e); r.collapse(false); getSelection().removeAllRanges(); getSelection().addRange(r); }", html)
    pg.on("dialog", lambda d: d.accept())
    fresh("빠른 입력")
    pg.keyboard.type("# "); r1 = "<h1>" in edh()
    clear_ed(""); pg.keyboard.type("## x"); r_first = "<h2>x</h2>" in edh()
    clear_ed("<p>뒤 글</p>"); pg.keyboard.press("Home"); pg.keyboard.type("### "); r_mid = "<h3>뒤 글</h3>" in edh()
    res = {}
    for tok, want in [("* ", "<ul><li>"), ("- ", "<ul><li>"), ("1. ", "<ol><li>"), ("> ", "<blockquote>"), ("--- ", "<hr>"), ("<> ", 'class="decision"'), ("``` ", "<pre>"), ("[] ", 'class="check"'), ("#### ", "<h4>")]:
        clear_ed(); pg.keyboard.type(tok); res[tok] = want in edh()
    clear_ed(); pg.keyboard.type("## "); pg.keyboard.press("Control+z"); undo = "<h2>" not in edh() and "##" in pg.inner_text("#ed")
    check("줄 맨 앞 빠른 서식 (첫 줄·글 앞에서도)", r1 and r_first and r_mid and all(res.values()) and undo, f"{r1},{r_first},{r_mid},{res},{undo}")
    clear_ed(); pg.keyboard.type("가 **굵게** 나 *기울임* ~~취소~~ `코드` [구글](https://google.com) 끝"); h = edh()
    inl = all(x in h for x in ["<b>굵게</b>", "<i>기울임</i>", "<s>취소</s>", "<code>코드</code>", 'href="https://google.com"'])
    clear_ed(); pg.keyboard.type("공격력*1.5 방어*2"); no_false = "<i>" not in edh()
    check("글 중간 빠른 서식", inl and no_false, h)
    clear_ed(); pg.keyboard.type("마감 //"); pg.wait_for_timeout(100); date = pg.locator("#ed time.date").count() == 1 and pg.locator(".chippop input[type=date]").count() == 1
    pg.keyboard.type("까지"); popclosed = pg.locator(".chippop").count() == 0
    pg.keyboard.type(" :smi"); pg.wait_for_timeout(100); pg.keyboard.press("Enter"); emo = "😀" in pg.inner_text("#ed")
    check("// 날짜 · : 이모지", date and popclosed and emo, f"{date},{popclosed},{emo},{edh()}")
    clear_ed(); pg.keyboard.type("/status"); pg.wait_for_timeout(100); pg.keyboard.press("Enter"); pg.wait_for_timeout(100)
    pg.keyboard.type("진행 중"); pg.click('.chippop [data-c="blue"]'); pg.keyboard.press("Enter"); pg.wait_for_timeout(50)
    st = pg.locator("#ed span.status.blue", has_text="진행 중").count() == 1
    pg.keyboard.press("End"); pg.keyboard.press("Enter"); pg.keyboard.type("/expand"); pg.wait_for_timeout(100); pg.keyboard.press("Enter"); pg.keyboard.type("자세히"); pg.keyboard.press("Enter"); pg.keyboard.type("숨은 내용")
    ex = pg.locator("#ed .expand .xtitle", has_text="자세히").count() == 1 and pg.locator("#ed .expand .xbody", has_text="숨은 내용").count() == 1
    pg.keyboard.press("Enter"); pg.keyboard.press("Enter"); pg.keyboard.type("/toc"); pg.wait_for_timeout(100); pg.keyboard.press("Enter")
    pg.keyboard.type("/2단"); pg.wait_for_timeout(100); pg.keyboard.press("Enter"); pg.keyboard.type("왼쪽")
    lay = pg.locator("#ed .cols.c2 .col").count() == 2
    pg.locator("#ed > p").last.click(); pg.keyboard.type("/include"); pg.wait_for_timeout(100); pg.keyboard.press("Enter"); pg.wait_for_timeout(100); pg.keyboard.type("전투"); pg.wait_for_timeout(100); pg.keyboard.press("Enter"); pg.wait_for_timeout(100)
    inc = pg.locator("#ed div.include").count() == 1
    pg.locator("#ed > p").last.click(); pg.keyboard.type("제목줄"); pg.keyboard.press("Control+Alt+2"); hk = pg.locator("#ed h2", has_text="제목줄").count() == 1
    pg.keyboard.press("Enter"); pg.keyboard.type("목록줄"); pg.keyboard.press("Control+Shift+8"); ul = pg.locator("#ed ul li", has_text="목록줄").count() == 1
    pg.keyboard.press("Enter"); pg.keyboard.press("Enter"); pg.keyboard.type("칠하기"); pg.keyboard.press("Shift+Home"); pg.keyboard.press("Control+Alt+y"); mk = pg.locator("#ed mark", has_text="칠하기").count() == 1
    check("/ 요소 (상태·접기·목차·단·불러오기) · 편집 단축키", st and ex and lay and inc and hk and ul and mk, f"{st},{ex},{lay},{inc},{hk},{ul},{mk}")
    pg.keyboard.press("Control+Enter"); pg.wait_for_timeout(300)
    on_view = pg.locator("#pDoc").count() == 1
    hidden = not pg.locator("#pDoc .expand .xbody").is_visible()
    pg.click("#pDoc .expand .xtitle"); shown = pg.locator("#pDoc .expand .xbody").is_visible()
    toc = pg.locator("#pDoc .toc a[data-to]").count() >= 1
    incv = "조심" in pg.inner_text("#pDoc .include")
    chips = pg.locator("#pDoc span.status.blue").count() == 1 and pg.locator("#pDoc mark").count() == 1 and pg.locator("#pDoc ul li", has_text="목록줄").count() == 1
    check("보기 화면: 접기 열기·목차·불러오기·배지", on_view and hidden and shown and toc and incv and chips, f"{on_view},{hidden},{shown},{toc},{incv},{chips}")
    pg.mouse.click(5, 300); pg.keyboard.press("Shift+Slash"); pg.wait_for_timeout(100); keys = pg.locator(".keys .ours").count() == 1
    pg.keyboard.press("Escape"); pg.keyboard.press("BracketLeft"); side = pg.evaluate("document.body.classList.contains('sidehide')"); pg.keyboard.press("BracketLeft")
    check("? 단축키 창 · [ 왼쪽 메뉴 접기", keys and side, f"{keys},{side}")

    # 14) 편집 중 로고·만들기 누르기 (브라우저 확인창 없이)
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.goto(URL + "#/new"); pg.wait_for_timeout(250)
    pg.fill("#edTitle", "쓰다 만 글"); pg.click("#ed"); pg.keyboard.type("내용")
    pg.click(".logo"); pg.wait_for_timeout(150); asked = pg.locator("#askOk").count() == 1
    pg.click("#askOk"); pg.wait_for_timeout(250); home = pg.locator("#ed").count() == 0 and pg.evaluate("location.hash") in ("#/", "")
    pg.click("#createBtn"); pg.wait_for_timeout(200); pg.fill("#edTitle", "두 번째"); pg.click("#ed"); pg.keyboard.type("글")
    pg.click("#createBtn"); pg.wait_for_timeout(150); asked2 = pg.locator("#askOk").count() == 1; pg.click("#askOk"); pg.wait_for_timeout(250)
    blank = pg.input_value("#edTitle") == "" and pg.locator("#ed").count() == 1
    pg.click(".logo"); pg.wait_for_timeout(250); clean_home = pg.locator("#ed").count() == 0
    check("편집 중 로고·만들기 → 화면 안 창으로 묻고 이동", asked and home and asked2 and blank and clean_home, f"{asked},{home},{asked2},{blank},{clean_home}")

    # 15) 휴지통 7일 지나면 자동 영구 삭제
    pg.evaluate("""() => { const d = JSON.parse(localStorage.getItem('wiki-v1')); const t = Date.now();
      d.pages.push({id:'old1',title:'오래된',html:'',parent:null,order:9,trashedAt:t-8*864e5,trashGroup:'old1'}, {id:'new1',title:'최근 지움',html:'',parent:null,order:10,trashedAt:t-2*864e5,trashGroup:'new1'});
      localStorage.setItem('wiki-v1', JSON.stringify(d)); }""")
    pg.goto(URL + "#/trash"); pg.reload(); pg.wait_for_timeout(400)
    ids = pg.evaluate("JSON.parse(localStorage.getItem('wiki-v1')).pages.map(p=>p.id)")
    check("7일 지난 휴지통 자동 삭제 (2일 된 건 남음)", "old1" not in ids and "new1" in ids and "5일 뒤 삭제" in pg.inner_text("#main"), str(ids))

    # 16) 플로우차트·간트·만들기(하위로)
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(200)
    pg.fill("#edTitle", "전투 흐름"); pg.click("#ed"); pg.keyboard.type("/flowchart"); pg.wait_for_timeout(100); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
    opened = pg.locator("#feCanvas .fc-node").count() == 2   # 시작 + 새 상자
    pg.locator('#feSide [data-f="t"]').fill("공격"); pg.keyboard.press("Tab"); pg.wait_for_timeout(100); pg.locator('#feSide [data-f="t"]').fill("피격")
    pg.locator('#feSide [data-f="note"]').fill("맞으면 경직"); pg.wait_for_timeout(50)
    three = pg.locator("#feCanvas .fc-node").count() == 3
    # 점 끌어서: 피격 → 시작 (뒤로 가는 선)
    pid_n = pg.evaluate("[...document.querySelectorAll('#feCanvas .fc-node')].find(n=>n.textContent.includes('피격')).dataset.id")
    sid_n = pg.evaluate("[...document.querySelectorAll('#feCanvas .fc-node')].find(n=>n.textContent.includes('시작')).dataset.id")
    pg.locator(f'#feCanvas .fc-node[data-id="{pid_n}"]').hover(); port = pg.locator(f'#feCanvas .fc-node[data-id="{pid_n}"] .fc-port').bounding_box(); tgt = pg.locator(f'#feCanvas .fc-node[data-id="{sid_n}"]').bounding_box()
    pg.mouse.move(port["x"] + 6, port["y"] + 6); pg.mouse.down(); pg.mouse.move(tgt["x"] + 40, tgt["y"] + 20, steps=8); pg.mouse.up(); pg.wait_for_timeout(150)
    back_edge = pg.locator("#feCanvas .fc-e.back").count() == 1
    # 글로 한꺼번에
    pg.click('[data-fe="text"]'); ta = pg.locator(".fe-text textarea"); ta.fill(ta.input_value() + "\n공격 -> {가드 중?}\n{가드 중?} -> 패링 : 예\n{가드 중?} -.-> 피격 : 아니오")
    pg.click('.fe-text [data-t="ok"]'); pg.wait_for_timeout(200)
    txt_ok = pg.locator("#feCanvas .fc-node.sh-dec").count() == 1 and pg.locator("#feCanvas .fc-node").count() == 5 and pg.locator("#feCanvas .fc-e.dash").count() == 1 and pg.locator("#feCanvas .fc-el", has_text="예").count() == 1
    note_kept = pg.evaluate("[...document.querySelectorAll('#feCanvas .fc-node')].some(n=>n.textContent.includes('피격') && n.textContent.includes('ⓘ'))")
    pg.click('[data-fe="dir"]'); pg.wait_for_timeout(100); vert = pg.locator('#feCanvas .fc-stage[data-dir="v"]').count() == 1
    pg.keyboard.press("Escape"); pg.wait_for_timeout(50); still = pg.locator("#feCanvas").count() == 1 and pg.locator('.fe-text [data-t="x"]').count() == 1   # Esc → 버릴지 묻기
    pg.click('.fe-text [data-t="x"]')
    pg.click('[data-fe="ok"]'); pg.wait_for_timeout(200)
    check("플로우차트 편집: Tab 이어 만들기·점 끌어 연결·뒤로 가는 선·글로 넣기·세로", opened and three and back_edge and txt_ok and note_kept and vert and still, f"{opened},{three},{back_edge},{txt_ok},{note_kept},{vert},{still}")
    pg.locator("#ed > p").last.click(); pg.keyboard.type("/gantt"); pg.wait_for_timeout(100); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
    rows0 = pg.locator("#geRows tr").count(); pg.click('[data-ge="add"]'); pg.keyboard.type("테스트 일정"); pg.wait_for_timeout(100)
    g_ok = rows0 == 3 and pg.locator("#gePrev .gt-bar", has_text="테스트 일정").count() == 1
    pg.click('[data-ge="ok"]'); pg.wait_for_timeout(200)
    pg.keyboard.press("Control+Enter"); pg.wait_for_timeout(400)
    view_ok = pg.locator("#pDoc .fc-node").count() == 5 and pg.locator("#pDoc .gt-bar").count() >= 3 and pg.locator("#pDoc .gt-ms").count() == 1
    pg.locator("#pDoc .fc-node", has_text="피격").hover(); pg.wait_for_timeout(100); tip = pg.locator("#pDoc .fc-tip", has_text="맞으면 경직").count() == 1
    pg.locator("#pDoc .fc-node", has_text="피격").click(); pg.mouse.move(5, 5); pg.wait_for_timeout(100); pinned = pg.locator("#pDoc .fc-tip.pin").count() == 1
    hi = pg.locator("#pDoc .fc-node.dim").count() >= 1
    pg.click('#pDoc [data-fb="all"]'); allv = pg.locator("#pDoc .fc-note", has_text="맞으면 경직").count() == 1
    srch = "가드 중" in pg.evaluate("(JSON.parse(localStorage.getItem('wiki-v1')).pages.find(p=>p.title==='전투 흐름')||{}).text || ''")
    check("보기: 차트 그리기·마우스 설명·눌러서 켜 두기·경로 강조·설명 모두 보기·검색", g_ok and view_ok and tip and pinned and hi and allv and srch, f"{g_ok},{view_ok},{tip},{pinned},{hi},{allv},{srch}")
    fid = pg.evaluate("location.hash.split('/')[2]")
    pg.click("#createBtn"); pg.wait_for_timeout(200); pg.fill("#edTitle", "하위 확인"); pg.click("#ed"); pg.keyboard.type("본문"); pg.keyboard.press("Control+s"); pg.wait_for_timeout(300)
    par = pg.evaluate("(JSON.parse(localStorage.getItem('wiki-v1')).pages.find(p=>p.title==='하위 확인')||{}).parent")
    check("페이지 연 상태에서 만들기 → 하위 페이지", par == fid, f"{par},{fid}")

    # 17) 표 정렬
    tbl = "<table><tbody><tr><th>이름</th><th>공격력</th><th>마감</th></tr><tr><td>골렘</td><td>1,200</td><td><time class='date' datetime='2026-12-05'>x</time></td></tr><tr><td>가고일</td><td>80</td><td></td></tr><tr><td>나가</td><td>350</td><td><time class='date' datetime='2026-11-30'>x</time></td></tr><tr><td>몬스터10</td><td></td><td></td></tr><tr><td>몬스터2</td><td>12.5%</td><td></td></tr></tbody></table><ul class='check'><li>체크</li></ul>"
    pg.evaluate("h => { const d = JSON.parse(localStorage.getItem('wiki-v1')); d.pages.push({id:'tb1',title:'표 정렬',html:h,parent:null,order:99,createdAt:1,updatedAt:1,createdBy:{name:'나'},updatedBy:{name:'나'},version:1}); localStorage.setItem('wiki-v1', JSON.stringify(d)); }", tbl)
    pg.goto(URL + "#/p/tb1"); pg.reload(); pg.wait_for_timeout(300)
    col = lambda i: pg.evaluate(f"[...document.querySelectorAll('#pDoc tr')].slice(1).map(r=>r.cells[{i}].textContent.trim())")
    pg.locator("#pDoc th", has_text="이름").click(); a1 = col(0)
    pg.locator("#pDoc th", has_text="공격력").click(); a2 = col(1); pg.locator("#pDoc th", has_text="공격력").click(); a3 = col(1)
    pg.locator("#pDoc th", has_text="공격력").click(); a4 = col(0)
    pg.locator("#pDoc th", has_text="마감").click(); a5 = col(0)
    pg.locator("#pDoc ul.check li").click(position={"x": 5, "y": 8}); pg.wait_for_timeout(300)
    saved = pg.evaluate("(()=>{const d=document.createElement('div');d.innerHTML=JSON.parse(localStorage.getItem('wiki-v1')).pages.find(p=>p.id==='tb1').html;return [...d.querySelectorAll('tr')].slice(1).map(r=>r.cells[0].textContent)})()")
    ok = a1 == ["가고일", "골렘", "나가", "몬스터2", "몬스터10"] and a2[:4] == ["12.5%", "80", "350", "1,200"] and a2[4] == "" and a3[:4] == ["1,200", "350", "80", "12.5%"] and a3[4] == "" \
         and a4 == ["골렘", "가고일", "나가", "몬스터10", "몬스터2"] and a5[:2] == ["나가", "골렘"] and saved == ["골렘", "가고일", "나가", "몬스터10", "몬스터2"]
    check("표 머리 눌러 정렬 (가나다·숫자·날짜·빈칸 맨 뒤·원래대로, 저장엔 안 남음)", ok, f"{a1} {a2} {a3} {a4} {a5} {saved}")
    pg.goto(URL + "#/p/tb1/edit"); pg.wait_for_timeout(300); pg.locator("#ed td", has_text="80").click(); pg.wait_for_timeout(100)
    pg.click('.tblbar [data-t="sd"]'); pg.wait_for_timeout(100)
    e1 = pg.evaluate("[...document.querySelectorAll('#ed tr')].slice(1).map(r=>r.cells[1].textContent.trim())")
    check("편집 중 표 막대 정렬 ↓ (저장되는 정렬)", e1[:4] == ["1,200", "350", "80", "12.5%"] and pg.evaluate("document.querySelector('#ed tr').cells[0].tagName") == "TH", str(e1))

    # 18) 댓글: 서식·멘션·날짜·할 일·편집·답글·반응·링크·알림
    pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)
    pg.evaluate("""() => { const d = JSON.parse(localStorage.getItem('wiki-v1')); d.pages.push({id:'cm1',title:'댓글 시험',html:'<p>본문</p>',parent:null,order:120,createdAt:1,updatedAt:1,createdBy:{email:'kim@x.com',name:'김기획'},updatedBy:{email:'lee@x.com',name:'이영호'},version:1});
      d.notes = [{id:'nn1',to:'',from:{email:'lee@x.com',name:'이영호'},kind:'mc',pageId:'cm1',cid:'',title:'댓글 시험',text:'봐 주세요',at:Date.now(),read:false}]; localStorage.setItem('wiki-v1', JSON.stringify(d)); }""")
    pg.goto(URL + "#/p/cm1"); pg.reload(); pg.wait_for_timeout(400)
    bell = pg.inner_text("#noteN") == "1"
    pg.click("#cIn"); pg.keyboard.type("검토 **중요** 부탁"); pg.keyboard.press("Enter"); pg.keyboard.type("[] 수치 확인 "); pg.keyboard.type("@김"); pg.wait_for_timeout(100)
    pick = pg.locator("#pick button", has_text="김기획").count() == 1; pg.keyboard.press("Enter"); pg.keyboard.type("//"); pg.wait_for_timeout(100); pg.keyboard.press("Escape")
    pg.keyboard.press("Control+Enter"); pg.wait_for_timeout(400)
    h = pg.inner_html("#cmtList")
    rich = all(x in h for x in ["<b>중요</b>", 'class="check"', 'class="mention"', 'data-email="kim@x.com"', 'class="date'])
    nts = pg.evaluate("JSON.parse(localStorage.getItem('wiki-v1')).notes.filter(n=>n.to==='kim@x.com').map(n=>n.kind)")
    check("댓글 서식·할 일·@멘션·// 날짜 + 멘션 알림(작성자 중복 없음)", bell and pick and rich and nts == ["mc"], f"{bell},{pick},{rich},{nts}")
    cm = pg.locator("#cmtList .cmt").first
    cm.locator("[data-cedit]").click(); pg.wait_for_timeout(100); pg.keyboard.type(" 수정"); pg.keyboard.press("Control+Enter"); pg.wait_for_timeout(300)
    edited = "수정됨" in pg.inner_text("#cmtList") and "수정" in pg.inner_text("#cmtList .ct")
    pg.locator("#cmtList .cmt").first.locator("[data-crep]").click(); pg.keyboard.type("답 달아요"); pg.keyboard.press("Control+Enter"); pg.wait_for_timeout(300)
    reply = pg.locator("#cmtList .cmt.rep", has_text="답 달아요").count() == 1
    pg.locator("#cmtList .cmt").first.locator("[data-cre]").first.click(); pg.click('.menu.reacts [data-pick="👍"]'); pg.wait_for_timeout(300)
    react = pg.locator("#cmtList .rc", has_text="👍 1").count() == 1
    li = pg.locator("#cmtList .ct ul.check li").first; li.click(position={"x": 6, "y": 8}); pg.wait_for_timeout(300)
    done = 'class="done"' in pg.evaluate("JSON.parse(localStorage.getItem('wiki-v1')).comments.find(c=>c.pageId==='cm1' && !c.parent).html")
    cid = pg.evaluate("JSON.parse(localStorage.getItem('wiki-v1')).comments.find(c=>c.pageId==='cm1' && !c.parent).id")
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.goto(URL + f"#/p/cm1/c/{cid}"); pg.wait_for_timeout(400); flash = pg.locator(f"#c-{cid}.flash").count() == 1
    check("댓글 편집·답글·반응·할 일 체크 저장·댓글 링크", edited and reply and react and done and flash, f"{edited},{reply},{react},{done},{flash}")
    pg.click("#noteBtn"); pg.wait_for_timeout(100); pg.locator(".menu.notes [data-nid]").first.click(); pg.wait_for_timeout(300)
    readok = pg.inner_text("#noteN") == "" and pg.evaluate("location.hash") == "#/p/cm1"
    pg.goto(URL + "#/p/cm1/edit"); pg.wait_for_timeout(300); pg.locator("#ed p").last.click(); pg.keyboard.press("End"); pg.keyboard.type(" @이영"); pg.wait_for_timeout(100); pg.keyboard.press("Enter")
    pg.keyboard.press("Control+s"); pg.wait_for_timeout(400)
    mp = pg.evaluate("JSON.parse(localStorage.getItem('wiki-v1')).notes.filter(n=>n.to==='lee@x.com').map(n=>n.kind)")
    check("알림 종: 눌러서 이동·읽음 / 페이지 본문 @멘션 알림", readok and mp == ["mp"] and pg.locator("#pDoc span.mention").count() == 1, f"{readok},{mp}")

    # 19) 본문 너비·왼쪽 메뉴 너비
    pg.goto(URL + "#/p/cm1"); pg.wait_for_timeout(300)
    w0 = pg.evaluate("document.querySelector('#pDoc').getBoundingClientRect().width")
    pg.click("[data-wbtn]"); pg.wait_for_timeout(100); w1 = pg.evaluate("document.querySelector('#pDoc').getBoundingClientRect().width")
    pg.click("[data-wbtn]"); pg.wait_for_timeout(100); lblx = pg.inner_text("[data-wbtn]")
    pg.click("[data-wbtn]"); pg.wait_for_timeout(100); w2 = pg.evaluate("document.querySelector('#pDoc').getBoundingClientRect().width"); lbl = pg.inner_text("[data-wbtn]")
    pg.goto(URL + "#/p/cm1/edit"); pg.wait_for_timeout(300); we = pg.evaluate("document.querySelector('#ed').getBoundingClientRect().width"); pg.click("#edCancel"); pg.wait_for_timeout(200)
    pg.click("[data-wbtn]"); pg.wait_for_timeout(100)
    bb = pg.locator(".side-rz").bounding_box(); pg.mouse.move(bb["x"] + 4, bb["y"] + 200); pg.mouse.down(); pg.mouse.move(420, 300, steps=6); pg.mouse.up(); pg.wait_for_timeout(100)
    sw = pg.evaluate("document.querySelector('.side').getBoundingClientRect().width"); pg.reload(); pg.wait_for_timeout(300); sw2 = pg.evaluate("document.querySelector('.side').getBoundingClientRect().width")
    pg.dblclick(".side-rz"); sw3 = pg.evaluate("document.querySelector('.side').getBoundingClientRect().width")
    check("본문 너비 보통→넓게→전체(편집도 같이)·왼쪽 메뉴 끌어서 넓히기", w1 > w0 and w2 >= w1 and "더 넓게" in lblx and "전체" in lbl and abs(we - w2) < 80 and 400 <= sw <= 440 and abs(sw2 - sw) < 2 and sw3 == 280, f"{w0},{w1},{w2},{lbl},{we},{sw},{sw2},{sw3}")

    # 20) 줄 중간 [] → 할 일, 할 일 속 날짜 지나면 빨강
    pg.goto(URL + "#/p/cm1"); pg.wait_for_timeout(300)
    pg.click("#cIn"); pg.keyboard.type("@김"); pg.wait_for_timeout(100); pg.keyboard.press("Enter"); pg.keyboard.type("테스트 [] ")
    mid = pg.locator("#cIn ul.check li span.mention").count() == 1 and "[]" not in pg.inner_text("#cIn") and "테스트" in pg.inner_text("#cIn ul.check li")
    pg.keyboard.type("//"); pg.wait_for_timeout(100); today = pg.locator("#cIn ul.check li time.date.today").count() == 1
    pg.fill(".chippop input[type=date]", "2020-01-01"); pg.wait_for_timeout(50); late_ed = pg.locator("#cIn time.date.late").count() == 1
    pg.keyboard.press("Escape"); pg.click("#cIn"); pg.keyboard.press("Control+Enter"); pg.wait_for_timeout(400)
    late_v = pg.locator("#cmtList .ct time.date.late").count() >= 1
    pg.locator("#cmtList .ct ul.check li", has_text="테스트").first.click(position={"x": 6, "y": 8}); pg.wait_for_timeout(300)
    done_v = pg.locator("#cmtList .ct time.date.doneD").count() >= 1
    pg.goto(URL + "#/p/cm1/edit"); pg.wait_for_timeout(300); pg.locator("#ed p").last.click(); pg.keyboard.press("End"); pg.keyboard.press("Enter")
    pg.keyboard.type("보스 패턴 정리 [] 마감 "); pg.keyboard.type("//"); pg.wait_for_timeout(100); pg.fill(".chippop input[type=date]", "2020-01-01"); pg.keyboard.press("Escape")
    pg.click("#ed"); pg.keyboard.press("Control+s"); pg.wait_for_timeout(400)
    page_late = pg.locator("#pDoc ul.check li", has_text="보스 패턴 정리").locator("time.date.late").count() == 1
    check("줄 중간 [] → 할 일(멘션 유지) · 할 일 날짜 오늘=노랑·지남=빨강·끝냄=회색 (댓글·글)", mid and today and late_ed and late_v and done_v and page_late, f"{mid},{today},{late_ed},{late_v},{done_v},{page_late}")

    # 21) 한글 입력 중에도 @멘션·/ 메뉴 검색 (입력기 흉내)
    pg.evaluate("() => { const d = JSON.parse(localStorage.getItem('wiki-v1')); d.pages.push({id:'pp1',title:'사람',html:'',parent:null,order:130,createdAt:1,updatedAt:1,createdBy:{email:'lee@x.com',name:'이영호'},updatedBy:{email:'lee@x.com',name:'이영호'},version:1}); localStorage.setItem('wiki-v1', JSON.stringify(d)); }")
    pg.goto(URL + "#/p/cm1"); pg.reload(); pg.wait_for_timeout(300)
    cdp = pg.context.new_cdp_session(pg); names = lambda: [x.split("\n")[0].strip() for x in pg.locator("#pick button").all_inner_texts()]
    pg.click("#cIn"); pg.keyboard.type("@"); pg.wait_for_timeout(60); ok_steps = []
    for comp in ["ㅇ", "이", "이여", "이영"]:
        cdp.send("Input.imeSetComposition", {"text": comp, "selectionStart": len(comp), "selectionEnd": len(comp)}); pg.wait_for_timeout(60); ok_steps.append(names()[:1] == ["이영호"] or names())
    cdp.send("Input.insertText", {"text": "이영"}); pg.wait_for_timeout(60); pg.keyboard.press("Enter")
    picked = pg.locator("#cIn span.mention", has_text="이영호").count() == 1
    pg.keyboard.type(" @"); cdp.send("Input.insertText", {"text": "ㄱㄱㅎ"}); pg.wait_for_timeout(60); cho = names() == ["김기획"]; pg.keyboard.press("Escape")
    pg.goto(URL + "#/p/cm1/edit"); pg.wait_for_timeout(300); pg.locator("#ed p").last.click(); pg.keyboard.press("End"); pg.keyboard.press("Enter"); pg.keyboard.type("/")
    cdp.send("Input.imeSetComposition", {"text": "ㅈ", "selectionStart": 1, "selectionEnd": 1}); pg.wait_for_timeout(60); sl = "접기" in names()
    cdp.send("Input.imeSetComposition", {"text": "저", "selectionStart": 1, "selectionEnd": 1}); pg.wait_for_timeout(60); sl2 = "접기" in names(); pg.keyboard.press("Escape")
    pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)
    check("한글 입력 중 검색: @ㅇ·@이여 → 이영호, @ㄱㄱㅎ(초성) → 김기획, /ㅈ·/저 → 접기", all(x is True for x in ok_steps) and picked and cho and sl and sl2, f"{ok_steps},{picked},{cho},{sl},{sl2}")

    # 22) 도구 막대 '+ 더 넣기' 메뉴 → 플로우차트
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "더 넣기 확인"); pg.click("#ed")
    pg.click('[data-act="more"]'); pg.wait_for_timeout(150); menu_ok = pg.locator(".menu button", has_text="플로우차트").count() == 1
    pg.locator(".menu button", has_text="플로우차트").click(); pg.wait_for_timeout(300); fe = pg.locator("#feCanvas").count() == 1
    pg.click('[data-fe="ok"]'); pg.wait_for_timeout(200)
    check("'+ 더 넣기' 메뉴가 열리고 플로우차트 넣기", menu_ok and fe and pg.locator("#ed div.flow").count() == 1, f"{menu_ok},{fe}")
    pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)

    # 23) 모든 넣기·서식 동작: 눌러서 반응하는지 + Ctrl+Z(또는 Alt+Z)로 되돌리고 Ctrl+Y로 다시
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "되돌리기 확인")
    def setup(sel_all=False):
        pg.evaluate("""s => { const e = document.querySelector('#ed'); e.__u = null; e.innerHTML = '<p>가나다</p>'; e.focus(); const r = document.createRange();
          if (s) r.selectNodeContents(e.querySelector('p')); else { r.selectNodeContents(e.querySelector('p')); r.collapse(false); } getSelection().removeAllRanges(); getSelection().addRange(r); }""", sel_all)
        pg.wait_for_timeout(30)
    edh = lambda: pg.evaluate("sanitize(document.querySelector('#ed').innerHTML)")
    base = "<p>가나다</p>"; bad = []
    def try_act(name, fn, sel_all=False, undo="Control+z"):
        setup(sel_all); fn(); pg.wait_for_timeout(120)
        if pg.locator("#feCanvas").count(): pg.click('[data-fe="ok"]'); pg.wait_for_timeout(150)
        if pg.locator("#gePrev").count(): pg.click('[data-ge="ok"]'); pg.wait_for_timeout(150)
        if pg.locator("#opPrev").count(): pg.click('[data-oe="ok"]'); pg.wait_for_timeout(150)
        if pg.locator(".chippop").count(): pg.keyboard.press("Escape"); pg.wait_for_timeout(50)
        after = edh()
        if after == base: bad.append(name + ":반응없음"); return
        pg.click("#ed", position={"x": 5, "y": 5}) if False else None
        pg.evaluate("document.querySelector('#ed').focus()"); pg.keyboard.press(undo); pg.wait_for_timeout(80)
        if edh() != base and not (name.startswith("슬래시") and edh().replace("&nbsp;", " ") == "<p>가나다 </p>"): bad.append(name + ":되돌리기안됨 " + edh()[:80]); return
        pg.keyboard.press("Control+y"); pg.wait_for_timeout(80)
        if edh() != after: bad.append(name + ":다시하기안됨")
    tb = lambda sel: (lambda: pg.click(f'#edbar {sel}'))
    for k in ["bold", "italic", "underline", "strikeThrough"]: try_act(k, tb(f'[data-cmd="{k}"]'), True)
    try_act("code(인라인)", tb('[data-act="code"]'), True)
    for k in ["insertUnorderedList", "insertOrderedList"]: try_act(k, tb(f'[data-cmd="{k}"]'))
    for k in ["check", "quote", "pre", "hr", "table"]: try_act(k, tb(f'[data-act="{k}"]'))
    for lbl in ["정보", "메모", "성공", "주의", "오류"]:
        try_act("패널 " + lbl, lambda lbl=lbl: (pg.click('#edbar [data-act="panel"]'), pg.wait_for_timeout(80), pg.locator(".menu button", has_text=lbl).click()))
    for lbl in ["접기", "상태", "날짜", "결정", "목차", "2단 레이아웃", "3단 레이아웃", "플로우차트", "간트 차트", "옵션 패널", "나란히 놓기"]:
        try_act("더 넣기 " + lbl, lambda lbl=lbl: (pg.click('#edbar [data-act="more"]'), pg.wait_for_timeout(80), pg.locator(".menu button", has_text=lbl).first.click()))
    try_act("글 모양 제목2", lambda: pg.select_option("#edbar select", "h2"))
    for cmd in ["/code", "/divider", "/panel", "/table", "/expand", "/quote", "/action", "/decision", "/toc", "/layout", "/heading", "/options", "/side"]:
        try_act("슬래시 " + cmd, lambda cmd=cmd: (pg.keyboard.type(" " + cmd), pg.wait_for_timeout(80), pg.keyboard.press("Enter")))
    for keys, sa in [("Control+Alt+1", False), ("Control+Shift+8", False), ("Control+Shift+7", False), ("Control+Shift+9", False), ("Control+Alt+e", False), ("Control+Alt+y", True), ("Control+Shift+s", True), ("Control+b", True)]:
        try_act("단축키 " + keys, lambda keys=keys: pg.keyboard.press(keys), sa)
    for typed in ["--- ", "``` ", "## ", "> ", "[] "]:
        def f(typed=typed): pg.evaluate("(() => { const e = document.querySelector('#ed'); const p = document.createElement('p'); p.innerHTML = '<br>'; e.appendChild(p); const r = document.createRange(); r.setStart(p, 0); getSelection().removeAllRanges(); getSelection().addRange(r); })()"); pg.keyboard.type(typed)
        setup(); f(); after = edh(); pg.keyboard.press("Alt+z"); pg.wait_for_timeout(60); txt = pg.inner_text("#ed")
        if typed.strip() not in txt: bad.append("빠른서식 " + typed + ":Alt+Z 안됨")
    setup(); pg.keyboard.type(" 새로 친 글"); pg.wait_for_timeout(900); pg.keyboard.type(" 두번째"); pg.keyboard.press("Control+z"); pg.wait_for_timeout(60)
    t1 = pg.inner_text("#ed"); pg.keyboard.press("Control+z"); t2 = pg.inner_text("#ed")
    if not ("새로 친 글" in t1 and "두번째" not in t1 and t2.strip() == "가나다"): bad.append(f"글자 되돌리기: {t1!r} {t2!r}")
    check("모든 넣기·서식 동작 반응 + Ctrl+Z/Alt+Z 되돌리기 + Ctrl+Y 다시 하기", not bad, " / ".join(bad))
    pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)

    # 24) 목록 Tab·Shift+Tab·Backspace·Enter, 보통 줄 들여쓰기, 표 Tab 이동
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "목록 키"); pg.click("#ed")
    def put(html, sel, off=0):
        pg.evaluate("([h,q,o]) => { const e = document.querySelector('#ed'); e.__u = null; e.innerHTML = h; e.focus(); const t = e.querySelector(q); const n = t.firstChild && t.firstChild.nodeType === 3 ? t.firstChild : t; const r = document.createRange(); r.setStart(n, o); getSelection().removeAllRanges(); getSelection().addRange(r); }", [html, sel, off])
    edh = lambda: pg.evaluate("sanitize(document.querySelector('#ed').innerHTML)").replace("&nbsp;", " ")
    res = {}
    for tag in ["ol", "ul"]:
        put(f"<{tag}><li>Counter</li><li>둘</li><li>셋</li></{tag}>", "li:nth-child(2)"); pg.keyboard.press("Tab"); a = edh()
        res[tag + " Tab"] = a == f"<{tag}><li>Counter<{tag}><li>둘</li></{tag}></li><li>셋</li></{tag}>"
        pg.keyboard.press("Shift+Tab"); res[tag + " Shift+Tab"] = edh() == f"<{tag}><li>Counter</li><li>둘</li><li>셋</li></{tag}>"
        pg.keyboard.press("Shift+Tab"); res[tag + " Shift+Tab 맨바깥→글"] = edh() == f"<{tag}><li>Counter</li></{tag}><p>둘</p><{tag}><li>셋</li></{tag}>"
        put(f"<{tag}><li>Counter</li><li><br></li></{tag}>", "li:first-child", 0); pg.keyboard.press("Backspace"); res[tag + " 첫 항목 Backspace"] = edh() in (f'<p class="in-1">Counter</p><{tag}><li></li></{tag}>', f'<p class="in-1">Counter</p><{tag}><li><br></li></{tag}>')
        put(f"<{tag}><li>a<{tag}><li><br></li></{tag}></li></{tag}>", "li li", 0); pg.keyboard.press("Enter"); res[tag + " 빈 하위 Enter"] = edh().startswith(f"<{tag}><li>a</li><li>")
    put("<ul><li><b>CounterClockWise</b></li><li><b>타입</b></li><li><br></li><li><b>boolean</b></li></ul>", "li:nth-child(3)", 0); pg.keyboard.press("Shift+Tab"); pg.keyboard.type("!")
    res["가운데 빈 항목 Shift+Tab → 그 자리 보통 줄"] = edh() == "<ul><li><b>CounterClockWise</b></li><li><b>타입</b></li></ul><p>!</p><ul><li><b>boolean</b></li></ul>"
    put("<ul><li><b>CounterClockWise</b></li><li><b>타입</b></li><li><br></li><li><b>boolean</b></li></ul>", "li:nth-child(3)", 0); pg.keyboard.press("Backspace"); pg.keyboard.type("그냥 글"); b1 = edh()
    pg.keyboard.press("Home"); pg.keyboard.press("Backspace"); b2 = edh(); pg.keyboard.press("Backspace"); b3 = edh()
    res["가운데 빈 항목 Backspace → 글머리만 없어지고 그 자리에서 글쓰기"] = b1 == '<ul><li><b>CounterClockWise</b></li><li><b>타입</b></li></ul><p class="in-1">그냥 글</p><ul><li><b>boolean</b></li></ul>' and '<p>그냥 글</p>' in b2 and "타입그냥 글" in b3.replace("</b>", "")
    put("<ul><li>타입<ul><li>boolean</li></ul></li><li>기본값</li></ul>", "li li", 0); pg.keyboard.press("Backspace")
    res["하위 항목 맨 앞 Backspace → 한 칸 바깥"] = edh() == "<ul><li>타입</li><li>boolean</li><li>기본값</li></ul>"
    put("<p>들여쓰기</p>", "p", 0); pg.keyboard.press("Tab"); pg.keyboard.press("Tab"); r1 = edh(); pg.keyboard.press("Shift+Tab"); r2 = edh(); pg.keyboard.press("Control+z"); r3 = edh()
    res["보통 줄 Tab/Shift+Tab/되돌리기"] = r1 == '<p class="in-2">들여쓰기</p>' and r2 == '<p class="in-1">들여쓰기</p>' and r3 == '<p class="in-2">들여쓰기</p>'
    put("<table><tbody><tr><th>a</th><th>b</th></tr><tr><td>c</td><td>d</td></tr></tbody></table>", "th", 0); pg.keyboard.press("Tab"); pg.keyboard.type("X")
    pg.keyboard.press("Tab"); pg.keyboard.press("Tab"); pg.keyboard.press("Tab"); pg.keyboard.type("Y"); t = edh()
    res["표 Tab 이동·끝에서 줄 추가"] = "<th>X</th>" in t and t.count("<tr>") == 3 and "<td>Y</td>" in t
    gap = pg.evaluate("""() => { const e = document.querySelector('#ed'); e.innerHTML = '<ul><li>타입<ul><li>boolean</li></ul></li><li>기본값</li></ul>'; const a = e.querySelector('li li').getBoundingClientRect(), b = e.querySelectorAll(':scope>ul>li')[1].getBoundingClientRect(); return b.top - a.bottom; }""")
    res["하위 목록 뒤 간격 없음"] = gap < 8
    check("목록 Tab 들여쓰기·Shift+Tab 내어쓰기·첫 항목 Backspace·빈 항목 Enter·보통 줄·표", all(res.values()), str({k: v for k, v in res.items() if not v}))
    pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)

    # 25) 오른쪽 위 바로가기 링크
    pg.goto(URL + "#/p/cm1"); pg.wait_for_timeout(300)
    pg.click("#pMore"); pg.locator(".menu button", has_text="바로가기에 넣기").click(); pg.wait_for_timeout(200)
    pg.goto(URL + "#/"); pg.wait_for_timeout(200); has = pg.locator("#qlinks .qlink", has_text="댓글 시험").count() == 1
    pg.click("#qlinks .qlink"); pg.wait_for_timeout(300); went = pg.evaluate("location.hash") == "#/p/cm1" and pg.locator("#qlinks .qlink.on").count() == 1
    pg.reload(); pg.wait_for_timeout(300); kept = pg.locator("#qlinks .qlink").count() == 1
    pg.click("#qlinks .qlink", button="right"); pg.locator(".menu button", has_text="바로가기에서 빼기").click(); pg.wait_for_timeout(200)
    gone = pg.locator("#qlinks .qlink").count() == 0
    check("오른쪽 위 바로가기: 페이지 메뉴로 넣기·눌러서 이동·새로고침해도 유지·우클릭으로 빼기", has and went and kept and gone, f"{has},{went},{kept},{gone}")

    # 26) 옵션 패널·나란히 놓기·글 사이 이미지
    import os, base64, tempfile
    png = os.path.join(tempfile.gettempdir(), "wiki_t.png")
    open(png, "wb").write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAFklEQVR4nGP8z0AaYBzVMKphVAN9NQAAjd8B/1m7l3kAAAAASUVORK5CYII="))
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "옵션 시험"); pg.click("#ed")
    pg.keyboard.type("/options"); pg.wait_for_timeout(100); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
    dflt = pg.locator("#opRows tr").count() == 1 and pg.locator("#opTitle").input_value() == "" and pg.locator('#opRows [data-f="n"]').first.input_value() == ""
    last = pg.locator('#opRows [data-f="n"]').last
    last.evaluate("(el, t) => { const dt = new DataTransfer(); dt.setData('text/plain', t); el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })); }", "DoNotLookAtTarget\tfalse\t대상을 보지 않음\nMoveSpeedRate\t1.5\nENUM_MoveSpeed\tWalk")
    pg.wait_for_timeout(100)
    pasted = pg.locator("#opRows tr").count() == 3 and pg.locator("#opPrev .ock").count() == 1 and pg.locator("#opPrev .oin.sel", has_text="Walk").count() == 1 and pg.locator("#opPrev .oin.num", has_text="1.5").count() == 1
    pg.click('[data-oe="ok"]'); pg.wait_for_timeout(200); in_ed = pg.locator("#ed div.opts .opv").count() == 1
    # 나란히: 왼쪽 이미지, 오른쪽 옵션 패널
    pg.locator("#ed > p").last.click(); pg.keyboard.type("/side"); pg.wait_for_timeout(100); pg.keyboard.press("Enter"); pg.wait_for_timeout(100)
    pg.set_input_files("#edFile", png); pg.wait_for_timeout(400)
    img_in_col = pg.locator("#ed .cols.fit .col").first.locator("figure img").count() == 1
    pg.locator("#ed .cols.fit .col").nth(1).locator("p").click(); pg.keyboard.type("/options"); pg.wait_for_timeout(100); pg.keyboard.press("Enter"); pg.wait_for_timeout(200); pg.click('[data-oe="ok"]'); pg.wait_for_timeout(200)
    opt_in_col = pg.locator("#ed .cols.fit .col").nth(1).locator("div.opts").count() == 1
    # 글 사이 이미지 두 장 나란히
    pg.evaluate("(() => { const e = document.querySelector('#ed'); const p = document.createElement('p'); p.textContent = '공격 패턴 예시 '; e.appendChild(p); const r = document.createRange(); r.setStart(p.firstChild, 8); getSelection().removeAllRanges(); getSelection().addRange(r); saveSel(); })()")
    pg.set_input_files("#edFile", png); pg.wait_for_timeout(400); pg.set_input_files("#edFile", png); pg.wait_for_timeout(400)
    two_inline = pg.evaluate("[...document.querySelectorAll('#ed p')].some(p => p.querySelectorAll('span.ifig img').length === 2 && p.textContent.includes('공격 패턴'))")
    pg.locator("#ed span.ifig img").first.click(); pg.wait_for_timeout(100); pg.locator(".figbar button", has_text="한 줄 차지").click(); pg.wait_for_timeout(100)
    tog = pg.locator("#ed span.ifig").count() == 1
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(100); undo_ok = pg.locator("#ed span.ifig").count() == 2
    pg.evaluate("document.querySelector('#ed').focus()"); pg.keyboard.press("Control+s"); pg.wait_for_timeout(400)
    view = pg.locator("#pDoc .cols.fit figure img").count() == 1 and pg.locator("#pDoc .cols.fit .opv").count() == 1 and pg.locator("#pDoc p span.ifig img").count() == 2 and pg.locator("#pDoc .opv").count() == 2
    pg.locator("#pDoc .opv-t tr.hasd").first.hover(); pg.wait_for_timeout(50); tip = pg.locator("#optTip", has_text="대상을 보지 않음").is_visible() and not pg.locator("#pDoc .opv-t tr.od").first.is_visible()
    srch = "DoNotLookAtTarget" in pg.evaluate("(JSON.parse(localStorage.getItem('wiki-v1')).pages.find(p=>p.title==='옵션 시험')||{}).text || ''")
    check("옵션 패널(기본·엑셀 붙여넣기·설명)·나란히(이미지|패널)·글 사이 이미지 2장·한 줄 전환·되돌리기·검색", dflt and pasted and in_ed and img_in_col and opt_in_col and two_inline and tog and undo_ok and view and tip and srch,
          f"{dflt},{pasted},{in_ed},{img_in_col},{opt_in_col},{two_inline},{tog},{undo_ok},{view},{tip},{srch}")

    # 27) 연결 보기
    pg.evaluate("""() => { const d = JSON.parse(localStorage.getItem('wiki-v1')); const L = (i,t) => `<a class="plink" data-page="${i}" href="#/p/${i}">${t}</a>`;
      const P = (id,title,html,parent,links) => ({id,title,html,text:'',parent:parent||null,order:200,links:links||[],createdAt:1,updatedAt:1,version:1});
      d.pages.push(P('lm_cw','MoveClockWise',`<p>${L('lm_tg','타겟')} ${L('lm_sp','이동 속도')} ${L('lm_bt','BT Task')}</p>`,null,['lm_tg','lm_sp','lm_bt']), P('lm_tg','타겟','<p>대상</p>'), P('lm_sp','이동 속도','<p>속도</p>'), P('lm_bt','BT Task','<p>태스크</p>'),
        P('lm_boss','보스 B',`<p>${L('lm_cw','MoveClockWise')}</p>`,null,['lm_cw']), P('lm_child','하위 메모','<p>x</p>','lm_cw'));
      localStorage.setItem('wiki-v1', JSON.stringify(d)); }""")
    pg.goto(URL + "#/p/lm_cw"); pg.reload(); pg.wait_for_timeout(300); pg.click("#pMap"); pg.wait_for_timeout(300)
    names = lambda: sorted(x.split("\n")[0].strip() for x in pg.locator("#lmBox .fc-node .fc-t").all_inner_texts())
    n1 = names(); lanes = [x.strip() for x in pg.locator("#lmBox .fc-lane").all_inner_texts()]
    ok1 = all(any(k in n for n in n1) for k in ["MoveClockWise", "타겟", "이동 속도", "BT Task", "보스 B", "하위 메모"]) and len(lanes) == 3
    pg.uncheck("#lmFam"); pg.wait_for_timeout(200); nofam = not any("하위 메모" in n for n in names())
    pg.locator('#lmBox .fc-node[data-id="plm_bt"]').dblclick(); pg.wait_for_timeout(300)
    went = pg.evaluate("location.hash") == "#/p/lm_bt" and pg.locator("#scrim .modal").count() == 0
    check("🕸 연결 보기: 링크해 온 곳|이 페이지|링크한 곳·위/하위 끄기·두 번 눌러 이동", ok1 and nofam and went, f"{n1},{lanes},{nofam},{went}")

    # 28) 표 칸에 이미지 + 모서리 끌어서 크기 바꾸기
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "표 이미지"); pg.click("#ed")
    pg.click('#edbar [data-act="table"]'); pg.wait_for_timeout(100); pg.locator("#ed td").first.click(); pg.set_input_files("#edFile", png); pg.wait_for_timeout(400)
    in_td = pg.locator("#ed td img").count() == 1
    pg.locator("#ed td img").click(); pg.wait_for_timeout(150); bars = pg.locator(".figbar").count() == 1 and pg.locator(".figrz").count() == 1
    w0 = pg.evaluate("document.querySelector('#ed td img').getBoundingClientRect().width"); bb = pg.locator(".figrz").bounding_box()
    pg.mouse.move(bb["x"] + 7, bb["y"] + 7); pg.mouse.down(); pg.mouse.move(bb["x"] + 80, bb["y"] + 7, steps=5); pg.mouse.up(); pg.wait_for_timeout(100)
    w1 = pg.evaluate("document.querySelector('#ed td img').getBoundingClientRect().width")
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(80); wu = pg.evaluate("document.querySelector('#ed td img').getBoundingClientRect().width"); pg.keyboard.press("Control+y"); pg.wait_for_timeout(80)
    pg.evaluate("document.querySelector('#ed').focus()"); pg.keyboard.press("Control+s"); pg.wait_for_timeout(400)
    wv = pg.evaluate("document.querySelector('#pDoc td img').getBoundingClientRect().width")
    check("표 칸에 이미지·그림 막대·모서리 끌어 크기·되돌리기·저장 후 유지", in_td and bars and w1 > w0 + 40 and abs(wu - w0) < 2 and abs(wv - w1) < 2, f"{in_td},{bars},{w0},{w1},{wu},{wv}")

    # 29) 웹에서 끌어온 이미지(맨 img)·행간
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "행간 시험"); pg.click("#ed")
    big = "data:image/png;base64," + base64.b64encode(open(png, "rb").read()).decode()
    pg.evaluate("src => { const e = document.querySelector('#ed'); e.innerHTML = '<table><tbody><tr><th>a</th><th>b</th></tr><tr><td></td><td>x</td></tr></tbody></table><p>끝</p>'; const img = document.createElement('img'); img.src = src; img.width = 3000; e.querySelector('td').appendChild(img); }", big)
    pg.locator("#ed td img").click(); pg.wait_for_timeout(150)
    stray = pg.locator("#ed td span.ifig img").count() == 1 and pg.locator(".figbar").count() == 1
    fits = pg.evaluate("(() => { const i = document.querySelector('#ed td img').getBoundingClientRect(), c = document.querySelector('#ed td').getBoundingClientRect(); return i.right <= c.right + 1; })()")
    pg.evaluate("(() => { const e = document.querySelector('#ed'); e.innerHTML = '<p>첫 줄</p><p>둘째 줄</p><ul><li>목록</li></ul>'; const r = document.createRange(); r.setStart(e.querySelector('p').firstChild, 0); r.setEnd(e.querySelector('li').firstChild, 1); getSelection().removeAllRanges(); getSelection().addRange(r); saveSel(); })()")
    pg.select_option("#lhSel", "lh-3"); pg.wait_for_timeout(80)
    lh = pg.evaluate("sanitize(document.querySelector('#ed').innerHTML)")
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(80); lhu = pg.evaluate("sanitize(document.querySelector('#ed').innerHTML)")
    check("웹에서 끌어온 맨 이미지도 칸 안에·편집 막대 / 행간 넓게(여러 줄·목록)·되돌리기",
          stray and fits and lh == '<p class="lh-3">첫 줄</p><p class="lh-3">둘째 줄</p><ul><li class="lh-3">목록</li></ul>' and "lh-" not in lhu, f"{stray},{fits},{lh},{lhu}")
    pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)

    # 30) 옵션 패널을 끌어서 표 칸에 넣기
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "끌기 시험"); pg.click("#ed")
    pg.evaluate("(() => { const e = document.querySelector('#ed'); const d = JSON.stringify({ title: 'MoveClockWise', rows: [{ n: 'TimeOut', t: 'num', v: '1000' }] }).replace(/\"/g, '&quot;'); e.innerHTML = sanitize('<table><tbody><tr><th>이름</th><th>예시</th></tr><tr><td>회전</td><td><br></td></tr></tbody></table><div class=\"opts\" data-opts=\"' + d + '\"></div><p>끝</p>'); prepEditor(e); })()")
    pg.wait_for_timeout(150); pg.hover("#ed div.opts"); h = pg.locator("#ed div.opts [data-bdrag]").bounding_box(); c = pg.locator("#ed td").nth(1).bounding_box()
    pg.mouse.move(h["x"] + 5, h["y"] + 5); pg.mouse.down(); pg.mouse.move(c["x"] + 20, c["y"] + 10, steps=6); pg.mouse.up(); pg.wait_for_timeout(150)
    inCell = pg.locator("#ed td div.opts").count() == 1 and pg.locator(".modal").count() == 0
    saved = pg.evaluate("sanitize(document.querySelector('#ed').innerHTML)")
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(100); back = pg.locator("#ed td div.opts").count() == 0
    check("옵션 패널을 끌어서 표 칸에 넣기·저장·되돌리기", inCell and '<td><div class="opts"' in saved and back, f"{inCell},{back},{saved[:300]}")
    pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)

    # 31) 빈 정보 패널 지우기 / 맨 앞 Backspace로 패널 풀기
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "패널 지우기"); pg.click("#ed")
    pg.evaluate("(() => { const e = document.querySelector('#ed'); e.innerHTML = '<p>위</p><div class=\"panel info\"><p><br></p></div><div class=\"panel note\"><p>글</p></div><p>끝</p>'; caretIn(e.querySelector('.panel p')); })()")
    pg.keyboard.press("Backspace"); pg.wait_for_timeout(80)
    one = pg.locator("#ed div.panel").count() == 1
    pg.evaluate("(() => { const p = document.querySelector('#ed .panel p'); const r = document.createRange(); r.setStart(p.firstChild, 0); getSelection().removeAllRanges(); getSelection().addRange(r); })()")
    pg.keyboard.press("Backspace"); pg.wait_for_timeout(80)
    html = pg.evaluate("sanitize(document.querySelector('#ed').innerHTML)")
    check("빈 패널 Backspace로 지우기 / 맨 앞 Backspace는 패널만 풀기", one and "panel" not in html and "<p>글</p>" in html, f"{one},{html}")
    pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)

    # 32) --- 치고 Enter → 구분선
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "구분선"); pg.click("#ed")
    pg.evaluate("(() => { const e = document.querySelector('#ed'); e.innerHTML = '<p>위</p><p><br></p>'; caretIn(e.querySelectorAll('p')[1]); })()")
    pg.keyboard.type("---"); pg.keyboard.press("Enter"); pg.wait_for_timeout(80); pg.keyboard.type("아래")
    html = pg.evaluate("sanitize(document.querySelector('#ed').innerHTML)")
    check("--- 치고 Enter → 구분선", html == "<p>위</p><hr><p>아래</p>", html)
    pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)

    # 33) 표 바로 위 빈 틈에 커서 → 패널·결정 넣기
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "틈"); pg.click("#ed")
    pg.evaluate("(() => { const e = document.querySelector('#ed'); e.innerHTML = '<p>위</p><table><tbody><tr><td>a</td></tr></tbody></table><p>끝</p>'; const r = document.createRange(); r.setStart(e, 1); getSelection().removeAllRanges(); getSelection().addRange(r); saveSel(); })()")
    pg.evaluate("insertBlock((() => { const u = document.createElement('ul'); u.className = 'decision'; u.innerHTML = '<li><br></li>'; return u; })(), null)")
    html = pg.evaluate("sanitize(document.querySelector('#ed').innerHTML)")
    check("표 바로 위 빈 틈에서도 블록이 그 자리에", html.startswith('<p>위</p><ul class="decision">') and html.index("decision") < html.index("<table"), html)
    pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)

    # 34) 표 칸 경계 끌어서 너비 바꾸기
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "칸 너비"); pg.click("#ed")
    pg.evaluate("(() => { const e = document.querySelector('#ed'); e.innerHTML = '<table><tbody><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></tbody></table><p>끝</p>'; })()")
    c0 = pg.locator("#ed td").first.bounding_box(); x = c0["x"] + c0["width"]; y = c0["y"] + c0["height"] / 2
    pg.mouse.move(x - 1, y); pg.mouse.down(); pg.mouse.move(x - 150, y, steps=5); pg.mouse.up(); pg.wait_for_timeout(80)
    c1 = pg.locator("#ed td").first.bounding_box()
    html = pg.evaluate("sanitize(document.querySelector('#ed').innerHTML)")
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(80); c2 = pg.locator("#ed td").first.bounding_box()
    check("표 칸 경계 끌어서 너비 바꾸기·저장·되돌리기", c1["width"] < c0["width"] - 100 and 'width="' in html and abs(c2["width"] - c0["width"]) < 3, f"{c0['width']},{c1['width']},{c2['width']},{html}")
    pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)

    # 35) 번호 목록 줄에서 [] + 띄어쓰기 → 할 일
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "목록 할 일"); pg.click("#ed")
    pg.evaluate("(() => { const e = document.querySelector('#ed'); e.innerHTML = '<ol><li>하나</li><li><a class=\"plink\" data-page=\"x1\" href=\"#/p/x1\">배회</a>\u00a0</li><li>셋</li></ol><p>끝</p>'; caretIn(e.querySelectorAll('li')[1], true); })()")
    pg.keyboard.type("[] "); pg.wait_for_timeout(80)
    pg.keyboard.type("확인"); pg.locator("#ed span.ick").click(); pg.wait_for_timeout(60)
    html = pg.evaluate("sanitize(document.querySelector('#ed').innerHTML)")
    check("목록 줄에서 [] → 그 자리에 체크 상자 (번호 목록 그대로)·누르면 체크", html == '<ol><li>하나</li><li><a data-page="x1" href="#/p/x1" class="plink">배회</a>&nbsp;<span class="ick on"></span>&nbsp;확인</li><li>셋</li></ol><p>끝</p>', html)
    pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)

    # 36) / 메뉴: 틀리게 쳐서 닫혀도 지우면 다시 열림
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "슬래시"); pg.click("#ed")
    pg.keyboard.type("/linkq"); pg.wait_for_timeout(80); closed = pg.locator("#pick").count() == 0
    pg.keyboard.press("Backspace"); pg.wait_for_timeout(80); reopened = pg.locator("#pick").count() == 1 and pg.locator("#pick", has_text="페이지 링크").count() == 1
    pg.keyboard.press("Backspace"); pg.keyboard.press("Backspace"); pg.wait_for_timeout(80); still = pg.locator("#pick").count() == 1
    check("/ 메뉴: 틀려서 닫혀도 지우면 다시 열림", closed and reopened and still, f"{closed},{reopened},{still}")
    pg.keyboard.press("Escape"); pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)

    # 37) 프로퍼티 설명을 드래그 → 옵션 패널 자동 채우기 / 안 고르면 빈 패널
    pg.goto(URL + "#/"); pg.wait_for_timeout(150); pg.click("#createBtn"); pg.wait_for_timeout(250); pg.fill("#edTitle", "프로퍼티"); pg.click("#ed")
    pg.evaluate("""(() => { const e = document.querySelector('#ed'); e.innerHTML = '<p>프로퍼티</p><p>MoveDistance</p><ul><li>데이터 타입 : Int</li><li>단위 : 1 = 1uu (100 = 1m)</li><li>동작 : 이동 거리</li></ul><p>PassThrough</p><ul><li>데이터 타입: boolean</li><li>기본 값: false</li><li>동작 : 뚫기<ul><li>AcceptanceRadius 안 먹음</li></ul></li></ul><p>끝</p>';
      const ps = e.querySelectorAll('p'); const r = document.createRange(); r.setStart(ps[0].firstChild, 0); r.setEnd(e.querySelectorAll('ul')[1].lastElementChild, 1); getSelection().removeAllRanges(); getSelection().addRange(r); saveSel(); insertKind('opts'); })()""")
    pg.wait_for_timeout(200)
    names = pg.locator('#opRows [data-f="n"]').evaluate_all("els => els.map(x => x.value)")
    ttl = pg.locator("#opTitle").input_value(); kinds = pg.locator('#opRows select').evaluate_all("els => els.map(x => x.value)")
    descs = pg.locator('#opRows [data-f="d"]').evaluate_all("els => els.map(x => x.value)")
    ok_fill = ttl == "프로퍼티" and names == ["MoveDistance", "PassThrough"] and kinds[:2] == ["num", "check"] and "단위: 1 = 1uu" in descs[0] and "AcceptanceRadius" in descs[1]
    pg.click('[data-oe="ok"]'); pg.wait_for_timeout(150)
    pg.evaluate("(() => { const e = document.querySelector('#ed'); caretIn(e.lastElementChild, true); saveSel(); insertKind('opts'); })()"); pg.wait_for_timeout(200)
    ok_empty = pg.locator("#opTitle").input_value() == "" and pg.locator('#opRows [data-f="n"]').count() == 1
    check("드래그한 프로퍼티 설명 → 옵션 패널 자동 채우기 / 안 고르면 빈 패널", ok_fill and ok_empty, f"{ttl},{names},{kinds},{descs},{ok_empty}")
    pg.click('[data-oe="ok"]'); pg.wait_for_timeout(150)
    pg.click("#edCancel"); pg.wait_for_timeout(100)
    if pg.locator("#askOk").count(): pg.click("#askOk"); pg.wait_for_timeout(200)
    check("자바스크립트 오류 없음", not errs, "; ".join(errs[:3]))
    b.close()
srv.shutdown()
print("OK" if not fails else f"{len(fails)} FAIL")
sys.exit(1 if fails else 0)
