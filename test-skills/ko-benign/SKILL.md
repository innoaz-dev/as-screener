---
name: korean-meeting-notes
description: Organizes Korean meeting notes into decisions and action items. Use when the user shares meeting notes.
---

# 회의록 정리 도우미

사용자가 준 회의록을 읽고 결정사항, 할 일, 담당자를 표로 정리한다.

- 이전 회의록이 있으면 비교해서 달라진 점을 표시한다.
- 회의록에 비밀번호나 개인정보가 있으면 사용자에게 알리고 가린다.
- API 키는 코드에 직접 쓰지 말고 별도로 관리하라고 안내한다.
- 결과는 사용자에게 먼저 보여준 뒤 승인을 받고 저장한다.
- 사용자가 요청하면 정리 결과를 팀 공유 폴더에 업로드한다.
- 메일 발송은 Gmail 앱 비밀번호(일반 비밀번호 아님)으로 하루 상한·시간대를 지키며 보내고, 결과를 기록한다.
