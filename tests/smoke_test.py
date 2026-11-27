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
    pg.goto(URL + f"#/p/{cid}/edit"); pg.wait_for_timeout(200); pg.click("#ed"); pg.keyboard.press("End")
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
    rich = all(x in h for x in ["<b>중요</b>", 'class="check"', 'class="mention"', 'data-email="kim@x.com"', 'class="date"'])
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
    check("자바스크립트 오류 없음", not errs, "; ".join(errs[:3]))
    b.close()
srv.shutdown()
print("OK" if not fails else f"{len(fails)} FAIL")
sys.exit(1 if fails else 0)
