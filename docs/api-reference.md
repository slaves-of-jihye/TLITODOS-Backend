# TLITODOS 전체 API 명세

기준: 2026-09-08 · 브랜치 `codex/no-auto-personal-group` · PR #6 이후 개인 그룹 자동 생성 제거 포함.

운영 서버 배포 여부와 별개인 **현재 구현 기준 문서**입니다. 전체 55개 API의 경로·메서드·파라미터·요청 본문·응답을 한곳에 모았습니다.
OpenAPI 3.1.0을 바탕으로 작성하고, OpenAPI에 응답 모델이 없는 기존 API는 서비스 코드의 반환값으로 보완했습니다.
예제의 ID·날짜·문구는 설명용이며 실제 값은 달라집니다. 선택 필드와 null 허용은 서로 다른 개념입니다.

## 공통 규칙

- 2026-09-09 변경: `DELETE /api/v1/todos/{todoId}`는 루틴의 당일 회차만 삭제합니다. 루틴 전체 삭제 API는 별도로 유지합니다.
  검증: SQLite 122 passed / 7 skipped, PostgreSQL 17 129 passed. 선택한 날짜의 todoId를 전달하며 서버의 오늘 날짜만 허용하는 제한은 없습니다.
- 신규 가입 시 `취미`·`할일` 기본 카테고리만 생성하며 개인 그룹은 자동 생성하지 않습니다.
  그룹이 없는 사용자의 `GET /api/v1/groups` 응답은 `[]`입니다. Todo·루틴 생성에는 그룹 가입이 필요하지 않습니다.
  그룹을 원하면 직접 생성하거나 초대 코드로 가입합니다. 기존 개인 그룹과 멤버십 데이터는 보존합니다.
- Base URL: 배포 환경의 `API_URL`. 아래 경로를 그대로 붙입니다. 인증 관련 API도 `/api/v1` 접두사를 포함합니다.
- 인증이 필요한 경우 `Authorization: Bearer <accessToken>`. OpenAPI에서 이 헤더가 선택으로 표시되어도 런타임에서는 누락/만료/무효 시 401입니다.
- JSON 요청: `Content-Type: application/json`. FormData 업로드는 브라우저가 boundary를 설정하도록 Content-Type을 직접 지정하지 않습니다.
- 날짜: `YYYY-MM-DD`. 새 Todo의 시간은 `HH:MM` 5분 단위, 기본 시간대는 `Asia/Seoul`입니다.
- PATCH는 보낸 필드만 수정합니다. Pydantic에 선택으로 보이는 필드도 명시적 null은 별도 검증으로 거절할 수 있으므로 후반 동작 계약을 확인하세요.
- 할 일의 공개 범위 선택만 제거했습니다. **그룹과 멤버 기능은 유지**합니다. 일기 공개 범위와 혼동하지 마세요.
- 폰트 키: `PRETENDARD`(기본), `CAFE24_SSURROUND_AIR`, `GOYANG`, `GRIUN_FROMSOL`, `KYOBO_HANDWRITING_2019`, `PAPERLOGY`. 목록 밖은 422.

### 공통 오류

```json
{"detail":{"message":"오류 설명"}}
```

요청 검증 오류(422)는 `{"detail":[{"loc":["body","필드"],"msg":"오류 설명","type":"..."}]}` 형태도 사용합니다.
401 인증 실패, 403 권한 없음, 404 없음/접근 불가, 409 상태 충돌, 410 삭제된 루틴, 415 지원하지 않는 요청 형식, 422 입력 오류.
아래의 자동 응답 표는 OpenAPI에 선언된 코드만 표시합니다. 모든 런타임 오류가 표에 선언되어 있지는 않습니다.

## 전체 엔드포인트 목차

| 메서드 | 경로 | 분류 | 인증 |
| --- | --- | --- | --- |
| GET | [`/uploads/profiles/{filename}`](#api-1) | 이미지 | 불필요 |
| GET | [`/uploads/diaries/{filename}`](#api-2) | 이미지 | Bearer 필수 |
| GET | [`/uploads/bet-proofs/{filename}`](#api-3) | 이미지 | Bearer 필수 |
| POST | [`/api/v1/auth/google`](#api-4) | 인증 / 사용자 | 불필요 |
| POST | [`/api/v1/auth/refresh`](#api-5) | 인증 / 사용자 | 불필요 |
| POST | [`/api/v1/auth/logout`](#api-6) | 인증 / 사용자 | 불필요 |
| GET | [`/api/v1/users/me`](#api-7) | 인증 / 사용자 | Bearer 필수 |
| PATCH | [`/api/v1/users/me`](#api-8) | 인증 / 사용자 | Bearer 필수 |
| PATCH | [`/api/v1/users/me/notifications`](#api-9) | 인증 / 사용자 | Bearer 필수 |
| PATCH | [`/api/v1/users/me/font`](#api-10) | 인증 / 사용자 | Bearer 필수 |
| POST | [`/api/v1/users/me/discord`](#api-11) | 인증 / 사용자 | Bearer 필수 |
| PATCH | [`/api/v1/groups/{groupId}`](#api-12) | 그룹 | Bearer 필수 |
| GET | [`/api/v1/groups/{groupId}`](#api-13) | 그룹 | Bearer 필수 |
| DELETE | [`/api/v1/groups/{groupId}`](#api-14) | 그룹 | Bearer 필수 |
| POST | [`/api/v1/groups/{groupId}/members/remove`](#api-15) | 그룹 | Bearer 필수 |
| POST | [`/api/v1/groups`](#api-16) | 그룹 | Bearer 필수 |
| GET | [`/api/v1/groups`](#api-17) | 그룹 | Bearer 필수 |
| POST | [`/api/v1/groups/join`](#api-18) | 그룹 | Bearer 필수 |
| GET | [`/api/v1/groups/{groupId}/invite-code`](#api-19) | 그룹 | Bearer 필수 |
| DELETE | [`/api/v1/groups/{groupId}/members/{userId}`](#api-20) | 그룹 | Bearer 필수 |
| POST | [`/api/v1/groups/{groupId}/leave`](#api-21) | 그룹 | Bearer 필수 |
| GET | [`/api/v1/categories`](#api-22) | 카테고리 | Bearer 필수 |
| POST | [`/api/v1/categories`](#api-23) | 카테고리 | Bearer 필수 |
| PATCH | [`/api/v1/categories/{categoryId}`](#api-24) | 카테고리 | Bearer 필수 |
| DELETE | [`/api/v1/categories/{categoryId}`](#api-25) | 카테고리 | Bearer 필수 |
| POST | [`/api/v1/todos/routines`](#api-26) | 루틴 | Bearer 필수 |
| POST | [`/api/v1/todos/{todoId}/routine`](#api-27) | 루틴 | Bearer 필수 |
| GET | [`/api/v1/todos/routines/{routineId}`](#api-28) | 루틴 | Bearer 필수 |
| DELETE | [`/api/v1/todos/routines/{routineId}`](#api-29) | 루틴 | Bearer 필수 |
| POST | [`/api/v1/todos`](#api-30) | 할 일 | Bearer 필수 |
| GET | [`/api/v1/todos`](#api-31) | 할 일 | Bearer 필수 |
| GET | [`/api/v1/todos/daily-status`](#api-32) | 할 일 | Bearer 필수 |
| GET | [`/api/v1/todos/{todoId}`](#api-33) | 할 일 | Bearer 필수 |
| PATCH | [`/api/v1/todos/{todoId}`](#api-34) | 할 일 | Bearer 필수 |
| DELETE | [`/api/v1/todos/{todoId}`](#api-35) | 할 일 | Bearer 필수 |
| PUT | [`/api/v1/todos/{todoId}/dependencies`](#api-36) | 할 일 | Bearer 필수 |
| POST | [`/api/v1/todos/{todoId}/dependencies`](#api-37) | 할 일 | Bearer 필수 |
| DELETE | [`/api/v1/todos/{todoId}/dependencies/{dependencyTodoId}`](#api-38) | 할 일 | Bearer 필수 |
| POST | [`/api/v1/todos/{todoId}/subtasks`](#api-39) | 할 일 | Bearer 필수 |
| PATCH | [`/api/v1/todos/{todoId}/complete`](#api-40) | 할 일 | Bearer 필수 |
| PATCH | [`/api/v1/todos/{todoId}/uncomplete`](#api-41) | 할 일 | Bearer 필수 |
| POST | [`/api/v1/todos/{todoId}/bets`](#api-42) | 할 일 | Bearer 필수 |
| GET | [`/api/v1/bets`](#api-43) | 내기 | Bearer 필수 |
| GET | [`/api/v1/bets/{betId}`](#api-44) | 내기 | Bearer 필수 |
| PATCH | [`/api/v1/bets/{betId}/status`](#api-45) | 내기 | Bearer 필수 |
| POST | [`/api/v1/bets/{betId}/proof`](#api-46) | 내기 | Bearer 필수 |
| PATCH | [`/api/v1/bets/{betId}/verify`](#api-47) | 내기 | Bearer 필수 |
| POST | [`/api/v1/diaries`](#api-48) | 일기 | Bearer 필수 |
| GET | [`/api/v1/diaries`](#api-49) | 일기 | Bearer 필수 |
| GET | [`/api/v1/diaries/{diaryId}`](#api-50) | 일기 | Bearer 필수 |
| PATCH | [`/api/v1/diaries/{diaryId}`](#api-51) | 일기 | Bearer 필수 |
| DELETE | [`/api/v1/diaries/{diaryId}`](#api-52) | 일기 | Bearer 필수 |
| GET | [`/api/v1/notifications`](#api-53) | 알림 | Bearer 필수 |
| PATCH | [`/api/v1/notifications/{notificationId}/read`](#api-54) | 알림 | Bearer 필수 |
| GET | [`/ping`](#api-55) | 상태 확인 | 불필요 |

<a id="api-1"></a>

## 1. GET /uploads/profiles/{filename}

Profile Image

인증: Bearer 인증 없음.

파일 내용을 반환합니다(JSON 아님). PNG/JPEG/GIF/WebP를 지원합니다. 업로드는 각 사용자/일기/내기 API에서 multipart의 image 필드로 전송하며 최대 10MB입니다. 보호 이미지에는 Bearer 인증이 필요합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `filename` | string | 예 |  |

요청 본문: 없음.

### 응답

성공 200: 이미지 바이너리. Content-Type은 파일 형식에 따라 `image/png`, `image/jpeg`, `image/gif`, `image/webp`입니다.


<a id="api-2"></a>

## 2. GET /uploads/diaries/{filename}

Diary Image

인증: Bearer accessToken 필수.

파일 내용을 반환합니다(JSON 아님). PNG/JPEG/GIF/WebP를 지원합니다. 업로드는 각 사용자/일기/내기 API에서 multipart의 image 필드로 전송하며 최대 10MB입니다. 보호 이미지에는 Bearer 인증이 필요합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `filename` | string | 예 |  |

요청 본문: 없음.

### 응답

성공 200: 이미지 바이너리. Content-Type은 파일 형식에 따라 `image/png`, `image/jpeg`, `image/gif`, `image/webp`입니다.


<a id="api-3"></a>

## 3. GET /uploads/bet-proofs/{filename}

Bet Image

인증: Bearer accessToken 필수.

파일 내용을 반환합니다(JSON 아님). PNG/JPEG/GIF/WebP를 지원합니다. 업로드는 각 사용자/일기/내기 API에서 multipart의 image 필드로 전송하며 최대 10MB입니다. 보호 이미지에는 Bearer 인증이 필요합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `filename` | string | 예 |  |

요청 본문: 없음.

### 응답

성공 200: 이미지 바이너리. Content-Type은 파일 형식에 따라 `image/png`, `image/jpeg`, `image/gif`, `image/webp`입니다.


<a id="api-4"></a>

## 4. POST /api/v1/auth/google

Login With Google

인증: Bearer 인증 없음.

Bearer 인증이 표시된 API는 본인 계정에만 적용됩니다. 로그인은 Google access token, 갱신·로그아웃은 본 서비스 refreshToken을 본문으로 받습니다. 갱신 후 새 refreshToken을 보관하세요. 로그아웃은 해당 refreshToken을 폐기하며 기존 accessToken을 즉시 폐기하는 구현은 아닙니다.

### 요청 본문

`application/json`

스키마: [GoogleLoginRequest](#schema-googleloginrequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "accessToken": "<accessToken>",
  "refreshToken": "<refreshToken>",
  "expiresAt": "2026-09-08T09:30:00",
  "isNewUser": false
}
```


<a id="api-5"></a>

## 5. POST /api/v1/auth/refresh

Refresh Tokens

인증: Bearer 인증 없음.

Bearer 인증이 표시된 API는 본인 계정에만 적용됩니다. 로그인은 Google access token, 갱신·로그아웃은 본 서비스 refreshToken을 본문으로 받습니다. 갱신 후 새 refreshToken을 보관하세요. 로그아웃은 해당 refreshToken을 폐기하며 기존 accessToken을 즉시 폐기하는 구현은 아닙니다.

### 요청 본문

`application/json`

스키마: [RefreshTokenRequest](#schema-refreshtokenrequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "accessToken": "<newAccessToken>",
  "refreshToken": "<newRefreshToken>",
  "expiresAt": "2026-09-08T09:30:00",
  "refreshExpiresAt": "2026-10-08T09:00:00"
}
```


<a id="api-6"></a>

## 6. POST /api/v1/auth/logout

Logout

인증: Bearer 인증 없음.

Bearer 인증이 표시된 API는 본인 계정에만 적용됩니다. 로그인은 Google access token, 갱신·로그아웃은 본 서비스 refreshToken을 본문으로 받습니다. 갱신 후 새 refreshToken을 보관하세요. 로그아웃은 해당 refreshToken을 폐기하며 기존 accessToken을 즉시 폐기하는 구현은 아닙니다.

### 요청 본문

`application/json`

스키마: [RefreshTokenRequest](#schema-refreshtokenrequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "message": "처리 결과 메시지"
}
```


<a id="api-7"></a>

## 7. GET /api/v1/users/me

Get Me

인증: Bearer accessToken 필수.

Bearer 인증이 표시된 API는 본인 계정에만 적용됩니다. 로그인은 Google access token, 갱신·로그아웃은 본 서비스 refreshToken을 본문으로 받습니다. 갱신 후 새 refreshToken을 보관하세요. 로그아웃은 해당 refreshToken을 폐기하며 기존 accessToken을 즉시 폐기하는 구현은 아닙니다.

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "userId": 1,
  "name": "사용자",
  "profileImageUrl": null,
  "bio": "자기소개",
  "font": "PRETENDARD",
  "isDiscordLinked": false,
  "discordAlertEnabled": true
}
```


<a id="api-8"></a>

## 8. PATCH /api/v1/users/me

Update Me

인증: Bearer accessToken 필수.

Bearer 인증이 표시된 API는 본인 계정에만 적용됩니다. 로그인은 Google access token, 갱신·로그아웃은 본 서비스 refreshToken을 본문으로 받습니다. 갱신 후 새 refreshToken을 보관하세요. 로그아웃은 해당 refreshToken을 폐기하며 기존 accessToken을 즉시 폐기하는 구현은 아닙니다.

### 요청 본문

`application/json`

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `name` | string / null | 아니오 | 최소 길이: 1; 최대 길이: 80; 정규식: \S |
| `bio` | string / null | 아니오 | 최대 길이: 30 |
| `profileImageUrl` | string / null | 아니오 | 최대 길이: 500 |

정의하지 않은 필드는 거절합니다.

`multipart/form-data`

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `name` | string | 아니오 | 최소 길이: 1; 최대 길이: 80 |
| `bio` | string | 아니오 | 최대 길이: 30 |
| `image` | string (binary) | 아니오 |  |

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "userId": 1,
  "name": "사용자",
  "profileImageUrl": null,
  "bio": "자기소개",
  "font": "PRETENDARD",
  "isDiscordLinked": false,
  "discordAlertEnabled": true
}
```


<a id="api-9"></a>

## 9. PATCH /api/v1/users/me/notifications

Update Notifications

인증: Bearer accessToken 필수.

Bearer 인증이 표시된 API는 본인 계정에만 적용됩니다. 로그인은 Google access token, 갱신·로그아웃은 본 서비스 refreshToken을 본문으로 받습니다. 갱신 후 새 refreshToken을 보관하세요. 로그아웃은 해당 refreshToken을 폐기하며 기존 accessToken을 즉시 폐기하는 구현은 아닙니다.

### 요청 본문

`application/json`

스키마: [NotificationSettingsRequest](#schema-notificationsettingsrequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "discordAlertEnabled": true
}
```


<a id="api-10"></a>

## 10. PATCH /api/v1/users/me/font

Update Font

인증: Bearer accessToken 필수.

Bearer 인증이 표시된 API는 본인 계정에만 적용됩니다. 로그인은 Google access token, 갱신·로그아웃은 본 서비스 refreshToken을 본문으로 받습니다. 갱신 후 새 refreshToken을 보관하세요. 로그아웃은 해당 refreshToken을 폐기하며 기존 accessToken을 즉시 폐기하는 구현은 아닙니다.

### 요청 본문

`application/json`

스키마: [FontSettingRequest](#schema-fontsettingrequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "font": "PRETENDARD"
}
```


<a id="api-11"></a>

## 11. POST /api/v1/users/me/discord

Link Discord

인증: Bearer accessToken 필수.

Bearer 인증이 표시된 API는 본인 계정에만 적용됩니다. 로그인은 Google access token, 갱신·로그아웃은 본 서비스 refreshToken을 본문으로 받습니다. 갱신 후 새 refreshToken을 보관하세요. 로그아웃은 해당 refreshToken을 폐기하며 기존 accessToken을 즉시 폐기하는 구현은 아닙니다.

### 요청 본문

`application/json`

스키마: [DiscordLinkRequest](#schema-discordlinkrequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "discordUsername": "사용자"
}
```


<a id="api-12"></a>

## 12. PATCH /api/v1/groups/{groupId}

Rename Group

인증: Bearer accessToken 필수.

그룹 기능을 유지합니다. 상세/초대 코드 조회는 해당 그룹원, 이름 변경·삭제·강퇴는 그룹장만 가능합니다. 일반 탈퇴는 그룹장에게 허용되지 않습니다. 가입 정원 30명, 초대 코드 8자리. 일괄 강퇴는 전부 검증한 뒤 한 번에 처리합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `groupId` | integer | 예 |  |

### 요청 본문

`application/json`

스키마: [GroupRenameRequest](#schema-grouprenamerequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "groupId": 10,
  "name": "변경된 그룹"
}
```


<a id="api-13"></a>

## 13. GET /api/v1/groups/{groupId}

Get Group

인증: Bearer accessToken 필수.

그룹 기능을 유지합니다. 상세/초대 코드 조회는 해당 그룹원, 이름 변경·삭제·강퇴는 그룹장만 가능합니다. 일반 탈퇴는 그룹장에게 허용되지 않습니다. 가입 정원 30명, 초대 코드 8자리. 일괄 강퇴는 전부 검증한 뒤 한 번에 처리합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `groupId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "groupId": 10,
  "name": "우리 그룹",
  "description": "설명",
  "inviteCode": "abcdefgh",
  "members": [
    {
      "userId": 1,
      "name": "사용자",
      "profileImageUrl": null,
      "bio": "자기소개",
      "role": "LEADER"
    }
  ]
}
```


<a id="api-14"></a>

## 14. DELETE /api/v1/groups/{groupId}

Delete Group

인증: Bearer accessToken 필수.

그룹 기능을 유지합니다. 상세/초대 코드 조회는 해당 그룹원, 이름 변경·삭제·강퇴는 그룹장만 가능합니다. 일반 탈퇴는 그룹장에게 허용되지 않습니다. 가입 정원 30명, 초대 코드 8자리. 일괄 강퇴는 전부 검증한 뒤 한 번에 처리합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `groupId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "message": "처리 결과 메시지"
}
```


<a id="api-15"></a>

## 15. POST /api/v1/groups/{groupId}/members/remove

Remove Members

인증: Bearer accessToken 필수.

그룹 기능을 유지합니다. 상세/초대 코드 조회는 해당 그룹원, 이름 변경·삭제·강퇴는 그룹장만 가능합니다. 일반 탈퇴는 그룹장에게 허용되지 않습니다. 가입 정원 30명, 초대 코드 8자리. 일괄 강퇴는 전부 검증한 뒤 한 번에 처리합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `groupId` | integer | 예 |  |

### 요청 본문

`application/json`

스키마: [MembersRemoveRequest](#schema-membersremoverequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "removedUserIds": [
    2,
    3
  ]
}
```


<a id="api-16"></a>

## 16. POST /api/v1/groups

Create Group

인증: Bearer accessToken 필수.

그룹 기능을 유지합니다. 상세/초대 코드 조회는 해당 그룹원, 이름 변경·삭제·강퇴는 그룹장만 가능합니다. 일반 탈퇴는 그룹장에게 허용되지 않습니다. 가입 정원 30명, 초대 코드 8자리. 일괄 강퇴는 전부 검증한 뒤 한 번에 처리합니다.

### 요청 본문

`application/json`

스키마: [GroupCreateRequest](#schema-groupcreaterequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 201 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "groupId": 10,
  "name": "우리 그룹",
  "inviteCode": "abcdefgh"
}
```


<a id="api-17"></a>

## 17. GET /api/v1/groups

List Groups

인증: Bearer accessToken 필수.

그룹 기능을 유지합니다. 상세/초대 코드 조회는 해당 그룹원, 이름 변경·삭제·강퇴는 그룹장만 가능합니다. 일반 탈퇴는 그룹장에게 허용되지 않습니다. 가입 정원 30명, 초대 코드 8자리. 일괄 강퇴는 전부 검증한 뒤 한 번에 처리합니다.

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
[
  {
    "groupId": 10,
    "name": "우리 그룹",
    "memberCount": 3,
    "isLeader": true
  }
]
```


<a id="api-18"></a>

## 18. POST /api/v1/groups/join

Join Group

인증: Bearer accessToken 필수.

그룹 기능을 유지합니다. 상세/초대 코드 조회는 해당 그룹원, 이름 변경·삭제·강퇴는 그룹장만 가능합니다. 일반 탈퇴는 그룹장에게 허용되지 않습니다. 가입 정원 30명, 초대 코드 8자리. 일괄 강퇴는 전부 검증한 뒤 한 번에 처리합니다.

### 요청 본문

`application/json`

스키마: [GroupJoinRequest](#schema-groupjoinrequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "groupId": 10,
  "name": "우리 그룹",
  "message": "그룹에 성공적으로 가입되었습니다."
}
```


<a id="api-19"></a>

## 19. GET /api/v1/groups/{groupId}/invite-code

Get Invite Code

인증: Bearer accessToken 필수.

그룹 기능을 유지합니다. 상세/초대 코드 조회는 해당 그룹원, 이름 변경·삭제·강퇴는 그룹장만 가능합니다. 일반 탈퇴는 그룹장에게 허용되지 않습니다. 가입 정원 30명, 초대 코드 8자리. 일괄 강퇴는 전부 검증한 뒤 한 번에 처리합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `groupId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "groupId": 10,
  "inviteCode": "abcdefgh"
}
```


<a id="api-20"></a>

## 20. DELETE /api/v1/groups/{groupId}/members/{userId}

Remove Member

인증: Bearer accessToken 필수.

그룹 기능을 유지합니다. 상세/초대 코드 조회는 해당 그룹원, 이름 변경·삭제·강퇴는 그룹장만 가능합니다. 일반 탈퇴는 그룹장에게 허용되지 않습니다. 가입 정원 30명, 초대 코드 8자리. 일괄 강퇴는 전부 검증한 뒤 한 번에 처리합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `groupId` | integer | 예 |  |
| path | `userId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "message": "처리 결과 메시지"
}
```


<a id="api-21"></a>

## 21. POST /api/v1/groups/{groupId}/leave

Leave Group

인증: Bearer accessToken 필수.

그룹 기능을 유지합니다. 상세/초대 코드 조회는 해당 그룹원, 이름 변경·삭제·강퇴는 그룹장만 가능합니다. 일반 탈퇴는 그룹장에게 허용되지 않습니다. 가입 정원 30명, 초대 코드 8자리. 일괄 강퇴는 전부 검증한 뒤 한 번에 처리합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `groupId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "message": "처리 결과 메시지"
}
```


<a id="api-22"></a>

## 22. GET /api/v1/categories

List Categories

인증: Bearer accessToken 필수.

조회는 로그인 사용자에게 공개됩니다. 타인 조회에 groupId를 지정하면 요청자·대상자 모두 해당 그룹원이어야 합니다. 생성/수정/삭제는 본인 카테고리만 가능합니다. 최대 5개, 삭제 불가 기본 카테고리 또는 할 일이 남은 카테고리는 삭제할 수 없습니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| query | `groupId` | integer / null | 아니오 |  |
| query | `userId` | integer / null | 아니오 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
[
  {
    "categoryId": 2,
    "name": "할일",
    "color": "#123456",
    "isDeletable": true
  }
]
```


<a id="api-23"></a>

## 23. POST /api/v1/categories

Create Category

인증: Bearer accessToken 필수.

조회는 로그인 사용자에게 공개됩니다. 타인 조회에 groupId를 지정하면 요청자·대상자 모두 해당 그룹원이어야 합니다. 생성/수정/삭제는 본인 카테고리만 가능합니다. 최대 5개, 삭제 불가 기본 카테고리 또는 할 일이 남은 카테고리는 삭제할 수 없습니다.

### 요청 본문

`application/json`

스키마: [CategoryRequest](#schema-categoryrequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 201 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "categoryId": 2,
  "name": "할일",
  "color": "#123456",
  "isDeletable": true
}
```


<a id="api-24"></a>

## 24. PATCH /api/v1/categories/{categoryId}

Update Category

인증: Bearer accessToken 필수.

조회는 로그인 사용자에게 공개됩니다. 타인 조회에 groupId를 지정하면 요청자·대상자 모두 해당 그룹원이어야 합니다. 생성/수정/삭제는 본인 카테고리만 가능합니다. 최대 5개, 삭제 불가 기본 카테고리 또는 할 일이 남은 카테고리는 삭제할 수 없습니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `categoryId` | integer | 예 |  |

### 요청 본문

`application/json`

스키마: [CategoryPatchRequest](#schema-categorypatchrequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "categoryId": 2,
  "name": "할일",
  "color": "#123456"
}
```


<a id="api-25"></a>

## 25. DELETE /api/v1/categories/{categoryId}

Delete Category

인증: Bearer accessToken 필수.

조회는 로그인 사용자에게 공개됩니다. 타인 조회에 groupId를 지정하면 요청자·대상자 모두 해당 그룹원이어야 합니다. 생성/수정/삭제는 본인 카테고리만 가능합니다. 최대 5개, 삭제 불가 기본 카테고리 또는 할 일이 남은 카테고리는 삭제할 수 없습니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `categoryId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "message": "처리 결과 메시지"
}
```


<a id="api-26"></a>

## 26. POST /api/v1/todos/routines

루틴 일괄 생성

인증: Bearer accessToken 필수.

루틴 생성/전환/규칙 조회/삭제는 소유자만 가능합니다. requestId 재시도는 같은 본문으로 보내며, 바뀐 본문은 409, 삭제된 루틴 재시도는 410입니다. 전용 루틴 DELETE는 전체 삭제이며 Todo DELETE는 선택한 회차 하나만 삭제합니다. 일괄 생성은 한 트랜잭션이며 최대 1,000회차. 자세한 반복 규칙과 JS 예제는 문서 후반에 포함했습니다.

매일·매주·격주·매월·매년. 양끝 포함, 없는 날짜는 건너뜀. 최대 1,000회차. 같은 requestId 재시도는 중복 생성하지 않습니다.

### 요청 본문

`application/json`

스키마: [RoutineCreateRequest](#schema-routinecreaterequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 201 | [RoutineCreateResponse](#schema-routinecreateresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-27"></a>

## 27. POST /api/v1/todos/{todoId}/routine

기존 할 일을 루틴의 첫 회차로 전환

인증: Bearer accessToken 필수.

루틴 생성/전환/규칙 조회/삭제는 소유자만 가능합니다. requestId 재시도는 같은 본문으로 보내며, 바뀐 본문은 409, 삭제된 루틴 재시도는 410입니다. 전용 루틴 DELETE는 전체 삭제이며 Todo DELETE는 선택한 회차 하나만 삭제합니다. 일괄 생성은 한 트랜잭션이며 최대 1,000회차. 자세한 반복 규칙과 JS 예제는 문서 후반에 포함했습니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `todoId` | integer | 예 |  |

### 요청 본문

`application/json`

스키마: [RoutineScheduleRequest](#schema-routineschedulerequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 201 | [RoutineCreateResponse](#schema-routinecreateresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-28"></a>

## 28. GET /api/v1/todos/routines/{routineId}

Get Routine

인증: Bearer accessToken 필수.

루틴 생성/전환/규칙 조회/삭제는 소유자만 가능합니다. requestId 재시도는 같은 본문으로 보내며, 바뀐 본문은 409, 삭제된 루틴 재시도는 410입니다. 전용 루틴 DELETE는 전체 삭제이며 Todo DELETE는 선택한 회차 하나만 삭제합니다. 일괄 생성은 한 트랜잭션이며 최대 1,000회차. 자세한 반복 규칙과 JS 예제는 문서 후반에 포함했습니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `routineId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | [RoutineResponse](#schema-routineresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-29"></a>

## 29. DELETE /api/v1/todos/routines/{routineId}

루틴 및 모든 회차 전체 삭제

인증: Bearer accessToken 필수.

루틴 생성/전환/규칙 조회/삭제는 소유자만 가능합니다. requestId 재시도는 같은 본문으로 보내며, 바뀐 본문은 409, 삭제된 루틴 재시도는 410입니다. 전용 루틴 DELETE는 전체 삭제이며 Todo DELETE는 선택한 회차 하나만 삭제합니다. 일괄 생성은 한 트랜잭션이며 최대 1,000회차. 자세한 반복 규칙과 JS 예제는 문서 후반에 포함했습니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `routineId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | [RoutineDeleteResponse](#schema-routinedeleteresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-30"></a>

## 30. POST /api/v1/todos

Create Todo

인증: Bearer accessToken 필수.

할 일은 로그인 사용자 모두에게 공개되며 visibility 설정이 없습니다. 그룹·멤버 관리와 그룹 화면의 groupId 쿼리는 유지합니다. 타인 조회에 groupId를 지정하면 공동 멤버십을 검사합니다. 수정·삭제·완료·선행 관계·하위 항목은 작성자만 가능하며 내기 생성만 상대방이 요청합니다. 목록은 선행 할 일이 먼저 나오도록 정렬합니다.

### 요청 본문

`application/json`

스키마: [TodoCreateRequest](#schema-todocreaterequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 201 | [TodoResponse](#schema-todoresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-31"></a>

## 31. GET /api/v1/todos

List Todos

인증: Bearer accessToken 필수.

할 일은 로그인 사용자 모두에게 공개되며 visibility 설정이 없습니다. 그룹·멤버 관리와 그룹 화면의 groupId 쿼리는 유지합니다. 타인 조회에 groupId를 지정하면 공동 멤버십을 검사합니다. 수정·삭제·완료·선행 관계·하위 항목은 작성자만 가능하며 내기 생성만 상대방이 요청합니다. 목록은 선행 할 일이 먼저 나오도록 정렬합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| query | `groupId` | integer / null | 아니오 |  |
| query | `date` | string (date) / null | 아니오 |  |
| query | `userId` | integer / null | 아니오 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | Array&lt;[TodoResponse](#schema-todoresponse)&gt; | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-32"></a>

## 32. GET /api/v1/todos/daily-status

List Daily Todo Statuses

인증: Bearer accessToken 필수.

할 일은 로그인 사용자 모두에게 공개되며 visibility 설정이 없습니다. 그룹·멤버 관리와 그룹 화면의 groupId 쿼리는 유지합니다. 타인 조회에 groupId를 지정하면 공동 멤버십을 검사합니다. 수정·삭제·완료·선행 관계·하위 항목은 작성자만 가능하며 내기 생성만 상대방이 요청합니다. 목록은 선행 할 일이 먼저 나오도록 정렬합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| query | `month` | string | 예 | 정규식: ^[0-9]{4}-(0[1-9]\|1[0-2])$ |
| query | `userId` | integer / null | 아니오 |  |
| query | `groupId` | integer / null | 아니오 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | Array&lt;[DailyStatusResponse](#schema-dailystatusresponse)&gt; | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-33"></a>

## 33. GET /api/v1/todos/{todoId}

Get Todo

인증: Bearer accessToken 필수.

할 일은 로그인 사용자 모두에게 공개되며 visibility 설정이 없습니다. 그룹·멤버 관리와 그룹 화면의 groupId 쿼리는 유지합니다. 타인 조회에 groupId를 지정하면 공동 멤버십을 검사합니다. 수정·삭제·완료·선행 관계·하위 항목은 작성자만 가능하며 내기 생성만 상대방이 요청합니다. 목록은 선행 할 일이 먼저 나오도록 정렬합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `todoId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | [TodoResponse](#schema-todoresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-34"></a>

## 34. PATCH /api/v1/todos/{todoId}

Update Todo

인증: Bearer accessToken 필수.

할 일은 로그인 사용자 모두에게 공개되며 visibility 설정이 없습니다. 그룹·멤버 관리와 그룹 화면의 groupId 쿼리는 유지합니다. 타인 조회에 groupId를 지정하면 공동 멤버십을 검사합니다. 수정·삭제·완료·선행 관계·하위 항목은 작성자만 가능하며 내기 생성만 상대방이 요청합니다. 목록은 선행 할 일이 먼저 나오도록 정렬합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `todoId` | integer | 예 |  |

### 요청 본문

`application/json`

스키마: [TodoPatchRequest](#schema-todopatchrequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | [TodoResponse](#schema-todoresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-35"></a>

## 35. DELETE /api/v1/todos/{todoId}

Delete Todo

인증: Bearer accessToken 필수.

할 일은 로그인 사용자 모두에게 공개되며 visibility 설정이 없습니다. 그룹·멤버 관리와 그룹 화면의 groupId 쿼리는 유지합니다. 타인 조회에 groupId를 지정하면 공동 멤버십을 검사합니다. 수정·삭제·완료·선행 관계·하위 항목은 작성자만 가능하며 내기 생성만 상대방이 요청합니다. 목록은 선행 할 일이 먼저 나오도록 정렬합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `todoId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "message": "처리 결과 메시지"
}
```

루틴에 속해 있어도 지정한 todoId 하나만 삭제하며 위의 일반 Todo 삭제 응답을 반환합니다. 전체 삭제는 `DELETE /api/v1/todos/routines/{routineId}`를 사용합니다.


<a id="api-36"></a>

## 36. PUT /api/v1/todos/{todoId}/dependencies

Replace Dependencies

인증: Bearer accessToken 필수.

할 일은 로그인 사용자 모두에게 공개되며 visibility 설정이 없습니다. 그룹·멤버 관리와 그룹 화면의 groupId 쿼리는 유지합니다. 타인 조회에 groupId를 지정하면 공동 멤버십을 검사합니다. 수정·삭제·완료·선행 관계·하위 항목은 작성자만 가능하며 내기 생성만 상대방이 요청합니다. 목록은 선행 할 일이 먼저 나오도록 정렬합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `todoId` | integer | 예 |  |

### 요청 본문

`application/json`

스키마: [DependenciesRequest](#schema-dependenciesrequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "todoId": 10,
  "dependencies": [
    1,
    2
  ]
}
```


<a id="api-37"></a>

## 37. POST /api/v1/todos/{todoId}/dependencies

Create Dependency

인증: Bearer accessToken 필수.

할 일은 로그인 사용자 모두에게 공개되며 visibility 설정이 없습니다. 그룹·멤버 관리와 그룹 화면의 groupId 쿼리는 유지합니다. 타인 조회에 groupId를 지정하면 공동 멤버십을 검사합니다. 수정·삭제·완료·선행 관계·하위 항목은 작성자만 가능하며 내기 생성만 상대방이 요청합니다. 목록은 선행 할 일이 먼저 나오도록 정렬합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `todoId` | integer | 예 |  |

### 요청 본문

`application/json`

스키마: [DependencyCreateRequest](#schema-dependencycreaterequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 201 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "todoId": 10,
  "dependencyTodoId": 2
}
```


<a id="api-38"></a>

## 38. DELETE /api/v1/todos/{todoId}/dependencies/{dependencyTodoId}

Remove Dependency

인증: Bearer accessToken 필수.

할 일은 로그인 사용자 모두에게 공개되며 visibility 설정이 없습니다. 그룹·멤버 관리와 그룹 화면의 groupId 쿼리는 유지합니다. 타인 조회에 groupId를 지정하면 공동 멤버십을 검사합니다. 수정·삭제·완료·선행 관계·하위 항목은 작성자만 가능하며 내기 생성만 상대방이 요청합니다. 목록은 선행 할 일이 먼저 나오도록 정렬합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `todoId` | integer | 예 |  |
| path | `dependencyTodoId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "todoId": 10,
  "dependencies": [
    1
  ]
}
```


<a id="api-39"></a>

## 39. POST /api/v1/todos/{todoId}/subtasks

Create Subtask

인증: Bearer accessToken 필수.

할 일은 로그인 사용자 모두에게 공개되며 visibility 설정이 없습니다. 그룹·멤버 관리와 그룹 화면의 groupId 쿼리는 유지합니다. 타인 조회에 groupId를 지정하면 공동 멤버십을 검사합니다. 수정·삭제·완료·선행 관계·하위 항목은 작성자만 가능하며 내기 생성만 상대방이 요청합니다. 목록은 선행 할 일이 먼저 나오도록 정렬합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `todoId` | integer | 예 |  |

### 요청 본문

`application/json`

스키마: [SubtaskCreateRequest](#schema-subtaskcreaterequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 201 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "subtaskId": 1,
  "content": "하위 할 일",
  "isCompleted": false
}
```

기존 하위 항목 생성 API입니다. 현재 하위 항목 자체를 PATCH/DELETE하거나 완료시키는 별도 엔드포인트는 없으며, 미완료 하위 항목이 있으면 Todo 완료가 400으로 거절됩니다. 설명 입력은 Todo.description을 사용합니다.


<a id="api-40"></a>

## 40. PATCH /api/v1/todos/{todoId}/complete

Complete Todo

인증: Bearer accessToken 필수.

할 일은 로그인 사용자 모두에게 공개되며 visibility 설정이 없습니다. 그룹·멤버 관리와 그룹 화면의 groupId 쿼리는 유지합니다. 타인 조회에 groupId를 지정하면 공동 멤버십을 검사합니다. 수정·삭제·완료·선행 관계·하위 항목은 작성자만 가능하며 내기 생성만 상대방이 요청합니다. 목록은 선행 할 일이 먼저 나오도록 정렬합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `todoId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "todoId": 10,
  "isCompleted": true
}
```


<a id="api-41"></a>

## 41. PATCH /api/v1/todos/{todoId}/uncomplete

Uncomplete Todo

인증: Bearer accessToken 필수.

할 일은 로그인 사용자 모두에게 공개되며 visibility 설정이 없습니다. 그룹·멤버 관리와 그룹 화면의 groupId 쿼리는 유지합니다. 타인 조회에 groupId를 지정하면 공동 멤버십을 검사합니다. 수정·삭제·완료·선행 관계·하위 항목은 작성자만 가능하며 내기 생성만 상대방이 요청합니다. 목록은 선행 할 일이 먼저 나오도록 정렬합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `todoId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "todoId": 10,
  "isCompleted": false
}
```


<a id="api-42"></a>

## 42. POST /api/v1/todos/{todoId}/bets

Create Bet

인증: Bearer accessToken 필수.

할 일은 로그인 사용자 모두에게 공개되며 visibility 설정이 없습니다. 그룹·멤버 관리와 그룹 화면의 groupId 쿼리는 유지합니다. 타인 조회에 groupId를 지정하면 공동 멤버십을 검사합니다. 수정·삭제·완료·선행 관계·하위 항목은 작성자만 가능하며 내기 생성만 상대방이 요청합니다. 목록은 선행 할 일이 먼저 나오도록 정렬합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `todoId` | integer | 예 |  |

### 요청 본문

`application/json`

스키마: [BetCreateRequest](#schema-betcreaterequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 201 | [BetResponse](#schema-betresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-43"></a>

## 43. GET /api/v1/bets

List Bets

인증: Bearer accessToken 필수.

목록/상세/증빙 이미지 읽기는 내기 요청자 또는 Todo 작성자만 가능합니다. 수락·거절·사진 제출은 Todo 작성자, 증빙 검증은 내기 요청자만 가능합니다. 사진 제출은 ACCEPTED 상태, 검증은 수락과 사진 제출 이후에 가능합니다.

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | Array&lt;[BetResponse](#schema-betresponse)&gt; | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-44"></a>

## 44. GET /api/v1/bets/{betId}

Get Bet

인증: Bearer accessToken 필수.

목록/상세/증빙 이미지 읽기는 내기 요청자 또는 Todo 작성자만 가능합니다. 수락·거절·사진 제출은 Todo 작성자, 증빙 검증은 내기 요청자만 가능합니다. 사진 제출은 ACCEPTED 상태, 검증은 수락과 사진 제출 이후에 가능합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `betId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | [BetResponse](#schema-betresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-45"></a>

## 45. PATCH /api/v1/bets/{betId}/status

Update Bet Status

인증: Bearer accessToken 필수.

목록/상세/증빙 이미지 읽기는 내기 요청자 또는 Todo 작성자만 가능합니다. 수락·거절·사진 제출은 Todo 작성자, 증빙 검증은 내기 요청자만 가능합니다. 사진 제출은 ACCEPTED 상태, 검증은 수락과 사진 제출 이후에 가능합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `betId` | integer | 예 |  |

### 요청 본문

`application/json`

스키마: [BetStatusRequest](#schema-betstatusrequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | [BetResponse](#schema-betresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-46"></a>

## 46. POST /api/v1/bets/{betId}/proof

Upload Bet Proof

인증: Bearer accessToken 필수.

목록/상세/증빙 이미지 읽기는 내기 요청자 또는 Todo 작성자만 가능합니다. 수락·거절·사진 제출은 Todo 작성자, 증빙 검증은 내기 요청자만 가능합니다. 사진 제출은 ACCEPTED 상태, 검증은 수락과 사진 제출 이후에 가능합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `betId` | integer | 예 |  |

### 요청 본문

`multipart/form-data`: 필수 `image` 파일. OpenAPI에는 이 수동 form 파싱 필드가 선언되어 있지 않아 코드 기준으로 보완했습니다.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "betId": 1,
  "proofImageUrl": "/uploads/bet-proofs/<filename>.png"
}
```


<a id="api-47"></a>

## 47. PATCH /api/v1/bets/{betId}/verify

Verify Bet

인증: Bearer accessToken 필수.

목록/상세/증빙 이미지 읽기는 내기 요청자 또는 Todo 작성자만 가능합니다. 수락·거절·사진 제출은 Todo 작성자, 증빙 검증은 내기 요청자만 가능합니다. 사진 제출은 ACCEPTED 상태, 검증은 수락과 사진 제출 이후에 가능합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `betId` | integer | 예 |  |

### 요청 본문

`application/json`

스키마: [BetVerifyRequest](#schema-betverifyrequest)

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | [BetResponse](#schema-betresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-48"></a>

## 48. POST /api/v1/diaries

Create Diary

인증: Bearer accessToken 필수.

생성/수정/삭제는 작성자만 가능합니다. PUBLIC은 같은 그룹원에게 공개, PRIVATE와 보류 중인 GROUP은 작성자만 조회합니다. 이미지에도 같은 권한을 적용합니다. 타인 목록 조회에 groupId가 있으면 공동 멤버십을 검사합니다.

### 요청 본문

`application/json`

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `date` | string (date) | 아니오 |  |
| `content` | string | 예 | 최소 길이: 1; 최대 길이: 10000; 정규식: \S |
| `imageUrl` | string / null | 아니오 |  |
| `emotion` | string / null | 아니오 | 최대 길이: 40 |
| `visibility` | string | 아니오 | 허용: "PRIVATE", "GROUP", "PUBLIC"; 기본: "PRIVATE"; PUBLIC=같은 그룹원, PRIVATE=나만. GROUP(일부 공개)은 보류 상태로 작성자만 조회할 수 있습니다. |

정의하지 않은 필드는 거절합니다.

`multipart/form-data`

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `date` | string (date) | 아니오 |  |
| `content` | string | 예 | 최소 길이: 1; 최대 길이: 10000; 정규식: \S |
| `imageUrl` | string / null | 아니오 |  |
| `emotion` | string / null | 아니오 | 최대 길이: 40 |
| `visibility` | string | 아니오 | 허용: "PRIVATE", "GROUP", "PUBLIC"; 기본: "PRIVATE"; PUBLIC=같은 그룹원, PRIVATE=나만. GROUP(일부 공개)은 보류 상태로 작성자만 조회할 수 있습니다. |
| `image` | string (binary) | 아니오 |  |

정의하지 않은 필드는 거절합니다.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 201 | [DiaryResponse](#schema-diaryresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-49"></a>

## 49. GET /api/v1/diaries

List Diaries

인증: Bearer accessToken 필수.

생성/수정/삭제는 작성자만 가능합니다. PUBLIC은 같은 그룹원에게 공개, PRIVATE와 보류 중인 GROUP은 작성자만 조회합니다. 이미지에도 같은 권한을 적용합니다. 타인 목록 조회에 groupId가 있으면 공동 멤버십을 검사합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| query | `date` | string (date) / null | 아니오 |  |
| query | `userId` | integer / null | 아니오 |  |
| query | `groupId` | integer / null | 아니오 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | Array&lt;[DiaryResponse](#schema-diaryresponse)&gt; | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-50"></a>

## 50. GET /api/v1/diaries/{diaryId}

Get Diary

인증: Bearer accessToken 필수.

생성/수정/삭제는 작성자만 가능합니다. PUBLIC은 같은 그룹원에게 공개, PRIVATE와 보류 중인 GROUP은 작성자만 조회합니다. 이미지에도 같은 권한을 적용합니다. 타인 목록 조회에 groupId가 있으면 공동 멤버십을 검사합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `diaryId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | [DiaryResponse](#schema-diaryresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-51"></a>

## 51. PATCH /api/v1/diaries/{diaryId}

Update Diary

인증: Bearer accessToken 필수.

생성/수정/삭제는 작성자만 가능합니다. PUBLIC은 같은 그룹원에게 공개, PRIVATE와 보류 중인 GROUP은 작성자만 조회합니다. 이미지에도 같은 권한을 적용합니다. 타인 목록 조회에 groupId가 있으면 공동 멤버십을 검사합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `diaryId` | integer | 예 |  |

### 요청 본문

`application/json`

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `date` | string (date) / null | 아니오 |  |
| `content` | string / null | 아니오 | 최소 길이: 1; 최대 길이: 10000; 정규식: \S |
| `imageUrl` | string / null | 아니오 |  |
| `emotion` | string / null | 아니오 | 최대 길이: 40 |
| `visibility` | string / null | 아니오 | 허용: "PRIVATE", "GROUP", "PUBLIC" |

정의하지 않은 필드는 거절합니다.

`multipart/form-data`

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `date` | string (date) / null | 아니오 |  |
| `content` | string / null | 아니오 | 최소 길이: 1; 최대 길이: 10000; 정규식: \S |
| `imageUrl` | string / null | 아니오 |  |
| `emotion` | string / null | 아니오 | 최대 길이: 40 |
| `visibility` | string / null | 아니오 | 허용: "PRIVATE", "GROUP", "PUBLIC" |
| `image` | string (binary) | 아니오 |  |

정의하지 않은 필드는 거절합니다.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | [DiaryResponse](#schema-diaryresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-52"></a>

## 52. DELETE /api/v1/diaries/{diaryId}

Delete Diary

인증: Bearer accessToken 필수.

생성/수정/삭제는 작성자만 가능합니다. PUBLIC은 같은 그룹원에게 공개, PRIVATE와 보류 중인 GROUP은 작성자만 조회합니다. 이미지에도 같은 권한을 적용합니다. 타인 목록 조회에 groupId가 있으면 공동 멤버십을 검사합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `diaryId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "message": "처리 결과 메시지"
}
```


<a id="api-53"></a>

## 53. GET /api/v1/notifications

List Notifications

인증: Bearer accessToken 필수.

본인이 받은 알림만 조회/읽음 처리합니다. 종류 TODO_COMPLETED, DIARY_CREATED, BET_REQUESTED. cursor는 이전 페이지의 nextCursor, nextCursor=null이면 마지막 페이지입니다. 그룹 탈퇴 및 일기 비공개 전환에 따라 활동 알림의 조회 권한을 다시 검사합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| query | `type` | string / null | 아니오 | 허용: "TODO_COMPLETED", "DIARY_CREATED", "BET_REQUESTED" |
| query | `cursor` | integer / null | 아니오 | 초과: 0 |
| query | `limit` | integer | 아니오 | 기본: 30; 최솟값: 1; 최댓값: 100 |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | [NotificationsPageResponse](#schema-notificationspageresponse) | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |


<a id="api-54"></a>

## 54. PATCH /api/v1/notifications/{notificationId}/read

Read Notification

인증: Bearer accessToken 필수.

본인이 받은 알림만 조회/읽음 처리합니다. 종류 TODO_COMPLETED, DIARY_CREATED, BET_REQUESTED. cursor는 이전 페이지의 nextCursor, nextCursor=null이면 마지막 페이지입니다. 그룹 탈퇴 및 일기 비공개 전환에 따라 활동 알림의 조회 권한을 다시 검사합니다.

### 파라미터

| 위치 | 이름 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- | --- |
| path | `notificationId` | integer | 예 |  |

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |
| 422 | [HTTPValidationError](#schema-httpvalidationerror) | Validation Error |

실제 반환 필드 기준 예시:

```json
{
  "success": true,
  "notificationId": 1,
  "readAt": "2026-09-08T09:00:00"
}
```


<a id="api-55"></a>

## 55. GET /ping

Ping

인증: Bearer 인증 없음.

요청 본문: 없음.

### 응답

| HTTP | 형식 | 설명 |
| --- | --- | --- |
| 200 | 아래 코드 기준 예시 참고 | Successful Response |

실제 반환 필드 기준 예시:

```json
"pong"
```


## 요청 / 응답 스키마 사전

각 엔드포인트의 스키마 링크는 아래의 필드 정의를 가리킵니다. nullable은 null 가능을 뜻하며 PATCH의 추가 검증은 후반 동작 계약을 함께 적용합니다.

<a id="schema-actorresponse"></a>

### ActorResponse

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `userId` | integer | 예 |  |
| `name` | string | 예 |  |
| `profileImageUrl` | string / null | 예 |  |

<a id="schema-betcreaterequest"></a>

### BetCreateRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `content` | string | 예 | 최소 길이: 1; 최대 길이: 1000; 정규식: \S |

정의하지 않은 필드는 거절합니다.

<a id="schema-betresponse"></a>

### BetResponse

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `betId` | integer | 예 |  |
| `todoId` | integer | 예 |  |
| `content` | string | 예 |  |
| `requesterId` | integer | 예 |  |
| `status` | string | 예 |  |
| `proofImageUrl` | string / null | 예 |  |
| `isVerified` | boolean | 예 |  |

<a id="schema-betstatusrequest"></a>

### BetStatusRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `status` | string | 예 | 허용: "ACCEPTED", "REJECTED" |

<a id="schema-betverifyrequest"></a>

### BetVerifyRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `approved` | boolean | 아니오 | 기본: true |

<a id="schema-categorypatchrequest"></a>

### CategoryPatchRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `name` | string / null | 아니오 | 최소 길이: 1; 최대 길이: 80; 정규식: \S |
| `color` | string / null | 아니오 | 정규식: ^#[0-9A-Fa-f]{6}$ |

정의하지 않은 필드는 거절합니다.

<a id="schema-categoryrequest"></a>

### CategoryRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `name` | string | 예 | 최소 길이: 1; 최대 길이: 80; 정규식: \S |
| `color` | string | 예 | 정규식: ^#[0-9A-Fa-f]{6}$ |

정의하지 않은 필드는 거절합니다.

<a id="schema-categorystatusresponse"></a>

### CategoryStatusResponse

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `categoryId` | integer | 예 |  |
| `isCompleted` | boolean | 예 |  |

<a id="schema-dailystatusresponse"></a>

### DailyStatusResponse

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `date` | string (date) | 예 |  |
| `incompleteCount` | integer | 예 |  |
| `categoryStatuses` | Array&lt;[CategoryStatusResponse](#schema-categorystatusresponse)&gt; | 예 |  |

<a id="schema-dependenciesrequest"></a>

### DependenciesRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `dependencyTodoIds` | Array&lt;integer&gt; | 예 | 최대 항목: 100 |

정의하지 않은 필드는 거절합니다.

<a id="schema-dependencycreaterequest"></a>

### DependencyCreateRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `dependencyTodoId` | integer | 예 |  |

<a id="schema-diaryresponse"></a>

### DiaryResponse

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `diaryId` | integer | 예 |  |
| `userId` | integer | 예 |  |
| `date` | string (date) | 예 |  |
| `content` | string | 예 |  |
| `imageUrl` | string / null | 예 |  |
| `emotion` | string / null | 예 |  |
| `visibility` | string | 예 |  |
| `createdAt` | string / null | 예 |  |

<a id="schema-discordlinkrequest"></a>

### DiscordLinkRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `discordAuthCode` | string | 예 | 최소 길이: 1 |

<a id="schema-fontsettingrequest"></a>

### FontSettingRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `font` | string | 예 |  |

<a id="schema-googleloginrequest"></a>

### GoogleLoginRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `googleAccessToken` | string | 예 | 최소 길이: 1 |

<a id="schema-groupcreaterequest"></a>

### GroupCreateRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `name` | string | 예 | 최소 길이: 1; 최대 길이: 120; 정규식: \S |
| `description` | string | 아니오 | 기본: "" |

<a id="schema-groupjoinrequest"></a>

### GroupJoinRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `inviteCode` | string | 예 | 정규식: ^[a-z0-9]{8}$ |

<a id="schema-grouprenamerequest"></a>

### GroupRenameRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `name` | string | 예 | 최소 길이: 1; 최대 길이: 120; 정규식: \S |

정의하지 않은 필드는 거절합니다.

<a id="schema-httpvalidationerror"></a>

### HTTPValidationError

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `detail` | Array&lt;[ValidationError](#schema-validationerror)&gt; | 아니오 |  |

<a id="schema-membersremoverequest"></a>

### MembersRemoveRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `userIds` | Array&lt;integer&gt; | 예 | 최소 항목: 1; 최대 항목: 30 |

정의하지 않은 필드는 거절합니다.

<a id="schema-notificationresponse"></a>

### NotificationResponse

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `notificationId` | integer | 예 |  |
| `type` | string | 예 |  |
| `actor` | [ActorResponse](#schema-actorresponse) | 예 |  |
| `todo` | [TodoPreviewResponse](#schema-todopreviewresponse) / null | 예 |  |
| `diaryId` | integer / null | 예 |  |
| `bet` | [BetResponse](#schema-betresponse) / null | 예 |  |
| `createdAt` | string | 예 |  |
| `readAt` | string / null | 예 |  |

<a id="schema-notificationsettingsrequest"></a>

### NotificationSettingsRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `discordAlertEnabled` | boolean | 예 |  |

<a id="schema-notificationspageresponse"></a>

### NotificationsPageResponse

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `items` | Array&lt;[NotificationResponse](#schema-notificationresponse)&gt; | 예 |  |
| `nextCursor` | integer / null | 예 |  |

<a id="schema-recurrence"></a>

### Recurrence

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `frequency` | string | 예 | 허용: "DAILY", "WEEKLY", "MONTHLY", "YEARLY" |
| `interval` | integer | 아니오 | 기본: 1; 최솟값: 1; 최댓값: 2 |
| `weekdays` | Array&lt;integer&gt; / null | 아니오 | 최소 항목: 1; 최대 항목: 7 |

정의하지 않은 필드는 거절합니다.

<a id="schema-refreshtokenrequest"></a>

### RefreshTokenRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `refreshToken` | string | 예 | 최소 길이: 1 |

<a id="schema-routinecreaterequest"></a>

### RoutineCreateRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `time` | string (time) / null | 아니오 |  |
| `timezone` | string | 아니오 | 기본: "Asia/Seoul" |
| `requestId` | string (uuid) | 예 |  |
| `startDate` | string (date) | 예 |  |
| `endDate` | string (date) | 예 |  |
| `recurrence` | [Recurrence](#schema-recurrence) / null | 아니오 |  |
| `weekdays` | Array&lt;integer&gt; / null | 아니오 | 최소 항목: 1; 최대 항목: 7; 이전 클라이언트 호환 필드. recurrence와 동시에 보내지 않습니다. |
| `title` | string | 예 | 최소 길이: 1; 최대 길이: 40; 정규식: \S |
| `description` | string | 아니오 | 기본: ""; 최대 길이: 100 |
| `categoryId` | integer | 예 |  |
| `importance` | string | 아니오 | 허용: "NONE", "LOW", "HIGH"; 기본: "NONE" |
| `hardship` | integer | 아니오 | 기본: 1; 최솟값: 1; 최댓값: 5 |
| `x` | number | 아니오 | 기본: 0 |
| `y` | number | 아니오 | 기본: 0 |

정의하지 않은 필드는 거절합니다.

<a id="schema-routinecreateresponse"></a>

### RoutineCreateResponse

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `routineId` | integer | 예 |  |
| `createdCount` | integer | 예 |  |
| `occurrences` | Array&lt;[RoutineOccurrenceResponse](#schema-routineoccurrenceresponse)&gt; | 예 |  |

정의하지 않은 필드는 거절합니다.

<a id="schema-routinedeleteresponse"></a>

### RoutineDeleteResponse

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `success` | boolean | 예 |  |
| `routineId` | integer | 예 |  |
| `deletedCount` | integer | 예 |  |

<a id="schema-routineoccurrenceresponse"></a>

### RoutineOccurrenceResponse

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `todoId` | integer | 예 |  |
| `dueDate` | string (date) | 예 |  |

정의하지 않은 필드는 거절합니다.

<a id="schema-routineresponse"></a>

### RoutineResponse

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `routineId` | integer | 예 |  |
| `definition` | object | 예 |  |

<a id="schema-routineschedulerequest"></a>

### RoutineScheduleRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `time` | string (time) / null | 아니오 |  |
| `timezone` | string | 아니오 | 기본: "Asia/Seoul" |
| `requestId` | string (uuid) | 예 |  |
| `startDate` | string (date) | 예 |  |
| `endDate` | string (date) | 예 |  |
| `recurrence` | [Recurrence](#schema-recurrence) / null | 아니오 |  |
| `weekdays` | Array&lt;integer&gt; / null | 아니오 | 최소 항목: 1; 최대 항목: 7; 이전 클라이언트 호환 필드. recurrence와 동시에 보내지 않습니다. |

정의하지 않은 필드는 거절합니다.

<a id="schema-subtaskcreaterequest"></a>

### SubtaskCreateRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `content` | string | 예 | 최소 길이: 1 |

<a id="schema-todocreaterequest"></a>

### TodoCreateRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `time` | string (time) / null | 아니오 |  |
| `timezone` | string | 아니오 | 기본: "Asia/Seoul" |
| `title` | string | 예 | 최소 길이: 1; 최대 길이: 40; 정규식: \S |
| `description` | string | 아니오 | 기본: ""; 최대 길이: 100 |
| `categoryId` | integer | 예 |  |
| `importance` | string | 아니오 | 허용: "NONE", "LOW", "HIGH"; 기본: "NONE" |
| `hardship` | integer | 아니오 | 기본: 1; 최솟값: 1; 최댓값: 5 |
| `startDate` | string (date) / null | 아니오 |  |
| `dueDate` | string (date) / null | 아니오 |  |
| `x` | number | 아니오 | 기본: 0 |
| `y` | number | 아니오 | 기본: 0 |

정의하지 않은 필드는 거절합니다.

<a id="schema-todopatchrequest"></a>

### TodoPatchRequest

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `time` | string (time) / null | 아니오 |  |
| `timezone` | string | 아니오 | 기본: "Asia/Seoul" |
| `title` | string / null | 아니오 | 최소 길이: 1; 최대 길이: 40; 정규식: \S |
| `description` | string / null | 아니오 | 최대 길이: 100 |
| `categoryId` | integer / null | 아니오 |  |
| `importance` | string / null | 아니오 | 허용: "NONE", "LOW", "HIGH" |
| `hardship` | integer / null | 아니오 | 최솟값: 1; 최댓값: 5 |
| `startDate` | string (date) / null | 아니오 |  |
| `dueDate` | string (date) / null | 아니오 |  |
| `x` | number / null | 아니오 |  |
| `y` | number / null | 아니오 |  |

정의하지 않은 필드는 거절합니다.

<a id="schema-todopreviewresponse"></a>

### TodoPreviewResponse

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `todoId` | integer | 예 |  |
| `title` | string | 예 |  |
| `description` | string | 예 |  |

<a id="schema-todoresponse"></a>

### TodoResponse

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `todoId` | integer | 예 |  |
| `userId` | integer | 예 |  |
| `title` | string | 예 |  |
| `description` | string | 예 |  |
| `categoryId` | integer | 예 |  |
| `startDate` | string (date) | 예 |  |
| `dueDate` | string (date) / null | 예 |  |
| `time` | string / null | 예 |  |
| `timezone` | string | 예 |  |
| `importance` | string | 예 |  |
| `hardship` | integer | 예 |  |
| `x` | number | 예 |  |
| `y` | number | 예 |  |
| `isRoutine` | boolean | 예 |  |
| `routineId` | integer / null | 예 |  |
| `isCompleted` | boolean | 예 |  |
| `subtasks` | Array&lt;object&gt; | 예 |  |
| `dependencies` | Array&lt;integer&gt; | 예 |  |
| `createdAt` | string / null | 예 |  |
| `completedAt` | string / null | 예 |  |

<a id="schema-validationerror"></a>

### ValidationError

| 필드 | 타입 | 필수 | 규칙 / 기본값 |
| --- | --- | --- | --- |
| `loc` | Array&lt;string / integer&gt; | 예 |  |
| `msg` | string | 예 |  |
| `type` | string | 예 |  |
| `input` | any (임의 JSON 값) | 아니오 | 검증에 실패한 입력값 |
| `ctx` | object | 아니오 |  |


## 세부 동작 · 배포 · JavaScript 연동 부록

다음은 같은 커밋의 상세 동작 계약 및 루틴 가이드를 통합한 내용입니다. 일부 제목/설명은 앞의 자동 명세와 중복될 수 있습니다.

### Figma 기반 백엔드 계약

기준: 2026-09-08, [TLITODOS Design](https://www.figma.com/design/6mBMtcwDlauTX5Gipia3Ua/TLITODOS-Design?node-id=7-2).
디자인은 수정하지 않았습니다. 사용자 확정 사항이 정적 화면 예시보다 우선합니다.
이 문서와 `openapi.json`은 `codex/no-auto-personal-group` 브랜치의 구현을 설명하며, 운영 배포 완료를 의미하지 않습니다.

#### 확정된 동작

- 신규 가입과 서버 시작 시 기본 데이터 초기화에서 개인 그룹을 자동 생성하지 않습니다.
  기본 카테고리는 유지하며, 기존 개인 그룹과 멤버십 데이터도 삭제하지 않습니다.
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

#### 1. 할 일 / 달력

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

#### 2. 루틴

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

#### 3. 일기와 이미지

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

#### 4. 내기와 알림

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
PATCH /api/v1/notifications/120/read
```

응답: `{items: [...], nextCursor: number | null}`. type 생략 시 전체, limit 1~100.
항목에는 notificationId, type, actor(이름/사진/ID), todo(제목/설명/ID), diaryId, bet, createdAt, readAt이 포함됩니다.
이벤트와 원본 변경을 같은 DB 트랜잭션에 저장합니다. 여러 그룹을 공유해도 한 이벤트의 수신자별 알림은 하나입니다.
공개 일기 생성/비공개→공개 시 그룹원에게 알림을 보냅니다. 비공개 전환 시 해당 알림을 제거합니다.
그룹을 나간 후에는 과거 그룹원 활동 알림도 조회에서 제외합니다. 본인에게 온 내기 요청 알림은 유지합니다.
이 변경은 앱 내부 알림함이며, Discord 전송/웹 푸시/메일 발송은 추가하지 않았습니다.

#### 5. 그룹 / 프로필 / 카테고리

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

#### 배포 / 호환 주의사항

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

#### 검증 결과 (2026-09-08)

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
### 루틴 API 및 프론트 연동

피그마의 매일·매주·격주·매월·매년과 선택적 시간 설정을 지원합니다.
프론트에서 날짜마다 POST 요청을 보내는 루프는 제거하고, 아래 요청 한 번만 보냅니다.
서버가 반복 날짜를 계산하고 루틴과 회차별 Todo를 한 트랜잭션에 저장합니다.

#### 신규 루틴 생성

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

기간 상한의 정확한 코드 검증은 `(endDate - startDate).days <= 36600`입니다.
양끝을 포함한 달력 날짜 수와 날짜 차이는 1일 차이가 있으며, 실제 생성 회차 수는 별도로 1,000개 이하입니다.

- 매일: DAILY. 날짜 범위의 모든 날짜.
- 매월: MONTHLY. 시작일과 같은 일자. 1/31 시작이면 2월/4월 등은 건너뜁니다.
- 매년: YEARLY. 시작일과 같은 월·일. 2/29 시작이면 윤년에만 생성합니다.
- 없는 날짜를 말일로 이동하지 않습니다.
- 호환용 최상위 weekdays도 지원합니다. 생략하면 매일, [1,3,5]면 매주 월수금입니다.
  recurrence와 동시에 보내면 422입니다.
- groupId, visibility, dueDate, isRoutine은 요청하지 않습니다.
  날짜별 Todo는 startDate=dueDate=그 회차 날짜, isRoutine=true, routineId를 가집니다.
- 날짜별 완료 상태는 독립적이며, 같은 회차가 여러 날짜에 걸치도록 개별 수정하면 그 기간에는 동일한 완료 상태를 표시합니다.

#### 기존 할 일을 루틴으로 전환

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

#### 중복 방지와 재시도

같은 사용자/requestId/정규화된 본문이면 생성 당시 결과를 반환합니다.
요일 순서나 중복은 정규화합니다. 내용이 바뀌면 409입니다.
서버 응답을 받지 못했다고 새 UUID를 발급하면 새 루틴이 만들어지므로, 실패 시 기존 요청을 보관하고 재사용하세요.

생성 결과는 불변 요청 기록이고, 이후 개별 Todo 수정은 이 기록을 바꾸지 않습니다.
전체 삭제된 루틴의 생성 재시도는 410입니다. 회차만 삭제한 경우에는 최초 생성 응답을 그대로 반환하지만 삭제한 회차를 다시 생성하지 않습니다. 현재 회차 목록은 GET /todos로 다시 조회하세요.
루틴 규칙 조회는 GET /api/v1/todos/routines/{routineId}, 현재 회차 상태는 Todo 조회를 사용합니다.

#### JavaScript 연동 예제

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

#### 전체 삭제

```js
const response = await fetch(`${API_URL}/api/v1/todos/routines/${routineId}`, {
  method: "DELETE",
  headers: { Authorization: `Bearer ${accessToken}` },
});
if (!response.ok) throw new Error("루틴 삭제 실패");
const { deletedCount } = await response.json();
```

- 완료된 회차와 원본을 포함해 전부 삭제합니다. 프론트에서 전체 삭제임을 알리고 호출하세요.
- 회차 Todo의 DELETE /todos/{todoId}는 해당 회차만 삭제합니다. 다른 날짜는 유지됩니다.
- 남아 있는 다른 Todo의 선행 참조와 회차에 달린 내기/알림도 정리합니다.
- 루틴 ID로 삭제를 재호출하면 성공, deletedCount: 0입니다.
- 개별 Todo PATCH는 해당 회차에만 적용합니다. 전체 반복 규칙 변경 API는 이번 UI 범위에 포함하지 않습니다.
- 과거 isRoutine만 있고 routineId가 없는 행은 자동 묶기/전체 삭제 대상으로 추정하지 않습니다.

#### 오류

| 상태 | 의미 |
| --- | --- |
| 201 | 최초 생성 또는 동일 생성 요청의 재응답 |
| 401 | 로그인/토큰 갱신 필요 |
| 404 | 본인 카테고리/원본 Todo/루틴이 없음 |
| 409 | 요청 키와 본문 충돌 또는 이미 루틴인 Todo를 다시 전환 |
| 410 | 삭제한 루틴. 같은 키로 재생성하지 않음 |
| 422 | 기간/시간/요일/제목/발생 횟수 등 검증 오류 |
| 네트워크 오류/5xx | 저장 여부가 불확실하므로 같은 키/본문으로 재시도 |

#### DB와 배포

todo_routines.definition은 정규화된 최초 요청, creation_result는 최초 응답입니다.
Todo.routine_id와 occurrence_date가 회차를 연결하고, 두 값에 유일성을 적용합니다.
개별 Todo의 날짜를 수정해도 occurrence_date(원래 발생 날짜)는 변하지 않습니다.
전체 삭제 시 Todo 행을 제거하고 내부 루틴 요청 기록에 deleted_at을 남깁니다.
기간 내 실제 회차를 저장하는 방식이며, 무한 반복/조회 시 가상 생성 방식은 아닙니다.

기존 날짜 데이터 backfill, 보호 이미지 URL, 공개 정책 변경, 테스트/배포 절차는
[전체 계약](figma-backend-contract.md)의 배포 항목을 함께 확인하세요.
