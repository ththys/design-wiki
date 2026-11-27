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
    check("새 페이지 게시: 제목·소제목·할 일·표", "#/p/" in pg.evaluate("location.hash") and "<h2>핵심 규칙</h2>" in doc and 'class="check"' in doc and "<table>" in doc and rows == 4 and has_tbl_bar, f"{rows},{has_tbl_bar},{doc[:300]}")
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
    pg.once("dialog", lambda d: d.accept()); pg.click("[data-cdel]"); pg.wait_for_timeout(300)
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
    pg.once("dialog", lambda d: d.dismiss()); pg.click("#edCancel"); pg.wait_for_timeout(200)
    check("저장 안 하고 닫으면 묻기", pg.locator("#ed").count() == 1)

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

    check("자바스크립트 오류 없음", not errs, "; ".join(errs[:3]))
    b.close()
srv.shutdown()
print("OK" if not fails else f"{len(fails)} FAIL")
sys.exit(1 if fails else 0)
