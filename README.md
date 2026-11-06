# TLITODOS-Backend
나는 부산소프트웨어마이스터고등학교의 박지혜 선생님의 노예가 아니며 자주적 정신을 가지고 개발할 것을 선언한다.

# Project Dependency
* Python 3.14 
* use uv instead of pip

# API Specification
https://www.notion.so/api-34d4deccb21e8024a8e1db08cf2a2f01

- [Figma 화면 기준 백엔드 계약 및 배포 주의사항](docs/figma-backend-contract.md)
- [전체 API 명세 — 58개 엔드포인트의 요청·응답·권한](docs/api-reference.md)
- [루틴 반복 규칙 / 단일 요청 / JS 연동](docs/routines.md)
- [OpenAPI](docs/openapi.json): `uv run python -m scripts.export_openapi`로 재생성


## Deployment

The API runs at `https://tlitodos-api.parafara.cloud` on the existing k3s GitOps
cluster. Deployment configuration lives in
[`parafara/tlitodos-backend-deploy`](https://github.com/parafara/tlitodos-backend-deploy),
on `main`, under `kubernetes/`. Argo CD reconciles that repository; this source
repository does not apply cluster resources directly. The legacy Jenkins/Compose
deployment is no longer used.

### Dependencies and local development

Use Python 3.14 or newer and uv. `uv.lock` records exact runtime and development
dependencies, including artifact hashes; commit it with dependency changes.

```sh
uv sync --locked --python 3.14.7
uv run --locked python -m pytest
uv run --locked --env-file .env uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Tests use in-memory SQLite by default. To include the PostgreSQL-specific schema
migration and concurrency tests, use a disposable PostgreSQL database named
`figma_qa` on `127.0.0.1` and set `TLITODOS_TEST_DATABASE_URL` to its asyncpg URL.
Never point tests at the production database. Update dependencies deliberately with
`uv lock --upgrade`, then commit `pyproject.toml` and `uv.lock` together as applicable.

### Container runtime

The root `Dockerfile` installs only locked production dependencies with uv 0.13.7
and runs Python 3.14.7 / Uvicorn on `0.0.0.0:8080` as UID/GID `10001:10001`.
The build context allowlist excludes environment files, Git metadata, tests, and
uploaded files. Uvicorn runs directly without uv or package installation at startup.

The Kubernetes deployment must use a read-only root filesystem, drop all Linux
capabilities, disallow privilege escalation, and provide these writable mounts:

- A persistent volume at `/app/uploads`, with `UPLOAD_DIR=/app/uploads` and
  ownership/access for UID/GID 10001 (the pod uses `fsGroup: 10001`).
- A temporary volume at `/tmp`, used for multipart upload spooling.

`GET /ping` returns `"pong"` and is the startup/readiness/liveness endpoint.
The image defaults `FORWARDED_ALLOW_IPS` to `127.0.0.1`. Production sets it to
`10.52.0.0/16,127.0.0.1`, the k3s pod network and loopback, while NetworkPolicy
restricts API ingress to Traefik. Do not use `*` or trust arbitrary forwarded
headers from public clients.

Production secrets come from Vault path `tlitodos/backend` through External
Secrets, not from the image or checked-in `.env` files. `DATABASE_URL` uses the
`postgresql+asyncpg://` scheme and the PostgreSQL server at `10.42.2.3:5432`.
Configure `JWT_SECRET`, OAuth credentials/redirects, and any additional
`CORS_ORIGINS` in Vault. Database initialization/schema migration runs during
application startup; reverting an image digest does not revert database changes
or restore uploaded files. Back up both independently before risky changes.

### GitHub Actions

`.github/workflows/deploy.yml` follows the
[`Team-Glitched/narackrock-backend-v1` GitOps workflow](https://github.com/Team-Glitched/narackrock-backend-v1/blob/main/.github/workflows/deploy.yml):

1. Pull requests run the complete test suite on SQLite and disposable PostgreSQL,
   then build a `linux/amd64` image without publishing or accessing deploy keys.
2. Pushes to the default branch, `master`, run those tests, build and publish
   `ghcr.io/slaves-of-jihye/tlitodos-backend` with `master` and `sha-<commit>` tags.
3. After publication, the workflow replaces exactly one matching image reference
   in `parafara/tlitodos-backend-deploy`'s `kubernetes/deployment.yaml` with
   `ghcr.io/slaves-of-jihye/tlitodos-backend@sha256:<digest>`, commits it, and pushes
   to `main`. Argo CD then rolls out the pinned image.

Manual dispatch publishes/deploys only when run against `master`. Production
workflow runs are serialized without canceling an in-flight deployment; outdated
PR runs may be canceled.

Repository administrators must allow `GITHUB_TOKEN` to write GHCR packages and
install a write-enabled SSH deploy key scoped to `parafara/tlitodos-backend-deploy`.
Store its private half as the source repository Actions secret
`TLITODOS_DEPLOY_KEY`. Make the GHCR package publicly readable, or configure the
cluster's image-pull credentials separately. This workflow never receives cluster
or Vault credentials. Roll back by reverting the GitOps image digest commit;
review any database compatibility implications first.

# Folder Structure
## Presentation
Presentation 폴더의 폴더 구조는 대체로 명세서 기준으로
```
{API version}/{명세서에 기제된 role}/{endpoint의 v1이후 root path}
    |   Controller (네이밍은 알아서)<br>
    ㄴ   dto/
--------------------------------------------------------
예)
v1
  ㄴ authorization
    |    GoogleController
    |    UserController
    |    DiscordContrller
    ㄴ    dto/
```
### 주의
1. 컨트롤러의 이름에 루트 폴더의 목적을 포함치 아니하도록 주의합니다. <br>
    컨트롤러의 상위 폴더는 네임스페이스로 취급합니다.
2. 폴더 뎁스는 최대한 1~2로 유지하도록 합니다.
