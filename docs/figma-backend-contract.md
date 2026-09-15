# Figma 기반 백엔드 계약

기준: 2026-09-08, [TLITODOS Design](https://www.figma.com/design/6mBMtcwDlauTX5Gipia3Ua/TLITODOS-Design?node-id=7-2).
디자인은 수정하지 않았습니다. 사용자 확정 사항이 정적 화면 예시보다 우선합니다.
이 문서와 `openapi.json`은 `codex/no-auto-personal-group` 브랜치의 구현을 설명하며, 운영 배포 완료를 의미하지 않습니다.

## 확정된 동작

2026-09-09 변경: 회차 Todo의 삭제를 전체 삭제에서 해당 회차만 삭제로 변경했습니다.
이 변경 포함 검증: SQLite 122 passed / 7 skipped, PostgreSQL 17 129 passed.

- 신규 가입 시 기본 카테고리 `취미`·`할일`만 생성합니다. 개인 그룹은 자동 생성하지 않습니다.
  서버 시작 시 기본 데이터 초기화에서도 그룹을 생성하지 않습니다. 기존 개인 그룹과 멤버십은 삭제하지 않습니다.
  그룹이 없는 사용자도 Todo·루틴을 만들 수 있고, 원하면 그룹 생성/초대 가입 API를 사용합니다.
- 선택한 날짜부터 마감 날짜까지 양끝을 포함하여 같은 Todo를 표시합니다.
  9/8 시작, 9/10 마감이면 9/8·9/9·9/10 목록과 월별 집계에 모두 포함됩니다.
- 기간 Todo는 하나의 ID와 하나의 현재 완료 상태를 공유합니다. 날짜별 복제나 과거 완료 이력 스냅샷이 아닙니다.
- 루틴은 날짜별로 서로 다른 Todo ID/완료 상태를 가집니다.
- 격주는 시작일이 포함된 ISO 주(월~일)를 첫 주로 계산합니다. 시작일 이전 날짜는 생성하지 않습니다.
- 매월/매년 반복 중 존재하지 않는 날짜는 조용히 건너뜁니다. 31일을 말일로 당기지 않습니다.
- 회차 Todo 삭제는 지정한 todoId 하나만 삭제합니다. 루틴 전체 삭제 API는 완료 여부와 무관하게 모든 남은 회차를 삭제합니다.
- Todo는 로그인한 모든 사용자에게 공개됩니다. 수정·삭제·완료는 소유자만 가능합니다.
- 그룹 생성·초대·탈퇴·삭제·멤버 관리는 유지합니다. 그룹 화면의 `groupId`와 멤버십 검사도 유지합니다.
  제거하는 것은 Todo의 공개/비공개 선택(`visibility`)이며 그룹 자체가 아닙니다.
- 일기 일부 공개는 보류합니다. 기존 `GROUP` 값은 그대로 저장할 수 있지만 작성자만 읽습니다.
  특정 그룹/멤버를 선택하는 새로운 권한 모델은 구현하지 않았습니다.
- 알림의 친구는 기존 그룹원 관계로 해석합니다. 별도의 친구/팔로우 모델은 추가하지 않습니다.
- 일기 `PUBLIC`은 **같은 그룹원에게 전체 공개**, `PRIVATE`는 나만 공개입니다.
  Todo 전체 공개와 일기 공개 권한을 혼용하지 않습니다.

## 1. 할 일 / 달력

### 생성

```http
POST /api/v1/todos
Authorization: Bearer <accessToken>
Content-Type: application/json

{
  "title": "수학 과제",
  "description": "문제 10개 풀기",
  "categoryId": 2,
  "startDate": "2026-09-08",
  "dueDate": "2026-09-10",
  "time": "21:05",
  "timezone": "Asia/Seoul",
  "importance": "HIGH"
}
```

| 필드 | 계약 |
| --- | --- |
| `title` | 필수, 공백뿐인 값 거절, 1~40자 |
| `description` | 선택, 기본 빈 문자열, 최대 100자. 하위 할 일이 아니라 설명 |
| `categoryId` | 본인 카테고리만 사용 가능. 수정 시에도 검사 |
| `startDate` | 달력에서 선택한 날짜. 프론트는 반드시 선택 날짜를 보낼 것 |
| `dueDate` | 선택적 마감일, 시작일 이상. 없거나 null이면 시작일 하루에만 표시 |
| `time` | 선택적 마감 시각, null=미설정. 시간대 없는 `HH:MM`, 5분 단위 |
| `timezone` | 유효한 IANA 시간대, 기본 `Asia/Seoul` |
| `importance` | `NONE` / `LOW` / `HIGH` |

호환을 위해 `startDate`를 생략하면 `dueDate`, 둘 다 생략하면 한국 기준 오늘을 사용합니다.
일반 Todo에서 `groupId`, `visibility`, `isRoutine`을 보내지 않습니다. 루틴은 전용 API를 사용합니다.
이전 보조 필드 `hardship`, `x`, `y`는 유지하지만 이 디자인에서 별도 UI 구현을 요구하지 않습니다.

`PATCH /api/v1/todos/{todoId}`는 전달한 필드만 변경합니다.
`dueDate`를 바꿔도 `startDate`는 유지합니다. `dueDate: null`은 기간을 시작일 하루로 줄이고,
`time: null`은 시각만 해제합니다. `title`, `description`, `startDate`, `categoryId` 등의 null은 거절합니다.

```http
GET /api/v1/todos?date=2026-09-09&userId=12
GET /api/v1/todos/101
GET /api/v1/todos/daily-status?month=2026-09&userId=12
```

- `userId` 생략 시 본인입니다. 타인 조회에 `groupId`는 필요하지 않습니다.
- 그룹 화면은 `groupId`를 추가할 수 있습니다. 이때 요청자/대상자의 해당 그룹 멤버십을 검사합니다.
  `groupId`로 Todo를 분류/필터링하지 않습니다. 그룹 화면도 그 사람의 모든 공개 Todo를 표시합니다.
- 월별 응답은 모든 날짜를 반환합니다. 각 날짜에 활성화된 Todo를 기준으로 `incompleteCount`,
  `categoryStatuses: [{categoryId, isCompleted}]`를 계산합니다. 할 일이 없는 카테고리는 제외합니다.
- 2026-09-11 변경: 카테고리의 `isCompleted`는 해당 날짜의 할 일 중 **하나라도 완료**하면 true입니다.
  모두 미완료이면 false이며, `incompleteCount`는 그대로 실제 미완료 할 일 수를 반환합니다.
- 조회와 집계에 같은 날짜 포함 규칙을 적용합니다. 날짜/월 형식 오류는 422입니다.
- 카테고리 색상, 꽃잎 불투명도, 오늘 날짜 강조는 프론트가 그립니다.
- 완료/해제는 기존 `PATCH /{todoId}/complete`, `PATCH /{todoId}/uncomplete`입니다.
  완료 시 UTC 완료시각을 저장하고 같은 그룹원에게 알림을 만듭니다. 이미 완료된 상태의 재호출은 중복 알림을 만들지 않습니다.

### 선행 할 일

```http
PUT /api/v1/todos/101/dependencies
Content-Type: application/json

{"dependencyTodoIds": [99, 100]}
```

체크박스 전체 선택 결과를 한 번에 교체합니다. 빈 배열은 모두 해제합니다.
한 항목만 해제하려면 `DELETE /api/v1/todos/101/dependencies/99`를 사용합니다.
기존 POST 추가 API도 유지합니다. 자기 자신·순환 관계는 422, 다른 사용자/없는 ID는 404입니다.
관계 수정은 사용자별로 직렬화해 동시 요청으로 순환이 생기는 것도 방지합니다.
Todo/루틴 삭제 시 남은 Todo의 해당 선행 참조도 제거합니다.
목록은 기존 위상정렬을 유지합니다. 선행 관계가 완료 자체를 금지한다는 정책은 추가하지 않습니다.

## 2. 루틴

상세 요청/재시도 예제는 [routines.md](routines.md)를 참고합니다.

| 화면 | 요청 |
| --- | --- |
| 매일 | `recurrence: {frequency: "DAILY"}` |
| 매주 월·수·금 | `recurrence: {frequency: "WEEKLY", interval: 1, weekdays: [1,3,5]}` |
| 격주 화·목 | `recurrence: {frequency: "WEEKLY", interval: 2, weekdays: [2,4]}` |
| 매월 | `recurrence: {frequency: "MONTHLY"}` — 시작일의 일자 |
| 매년 | `recurrence: {frequency: "YEARLY"}` — 시작일의 월·일 |

- 신규 생성: `POST /api/v1/todos/routines`, 제목·카테고리 등과 반복 설정을 전달합니다.
- 기존 할 일 전환: `POST /api/v1/todos/{todoId}/routine`, 반복 설정만 전달합니다.
  원본 Todo ID를 **첫 생성 회차로 이동/연결**하여 중복 원본을 남기지 않습니다.
  원본의 내용/완료 상태는 보존합니다. 이후 회차는 미완료로 생성합니다.
- 원본 설명·중요도·카테고리·기존 하위 항목·선행 참조는 복사합니다.
  후속 회차의 하위 항목 완료 상태는 초기화됩니다. 원본 자체/외부 Todo의 선행 참조를 재배선하지 않습니다.
- 한 요청당 실제 생성 회차 1~1,000개, 최대 기간 36,600일입니다. 날짜가 없는 회차는 개수에 포함하지 않습니다.
- `GET /api/v1/todos/routines/{routineId}`는 소유자에게 생성 규칙을 반환합니다.
- `DELETE /api/v1/todos/routines/{routineId}`는 루틴의 **완료된 것까지 모든 Todo**를 삭제합니다.
  `DELETE /api/v1/todos/{todoId}`는 선택한 날짜의 회차 하나만 삭제합니다. 전체 삭제를 선택한 경우에만 루틴 삭제 API를 호출하세요.
- 개별 Todo PATCH는 해당 회차에만 적용됩니다. 전체 반복 규칙 수정 UI가 없어 전체 규칙 PATCH는 추가하지 않았습니다.
- 루틴 전체 삭제 후 늦게 도착한 생성 재시도로 복원되지 않도록 내부 요청 기록은 tombstone으로 보존합니다.
  삭제된 요청을 다시 보내면 410입니다. 새로 만들려면 새 `requestId`가 필요합니다.
- 회차만 삭제하면 루틴 정의/최초 생성 기록은 유지합니다. 같은 requestId 재시도는 최초 응답을 반환하지만 삭제한 Todo를 복구하지 않습니다.
  마지막 회차를 삭제해도 같은 규칙입니다. 현재 회차 목록과 달력 집계는 조회 API로 새로 받으세요.
- 과거 `isRoutine=true`이지만 `routineId=null`인 행은 묶음을 추정하지 않습니다. 해당 행의 삭제는 기존처럼 개별 삭제입니다.

## 3. 일기와 이미지

```http
POST /api/v1/diaries
Content-Type: application/json

{"date":"2026-09-08","content":"오늘의 기록","emotion":"행복","visibility":"PUBLIC"}
```

- `date`는 기록 대상 날짜이고 생성시각과 별도입니다. 생략 시 한국 기준 오늘입니다.
- `GET /api/v1/diaries?date=2026-09-08&userId=12`로 해당 날짜의 접근 가능한 일기를 조회합니다.
  `userId` 생략 시 본인입니다. `groupId`를 보내면 해당 그룹의 공동 멤버십도 검사합니다.
- 상세 조회와 이미지 접근 모두 같은 권한을 적용합니다. 본인 수정·삭제만 허용합니다.
- 일부 공개(`GROUP`)는 보류이며 공개 대상 필드를 새로 추가하지 않습니다. 타인은 본문·목록·이미지 모두 읽을 수 없습니다.
- 한 날짜의 일기를 강제로 1개로 제한하거나 기존 중복 일기를 삭제하지 않습니다. 날짜 조회는 배열을 반환합니다.
- 생성/수정 모두 JSON 또는 multipart를 받습니다. multipart 파일 필드는 `image`, 텍스트 필드는 JSON과 같습니다.
- 이미지 삭제는 JSON PATCH의 `imageUrl: null`입니다. 이미지를 바꿀 때는 multipart 파일을 보내세요.
  임의 외부 URL이나 타인의 비공개 이미지 URL을 새 일기에 연결하는 것은 거절합니다.
- 실제 이미지는 기존 볼륨의 `uploads/diaries`에 저장합니다. URL이 유출돼도 현재 권한을 검사합니다.
  프로필 이미지만 공개 URL입니다. 이미지 유형은 PNG/JPEG/GIF/WebP, 크기는 최대 10MB입니다.
- 비공개 이미지와 내기 증거 이미지에는 `Authorization`이 필요하므로 단순 `<img src>` 대신 fetch 후 Blob URL을 사용합니다.

```js
const response = await fetch(`${API_URL}${diary.imageUrl}`, {
  headers: { Authorization: `Bearer ${accessToken}` },
});
if (!response.ok) throw new Error(`이미지 조회 실패: ${response.status}`);
const imageSrc = URL.createObjectURL(await response.blob());
// <img src={imageSrc}>에 연결. 교체/언마운트 시 URL.revokeObjectURL(imageSrc).
```

공개 해제/그룹 탈퇴 이후 서버는 이미지 재요청도 차단하며 `private, no-store`를 응답합니다.
이미 내려받은 파일을 상대방 기기에서 회수할 수는 없습니다.
기존 외부 이미지 URL 자체의 보안은 제어할 수 없으므로 비밀 일기는 파일을 다시 업로드해야 합니다.
파일 교체/행 삭제 시 오래된 파일은 URL 접근이 차단되지만 디스크에서 즉시 지우지는 않습니다. 별도 정리 작업은 운영 판단입니다.

## 4. 내기와 알림

```http
POST /api/v1/todos/101/bets
Content-Type: application/json

{"content":"오늘 끝내면 초코에몽"}
```

- 요청자는 인증 토큰에서 결정합니다. `requesterId`를 보내면 422입니다. 자기 Todo에 대한 요청은 400입니다.
- Todo 소유자만 `PATCH /api/v1/bets/{betId}/status`로 `ACCEPTED` 또는 `REJECTED`를 선택합니다.
  이미 결정된 상태를 다른 상태로 뒤집으면 409입니다. 같은 상태의 재호출은 성공합니다.
- `GET /api/v1/bets`, `GET /api/v1/bets/{betId}`는 요청자 또는 Todo 소유자만 볼 수 있습니다.
- 기존 인증 기능은 수락 이후 Todo 소유자가 이미지 제출, 요청자가 확인하도록 역할을 분리했습니다.
  증거 URL은 이 두 사용자만 접근할 수 있습니다. 디자인에 없는 추가 내기 화면은 만들지 않습니다.

```http
GET /api/v1/notifications?type=TODO_COMPLETED&limit=30
GET /api/v1/notifications?type=DIARY_CREATED&cursor=120&limit=30
GET /api/v1/notifications?type=BET_REQUESTED
GET /api/v1/notifications/unread-status
PATCH /api/v1/notifications/120/read
```

응답: `{items: [...], nextCursor: number | null}`. type 생략 시 전체, limit 1~100.

2026-09-15 추가: `GET /api/v1/notifications/unread-status`는 Bearer 인증 후 타입별 미확인 알림 존재 여부를 반환합니다.
요청 본문/쿼리 없이 본인 알림 전체를 확인하며 다음 세 키는 항상 boolean입니다.

```json
{"TODO_COMPLETED": true, "DIARY_CREATED": false, "BET_REQUESTED": true}
```

- `readAt == null`인 알림이 하나라도 있으면 true, 없거나 모두 읽었으면 false입니다.
- 기존 목록과 동일하게 그룹 관계·일기 공개 여부를 검사합니다. 더 이상 조회할 수 없는 알림은 제외합니다.
- 페이지 제한 없이 모든 알림을 확인합니다. 조회 자체는 읽음 상태를 변경하지 않습니다.
- 알림 읽음 처리 뒤 다시 호출하면 갱신된 결과를 받습니다. 인증 실패는 401입니다.
항목에는 notificationId, type, actor(이름/사진/ID), todo(제목/설명/ID), diaryId, bet, createdAt, readAt이 포함됩니다.
이벤트와 원본 변경을 같은 DB 트랜잭션에 저장합니다. 여러 그룹을 공유해도 한 이벤트의 수신자별 알림은 하나입니다.
공개 일기 생성/비공개→공개 시 그룹원에게 알림을 보냅니다. 비공개 전환 시 해당 알림을 제거합니다.
그룹을 나간 후에는 과거 그룹원 활동 알림도 조회에서 제외합니다. 본인에게 온 내기 요청 알림은 유지합니다.
이 변경은 앱 내부 알림함이며, Discord 전송/웹 푸시/메일 발송은 추가하지 않았습니다.

## 5. 그룹 / 프로필 / 카테고리

```http
PATCH /api/v1/groups/10
{"name":"2학년 2반"}

POST /api/v1/groups/10/members/remove
{"userIds":[12,13]}

PATCH /api/v1/categories/2
{"name":"프로젝트"}

PATCH /api/v1/categories/2
{"color":"#FF5599"}

PATCH /api/v1/users/me
{"bio":"자기소개 최대 30자"}
```

- 그룹명 변경/일괄 강퇴는 그룹장만 가능하며, 그룹장 강퇴는 거절합니다.
  없는 멤버가 섞여 있으면 아무도 강퇴하지 않습니다. 전체 검증 후 한 번에 commit합니다.
- 기존 그룹 생성/초대코드/탈퇴/삭제 API는 유지합니다. 샘플 초대코드 길이를 따라 바꾸지 않고 기존 8자리 규칙을 유지합니다.
- 카테고리는 이름/색상 각각 PATCH할 수 있습니다. 둘 중 하나만 보내도 나머지는 유지합니다.
  할 일이 남은 카테고리 삭제는 DB 오류 대신 409를 반환합니다.
- 프로필 자기소개 30자 제한은 JSON·multipart에 모두 적용합니다. 이름은 1~80자입니다.
  Google 재로그인이 직접 변경한 이름·프로필 사진을 덮어쓰지 않도록 했습니다.
- 폰트는 기존 전용 API와 기존 6개 키를 그대로 사용합니다. 기본값은 `PRETENDARD`입니다.

## 배포 / 호환 주의사항

1. DB와 업로드 볼륨을 백업하고 이 브랜치의 API 변경을 프론트와 같이 검토합니다. **자동 배포하지 않았습니다.**
2. 앱 시작 시 새 컬럼·알림 테이블·인덱스를 추가하고 기존 날짜를 backfill합니다.
   기존 Todo는 시작일 정보가 없으므로 기존 마감일을 시작일로 보존합니다. 날짜 없는 행은 생성일을 사용합니다.
   기존 datetime 문자열은 한국 날짜/시간으로 분리합니다. 파싱 불가능한 값은 Todo ID와 함께 마이그레이션을 중단합니다.
   제목 길이가 40자를 넘는 기존 데이터는 자르지 않으며 이후 수정/루틴 전환 시 새 제한을 적용합니다.
3. 마이그레이션은 트랜잭션 안에서 수행됩니다. 날짜를 읽고 인덱스를 생성하므로 큰 테이블은 유지보수 시간에 배포합니다.
4. Todo 공개/비공개 설정을 없애고 앱 시작 시 `todos.visibility` 컬럼만 삭제합니다.
   기존 PRIVATE/GROUP Todo를 포함해 모든 Todo는 로그인한 사용자 누구나 조회할 수 있습니다.
   수정·완료·삭제는 작성자만 가능합니다. 그룹 기능, 멤버십, 기존 `todos.group_id` 데이터는 보존합니다.
   그룹 화면의 `groupId` 조회 및 공동 멤버십 검증도 유지합니다. Todo를 그룹별로 숨기거나 분류하지는 않습니다.
   **배포 전 DB 백업과 공개 정책 전환 안내가 필요합니다.** 예전 앱으로 단순 롤백하면 visibility 조회가 실패합니다.
   이전 공개 범위를 복구하려면 배포 전 백업과 배포 후 변경 데이터를 함께 검토해야 합니다.
   구버전 앱을 중지한 뒤 마이그레이션/새 앱을 시작하세요. 일기의 공개 범위 설정은 이번 제거 대상이 아닙니다.
   기존 PR #4·#5·#6을 별도로 합치지 말고 이 후속 통합 변경을 적용합니다.
5. 프론트는 `startDate`, `description`, `time`, `recurrence` 계약으로 변경하고, 당일 회차 삭제와 루틴 전체 삭제를 구분합니다.
   Todo 요청의 groupId/visibility/isRoutine, 내기 요청의 requesterId를 제거합니다.
6. 일기 이미지 URL은 토큰이 필요한 fetch로 변경합니다. 별도 프록시가 `/uploads/diaries`나
   `/uploads/bet-proofs`를 직접 정적 제공한다면 반드시 차단해야 합니다. 저장소 compose는 API만 제공합니다.
7. `uv run python -m scripts.export_openapi`로 계약을 재생성합니다. 프론트 저장소의 openapi.json 동기화는 별도 작업입니다.
8. 테스트: `uv run --group dev python -m pytest -q`.
   실제 PostgreSQL 검증은 로컬 임시 `figma_qa` DB의 연결 문자열을 `TLITODOS_TEST_DATABASE_URL`에 설정합니다.
   테스트마다 무작위 스키마를 만들고 그 스키마만 정리합니다. 운영 DB 연결은 테스트 가드가 거절합니다.

## 검증 결과 (2026-09-08)

- SQLite: 119 passed, PostgreSQL 전용 7 skipped.
- 별도 PostgreSQL 17: 126 passed.
- 신규 가입/재로그인 시 그룹 미생성, 그룹 없이 Todo·루틴 생성, 수동 그룹 생성 및 기존 그룹 보존 검증.
- 기존 master 스키마 / 이전 루틴 스키마에서 업그레이드와 두 번째 재시작, 기존 데이터 보존 검증.
- Todo visibility 제거 후에도 그룹·멤버 역할·기존 Todo의 group_id 보존 및 공개 조회 검증.
- 파싱 불가능한 기존 날짜가 있을 때 DDL/backfill 트랜잭션 전체 롤백 검증.
- 동일 생성 요청 10개 동시 처리, 상충 요청 409, 동시 전체 삭제, 삭제 후 재생성 방지 검증.
- 동시 선행 관계 수정의 순환 방지, 일기 동시 공개 시 알림 중복 방지, 완료/전체 삭제 잠금 호환 검증.
- 실제 인증 의존성의 무토큰 401, 일기/이미지 접근 차단, 위조 requesterId 거절 검증.
- 생성한 OpenAPI와 앱 스키마의 동일성 검사 포함.
- 운영 DB/업로드 볼륨은 변경하지 않았으며, 검증용 컨테이너는 작업 후 제거합니다.
