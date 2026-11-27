// 디자인 위키 설정
// 공개 저장소라 이메일 같은 개인정보는 여기 적지 마세요. 팀원 권한은 Firebase 규칙에서 정합니다.
window.WIKI_CONFIG = {
  // 위키 이름 (상단·사이드바에 보임)
  spaceName: "디자인 위키",

  // 데이터 저장 (Firebase) — 레퍼런스 아카이브와 같은 프로젝트, 다른 칸(wiki_pages 등)에 저장
  // 비워 두면 "이 브라우저에만 저장" 모드로 동작합니다.
  firebase: {
    apiKey: "AIzaSyBt75WCkZe-gdOoLHd23_19Mq6VD2ua89s",
    authDomain: "monster-ref.firebaseapp.com",
    projectId: "monster-ref",
    storageBucket: "monster-ref.firebasestorage.app",
    messagingSenderId: "495025801043",
    appId: "1:495025801043:web:463bda47ab7d7b0c1803a6"
  },

  // 이미지·영상 올리기 (Cloudinary). 새 파일은 목록의 마지막 계정으로 올라갑니다.
  cloudinary: [
    { cloudName: "evqhgyll", uploadPreset: "monster_ref" }
  ]
};
