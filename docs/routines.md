# 루틴 API 및 프론트 연동

피그마의 매일·매주·격주·매월·매년과 선택적 시간 설정을 지원합니다.
프론트에서 날짜마다 POST 요청을 보내는 루프는 제거하고, 아래 요청 한 번만 보냅니다.
서버가 반복 날짜를 계산하고 루틴과 회차별 Todo를 한 트랜잭션에 저장합니다.

## 신규 루틴 생성

```http
POST /api/v1/todos/routines
Authorization: Bearer <accessToken>
Content-Type: application/json

{
  "requestId": "c0a31e62-8c24-4c3e-a384-5ad0c50d9ddd",
  "title": "운동",
  "description": "30분 달리기",
  "categoryId": 2,
  "startDate": "2026-09-09",
  "endDate": "2026-09-30",
  "time": "21:00",
  "timezone": "Asia/Seoul",
  "recurrence": {
    "frequency": "WEEKLY",
    "interval": 2,
    "weekdays": [1, 3, 5]
  }
}
```

위 요청은 시작일이 포함된 9/7~9/13 주부터 격주로 반복하므로
9/9, 9/11, 9/21, 9/23, 9/25의 5회차를 만듭니다. 시작일 이전 9/7은 만들지 않습니다.

| 항목 | 규칙 |
| --- | --- |
| requestId | 생성 동작마다 UUID 발급. 재시도는 같은 키와 같은 본문 |
| title / description | 제목 1~40자, 설명 최대 100자 |
| categoryId | 본인 카테고리 |
| startDate / endDate | YYYY-MM-DD, 양끝 포함, 최대 36,600일 |
| time | HH:MM, 5분 단위. 생략/null은 미설정 |
| timezone | IANA 시간대, 기본 Asia/Seoul |
| recurrence.frequency | DAILY, WEEKLY, MONTHLY, YEARLY |
| recurrence.interval | WEEKLY에서 1=매주, 2=격주. 나머지는 1 |
| recurrence.weekdays | WEEKLY에서 월=1~일=7. 중복 제거/정렬. 생략하면 시작일 요일 |
| 최대 회차 | 실제 발생하는 회차 1~1,000개. 초과/0개면 422, 부분 생성 없음 |

- 매일: DAILY. 날짜 범위의 모든 날짜.
- 매월: MONTHLY. 시작일과 같은 일자. 1/31 시작이면 2월/4월 등은 건너뜁니다.
- 매년: YEARLY. 시작일과 같은 월·일. 2/29 시작이면 윤년에만 생성합니다.
- 없는 날짜를 말일로 이동하지 않습니다.
- 호환용 최상위 weekdays도 지원합니다. 생략하면 매일, [1,3,5]면 매주 월수금입니다.
  recurrence와 동시에 보내면 422입니다.
- groupId, visibility, dueDate, isRoutine은 요청하지 않습니다.
  날짜별 Todo는 startDate=dueDate=그 회차 날짜, isRoutine=true, routineId를 가집니다.
- 날짜별 완료 상태는 독립적이며, 같은 회차가 여러 날짜에 걸치도록 개별 수정하면 그 기간에는 동일한 완료 상태를 표시합니다.

## 기존 할 일을 루틴으로 전환

```http
POST /api/v1/todos/101/routine
Authorization: Bearer <accessToken>
Content-Type: application/json

{
  "requestId": "db743877-c97f-4563-bc31-0bf37182920c",
  "startDate": "2026-09-08",
  "endDate": "2027-09-08",
  "time": null,
  "recurrence": {"frequency": "MONTHLY"}
}
```

제목/카테고리는 보내지 않습니다. 기존 Todo의 내용을 사용합니다.
원본 ID 101을 첫 발생 날짜의 회차로 이동하고, 이후 날짜만 추가 생성합니다.
원본을 따로 남겨 같은 날짜에 중복 생성하지 않습니다.
원본 완료 상태/하위 항목 상태는 유지하며, 이후 회차의 완료 상태는 초기화합니다.
원본에 연결된 내기나 다른 Todo의 선행 참조는 원본 ID를 계속 가리킵니다.
이미 루틴에 속한 Todo는 409, 타인의 Todo는 404입니다.
기존 제목이 40자를 넘는 경우 먼저 제목을 수정해야 합니다.

신규 생성과 전환 모두 다음 형태의 201 응답을 반환합니다.
createdCount는 원본 재사용을 포함한 총 회차 수입니다.

```json
{
  "routineId": 12,
  "createdCount": 3,
  "occurrences": [
    {"todoId": 101, "dueDate": "2026-09-07"},
    {"todoId": 102, "dueDate": "2026-09-09"},
    {"todoId": 103, "dueDate": "2026-09-11"}
  ]
}
```

## 중복 방지와 재시도

같은 사용자/requestId/정규화된 본문이면 생성 당시 결과를 반환합니다.
요일 순서나 중복은 정규화합니다. 내용이 바뀌면 409입니다.
서버 응답을 받지 못했다고 새 UUID를 발급하면 새 루틴이 만들어지므로, 실패 시 기존 요청을 보관하고 재사용하세요.

생성 결과는 불변 요청 기록이고, 이후 개별 Todo 수정은 이 기록을 바꾸지 않습니다.
삭제된 루틴의 재시도는 410이며, 삭제한 회차를 다시 생성하지 않습니다.
루틴 규칙 조회는 GET /api/v1/todos/routines/{routineId}, 현재 회차 상태는 Todo 조회를 사용합니다.

## JavaScript 연동 예제

```js
function prepareRoutineSubmission(apiUrl, fields, sourceTodoId = null) {
  const requestId = crypto.randomUUID();
  const body = JSON.stringify({ ...fields, requestId });
  const path = sourceTodoId == null
    ? "/api/v1/todos/routines"
    : `/api/v1/todos/${sourceTodoId}/routine`;
  let inFlight = null;
  let savedResult = null;

  return function submit(accessToken) {
    if (savedResult) return Promise.resolve(savedResult);
    if (inFlight) return inFlight;
    inFlight = (async () => {
      const response = await fetch(apiUrl.replace(/\/$/, "") + path, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body,
      });
      const result = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = result?.detail;
        const message = Array.isArray(detail)
          ? detail.map((item) => item.msg).join("\n")
          : detail?.message ?? `HTTP ${response.status}`;
        const error = new Error(message);
        error.status = response.status;
        throw error;
      }
      if (!result) throw new Error("응답을 확인할 수 없습니다. 같은 요청으로 재시도하세요.");
      savedResult = result;
      return result;
    })().finally(() => { inFlight = null; });
    return inFlight;
  };
}

const submit = prepareRoutineSubmission(API_URL, {
  title: "월수금 운동",
  categoryId: 2,
  startDate: "2026-09-01",
  endDate: "2026-09-30",
  time: "21:00",
  recurrence: { frequency: "WEEKLY", weekdays: [1, 3, 5] },
});

const result = await submit(accessToken);
// 네트워크 실패: 동일 submit(accessToken) 재호출.
// 401: 토큰 갱신 후 동일 submit(newAccessToken) 재호출.
// 매번 prepareRoutineSubmission을 다시 호출하면 중복 방지가 안 됩니다.
```

선택한 날짜의 GET /todos와 기간에 포함된 모든 월의 GET /todos/daily-status 캐시를 갱신하세요.
생성이 성공했는데 조회 갱신만 실패했다면 조회만 재시도합니다.
기존 Todo를 전환한 경우 원본이 있던 이전 날짜/월 캐시도 갱신해야 합니다.
새로고침을 넘기는 재시도는 사용자별 requestId와 본문을 함께 보관해야 합니다. 토큰을 본문에 보관하지 않습니다.

요일 버튼은 월=1~일=7을 사용합니다. JS getDay()의 일요일=0은 7로 변환합니다.
날짜 input의 YYYY-MM-DD 문자열을 그대로 전송하세요. toISOString()으로 변환해 날짜를 밀지 마세요.

## 전체 삭제

```js
const response = await fetch(`${API_URL}/api/v1/todos/routines/${routineId}`, {
  method: "DELETE",
  headers: { Authorization: `Bearer ${accessToken}` },
});
if (!response.ok) throw new Error("루틴 삭제 실패");
const { deletedCount } = await response.json();
```

- 완료된 회차와 원본을 포함해 전부 삭제합니다. 프론트에서 전체 삭제임을 알리고 호출하세요.
- 회차 Todo의 기존 DELETE /todos/{todoId}도 같은 전체 삭제 동작입니다.
- 남아 있는 다른 Todo의 선행 참조와 회차에 달린 내기/알림도 정리합니다.
- 루틴 ID로 삭제를 재호출하면 성공, deletedCount: 0입니다.
- 개별 Todo PATCH는 해당 회차에만 적용합니다. 전체 반복 규칙 변경 API는 이번 UI 범위에 포함하지 않습니다.
- 과거 isRoutine만 있고 routineId가 없는 행은 자동 묶기/전체 삭제 대상으로 추정하지 않습니다.

## 오류

| 상태 | 의미 |
| --- | --- |
| 201 | 최초 생성 또는 동일 생성 요청의 재응답 |
| 401 | 로그인/토큰 갱신 필요 |
| 404 | 본인 카테고리/원본 Todo/루틴이 없음 |
| 409 | 요청 키와 본문 충돌 또는 이미 루틴인 Todo를 다시 전환 |
| 410 | 삭제한 루틴. 같은 키로 재생성하지 않음 |
| 422 | 기간/시간/요일/제목/발생 횟수 등 검증 오류 |
| 네트워크 오류/5xx | 저장 여부가 불확실하므로 같은 키/본문으로 재시도 |

## DB와 배포

todo_routines.definition은 정규화된 최초 요청, creation_result는 최초 응답입니다.
Todo.routine_id와 occurrence_date가 회차를 연결하고, 두 값에 유일성을 적용합니다.
개별 Todo의 날짜를 수정해도 occurrence_date(원래 발생 날짜)는 변하지 않습니다.
전체 삭제 시 Todo 행을 제거하고 내부 루틴 요청 기록에 deleted_at을 남깁니다.
기간 내 실제 회차를 저장하는 방식이며, 무한 반복/조회 시 가상 생성 방식은 아닙니다.

기존 날짜 데이터 backfill, 보호 이미지 URL, 공개 정책 변경, 테스트/배포 절차는
[전체 계약](figma-backend-contract.md)의 배포 항목을 함께 확인하세요.
