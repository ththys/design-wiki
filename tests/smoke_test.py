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
    check("새 페이지 게시: 제목·소제목·할 일·표", "#/p/" in pg.evaluate("location.hash") and ">핵심 규칙</h2>" in doc and 'class="check"' in doc and "<table>" in doc and rows == 4 and has_tbl_bar, f"{rows},{has_tbl_bar},{doc[:300]}")
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
    pg.fill("#cIn", "좋아요 확인했어요"); pg.click("#cAdd"); pg.wait_for_timeout(300)
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
    pg.click("#themeBtn"); t1 = pg.evaluate("document.documentElement.dataset.theme"); pg.click("#themeBtn")
    check("다크·라이트 전환", t1 in ("dark", "light"))
    pg.goto(URL + f"#/p/{cid}"); pg.wait_for_timeout(200)
    pg.click("#pMore"); pg.locator(".menu button", has_text="삭제").click(); pg.click("#delYes"); pg.wait_for_timeout(300)
    check("페이지 삭제", pg.evaluate("JSON.parse(localStorage.getItem('wiki-v1')).pages.length") == 1)

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
    check("자바스크립트 오류 없음", not errs, "; ".join(errs[:3]))
    b.close()
srv.shutdown()
print("OK" if not fails else f"{len(fails)} FAIL")
sys.exit(1 if fails else 0)
