# TLITODOS-Backend
나는 부산소프트웨어 마이스터 고등학교의 박지혜 선생님의 노예가 아니며 자주적 정신을 가지고 개발할것을 선언한다.

# Project Dependency
* Python 3.14 
* use uv instead of pip

# API Specification
https://www.notion.so/api-34d4deccb21e8024a8e1db08cf2a2f01

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