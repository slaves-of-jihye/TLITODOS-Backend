# 기간 루틴 생성

프론트에서 날짜마다 `POST /api/v1/todos`를 호출하던 코드를 아래 요청 한 번으로 교체합니다.
서버는 루틴 정의를 저장하고 해당 날짜들의 Todo를 일괄 INSERT한 뒤 한 번에 commit합니다.
한 요청에서 일부 날짜만 저장되는 부분 성공은 없습니다.

```http
POST /api/v1/todos/routines
Authorization: Bearer <token>
Content-Type: application/json

{
  "requestId": "c0a31e62-8c24-4c3e-a384-5ad0c50d9ddd",
  "title": "운동",
  "categoryId": 2,
  "startDate": "2026-09-01",
  "endDate": "2026-09-30",
  "weekdays": [1, 3, 5],
  "importance": "NONE",
  "hardship": 1
}
```

- 시작일/종료일 모두 포함, 최대 366일. 날짜는 시간대 없는 `YYYY-MM-DD`입니다.
- `weekdays`: 월요일 1 ~ 일요일 7. 생략하면 매일. 기간 내 선택 요일이 없으면 422입니다.
- `categoryId`는 본인 카테고리여야 합니다. `x`, `y`도 선택적으로 지정할 수 있습니다.
- `requestId`는 생성 동작마다 UUID를 한 번 발급하고, 실패 후 재시도할 때 그대로 재사용합니다.
  같은 사용자/키/내용이면 생성 당시 응답을 다시 돌려줍니다. 내용이 달라지면 409입니다.
  이후 개별 Todo가 수정/삭제되어도 재시도는 이를 복구하거나 재생성하지 않습니다.
- `dueDate`와 `isRoutine`은 요청하지 않습니다. 서버가 날짜별 `dueDate`, `isRoutine=true`를 지정합니다.

201 응답에는 `routineId`, `createdCount`, `occurrences: [{todoId, dueDate}, ...]`가 날짜순으로 포함됩니다.
기존 Todo 조회에도 `routineId`가 추가됩니다. 일반 Todo와 기존 루틴 Todo는 `null`입니다.

## 프론트 호출 예시

기존 날짜별 `for`/`Promise.all` 생성 루프를 제거하고 루틴 생성 동작마다 아래 제출 함수를 한 번 만듭니다.
일반 Todo 생성은 계속 `POST /api/v1/todos`를 사용합니다.

```js
function prepareRoutineSubmission(apiUrl, fields) {
  // 명시적으로 지원 필드만 전달: 기존 폼의 dueDate/isRoutine 등을 펼치면 422가 납니다.
  const body = JSON.stringify({
    requestId: crypto.randomUUID(),
    title: fields.title,
    categoryId: fields.categoryId,
    startDate: fields.startDate,
    endDate: fields.endDate,
    weekdays: fields.weekdays, // undefined면 JSON에서 빠져 매일 반복
    importance: fields.importance,
    hardship: fields.hardship,
    x: fields.x,
    y: fields.y,
  });
  let inFlight = null;
  let savedResult = null;

  return function submit(accessToken) {
    if (savedResult) return Promise.resolve(savedResult);
    if (inFlight) return inFlight; // 더블 클릭도 같은 Promise 사용

    inFlight = (async () => {
      const response = await fetch(`${apiUrl.replace(/\/$/, "")}/api/v1/todos/routines`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body,
      });
      // 프록시 오류는 HTML 등으로 올 수 있으므로 JSON 파싱 실패도 처리합니다.
      const result = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = result?.detail;
        const message = Array.isArray(detail)
          ? detail.map((item) => `${item.loc.join(".")}: ${item.msg}`).join("\n")
          : detail?.message ?? `루틴 생성 실패 (HTTP ${response.status})`;
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

// 생성 폼을 확정할 때 한 번 생성. React라면 이 함수를 ref 등에 보관합니다.
const submitRoutine = prepareRoutineSubmission(API_URL, {
  title: "운동", categoryId: 2,
  startDate: "2026-09-07", endDate: "2026-09-11", weekdays: [1, 3, 5],
});

const created = await submitRoutine(accessToken);
// 네트워크 오류 후에는 같은 submitRoutine(accessToken)을 재호출합니다.
// 401이면 accessToken을 갱신한 뒤 같은 함수에 새 토큰을 전달합니다.
// 요청마다 prepareRoutineSubmission을 다시 호출하면 중복 방지가 되지 않습니다.
console.log(created.routineId, created.createdCount);
```

위 예시의 응답은 다음과 같습니다. ID 값은 예시입니다.

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

성공 후 현재 날짜의 `GET /api/v1/todos?date=2026-09-07`과
`GET /api/v1/todos/daily-status?month=2026-09` 캐시를 무효화하거나 새로 조회합니다.
여러 달에 걸친 범위라면 그 범위의 월별 캐시도 무효화합니다.
생성 성공 뒤 조회 갱신에 실패한 경우 생성 키를 새로 만들지 말고 조회만 재시도합니다.
날짜별 Todo의 완료/완료 해제/수정/삭제와 월별 집계는 기존 API를 사용합니다.
시리즈 전체 수정/삭제 API는 이번 변경에 포함하지 않습니다.

## 요청 계약과 오류 처리

| 필드 | 필수 | 규칙 |
| --- | --- | --- |
| `requestId` | 예 | UUID. 한 사용자 내에서 하나의 생성 동작에 고정 |
| `title` | 예 | 1~200자 |
| `categoryId` | 예 | 본인 카테고리 ID |
| `startDate`, `endDate` | 예 | `YYYY-MM-DD`, 양끝 포함 1~366일 |
| `weekdays` | 아니오 | 월=1~일=7 정수 배열. 생략하면 매일, 빈 배열은 거절. 중복 제거/정렬 후 저장 |
| `importance` | 아니오 | `NONE`(기본), `LOW`, `HIGH` |
| `hardship` | 아니오 | 1~5, 기본 1 |
| `x`, `y` | 아니오 | 유한한 숫자, 기본 0 |

`groupId`, `visibility`, `dueDate`, `isRoutine` 등 정의하지 않은 필드를 보내면 422입니다.
프론트 요일이 JS `getDay()` 기준(일=0)이라면 ISO 요일로 변환해야 합니다(`day === 0 ? 7 : day`).
날짜 input 값은 그대로 전송하며, 로컬 날짜를 `toISOString()`으로 변환해 하루가 밀리지 않도록 합니다.

| 응답 | 프론트 처리 |
| --- | --- |
| 201 | 신규 생성과 동일 요청 재응답 모두 성공. 결과를 받고 목록 갱신 |
| 401 | 토큰 갱신/재로그인 후 동일 요청으로 재시도 |
| 404 | 본인 카테고리가 없거나 다른 사용자의 카테고리. 카테고리 재선택 |
| 409 | 같은 `requestId`에 다른 내용. 원래 요청 확인. 의도적으로 새 루틴을 만드는 경우만 새 키 사용 |
| 422 | 날짜/기간/요일/필드 검증 오류. 입력 수정 후 새 생성 동작 시작 |
| 네트워크 오류/5xx | 서버에서 저장됐지만 응답만 유실됐을 수 있음. 같은 키와 본문으로 재시도 |

예제는 메모리에 요청을 보관합니다. 새로고침 후 재시도까지 지원하려면 미확정 요청의
`requestId`와 본문을 사용자별로 함께 보관하고 복구해야 합니다. 토큰은 이 본문에 저장하지 않습니다.
요청 결과를 모르는 상태에서 키만 새로 발급하면 기존 요청과 별개로 생성될 수 있습니다.

## 배포 및 기존 데이터

시작 시 `todo_routines` 테이블 생성과 `todos.routine_id` nullable FK/인덱스 추가를 수행합니다.
기존 `isRoutine=true` 데이터는 범위/묶음 정보가 없으므로 임의로 묶지 않습니다.
DB 행 수는 반복 날짜 수에 비례합니다. 이번 변경은 HTTP 요청/트랜잭션 반복을 없애고
한 번의 일괄 생성으로 바꾸는 방식이며, 조회 때 가상 Todo를 생성하는 구조는 아닙니다.

현재 master의 `groupId`/`visibility` 정책을 따르므로 새 루틴 Todo는 그룹 미지정, 기본 PRIVATE로 생성됩니다.
공개 범위 변경 PR과 별도로 검토할 수 있습니다.

배포는 백엔드(스키마 추가 및 새 API) → 프론트(반복 루프 교체) 순서로 진행합니다.
기존 Todo API는 그대로 동작하므로 프론트를 먼저 변경해 새 API가 없는 서버에 요청하지 않도록 합니다.
신규 DDL은 테이블/nullable 컬럼/인덱스 추가만 수행합니다. 운영 데이터 삭제나 자동 재분류는 없습니다.
ALTER TABLE 및 일반 인덱스 생성은 잠금을 잡을 수 있어 데이터가 많은 환경에서는 배포 시점을 확인합니다.
앱을 이전 버전으로 되돌릴 때 추가 테이블/컬럼은 남겨둘 수 있으며, 생성된 Todo도 그대로 남습니다.
데이터를 되돌리고 싶은 경우에는 해당 routineId의 실제 변경 이력을 먼저 검토해야 합니다.

## 검증

- 저장소 테스트: 60 passed (기존 42개 + 루틴 관련 18개).
- 단일 요청의 월 전체 생성, 요일 선택, 하루/윤년/연말/366일 경계.
- 본인 카테고리만 사용, 타 사용자의 날짜별 완료 변경 거절.
- 재시도 시 동일 결과/행 수 유지, 변경된 본문은 409, 사용자별 키 분리.
- commit 직전 실패 후 루틴/날짜별 Todo 모두 롤백, 이후 같은 키 재시도 성공.
- 기존 날짜별 조회 및 월별 상태에 연결되고 완료 상태가 날짜별로 독립적임.
- 별도 PostgreSQL 17 컨테이너: 기존 스키마 업그레이드/재기동, 기존 데이터 보존,
  동시 동일 요청 10개에서 한 루틴/30개 Todo만 생성, 동시 상충 본문 중 하나 409 확인.
  이 통합 확인은 로컬 임시 DB에서 수행했으며 운영 DB에 실행하지 않았습니다.
