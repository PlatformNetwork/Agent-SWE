# prgrms-be-adv-devcourse/beadv4_4_HexaCore_BE-327 (original PR)

prgrms-be-adv-devcourse/beadv4_4_HexaCore_BE (#327): [REFACTOR] 피드백 반영 및 KafkaTemplate 수정 (#319)

## ✨ 관련 이슈

- Resolved: #319 

## 🔎 작업 내용

- pr 리뷰를 통한 피드백을 반영했습니다.
  -  ApiV1CashPaymentController 컨트롤러에 CashPaymentApiV1 인터페이스 추가 (스웨거 설정)
  - Toss Api 요청시 Authorization 헤더를 매 요청마다 생성하는 문제를 생성자에서 한 번 생성하도록 변경했습니다.
- dlt 전용으로 KafkaTemplate을 새로 생성하면서, 기존 KafkaTemplate이 자동 생성이 되지 않아서 발생하는 에러를, ProducerFactory를 주입받은 KafkaTemplate을 빈 등록 해주었습니다.  
참고 링크: https://www.notion.so/KafkaTemplate-30d15a01205480a0bcdeed93e82b4534?source=copy_link 
<br>




<br>

---

## ✅ Check List
- [x] 라벨 지정
- [x] 리뷰어 지정
- [x] 담당자 지정
- [x] 테스트 완료
- [x] 이슈 제목 컨벤션 준수
- [x] PR 제목 및 설명 작성
- [x] 커밋 메시지 컨벤션 준수

