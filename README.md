# 디자인 위키

팀이 같이 쓰는 기획 문서 위키입니다. 페이지 트리, 글쓰기 편집기(표·패널·할 일·이미지·코드), 검색, 최근 수정, 수정 기록·되돌리기, 댓글, 페이지 간 `[[링크]]`와 "이 페이지를 링크한 곳"이 있습니다.

- 주소: https://ththys.github.io/design-wiki/
- 파일: `index.html`(앱 전체), `config.js`(Firebase·Cloudinary 설정), `firestore.rules.wiki.txt`(권한 규칙 견본)
- 데이터: 레퍼런스 아카이브와 같은 Firebase 프로젝트의 `wiki_pages`, `wiki_history`, `wiki_comments` 컬렉션
- 이미지: Cloudinary Unsigned 업로드 (`wiki` 폴더)
- 테스트: `python tests/smoke_test.py` (주소 뒤 `?local` = 이 브라우저 저장 모드)

## 팀원 추가
1. Firebase 콘솔 > Firestore > 규칙에서 `isWikiTeam()` 목록에 이메일 추가 후 게시
2. 이메일 로그인을 쓰는 팀원은 Firebase 콘솔 > Authentication > 사용자 추가에서 계정 만들기

## 단축키
`/` 검색 · `E` 편집 · `Ctrl+S` 저장 · 편집 중 `/` 넣기 메뉴, `[[` 페이지 링크, `## ` `- ` `1. ` `[] ` `> ` ```` ``` ```` 빠른 서식
