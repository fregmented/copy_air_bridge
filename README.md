# copy_air_bridge

Tuya IoT 에어컨을 로컬 네트워크에서 TinyTuya로 제어하고 SmartThings Edge Driver와 연동하기 위한 브리지입니다.

## 구조

- `src/copy_air_bridge/`: Python 서버 스켈레톤입니다.
  - `config.py`: `data/settings.yaml` 로딩 및 검증 모델입니다.
  - `tuya_model.py`: Tuya DP ID, 코드, 접근 권한, 값 범위 정의와 명령 검증입니다.
  - `tuya_client.py`: TinyTuya 클라이언트 래퍼입니다.
  - `server.py`: FastAPI 기반 로컬 API 진입점입니다.
- `smartthings-edge/`: SmartThings Edge Driver 스켈레톤입니다.
  - `src/init.lua`: Driver 진입점과 기본 capability handler입니다.
  - `src/tuya_mappings.lua`: SmartThings capability와 Tuya code 변환 테이블입니다.
  - `profiles/air-conditioner.yml`: 에어컨 디바이스 프로필입니다.
- `data/settings.example.yaml`: 실제 credential 없이 제공되는 런타임 설정 예시입니다.
- `Dockerfile`, `compose.yaml`: Docker 배포 골격입니다.

## Python 서버 실행

```bash
cp data/settings.example.yaml data/settings.yaml
uv sync
uv run copy-air-bridge
```

`data/settings.yaml`에는 실제 Tuya `device_id`, `local_key`, IP 주소를 로컬 환경에서만 입력하세요.

## Docker 실행

```bash
cp data/settings.example.yaml data/settings.yaml
docker compose up --build
```

## API 초안

- `GET /health`: 서버 상태 확인
- `GET /model`: Tuya DP 모델 확인
- `GET /status`: TinyTuya 상태 조회
- `GET /buttons`: 현재 디바이스 상태에서 조작 가능한 버튼 목록 조회
- `POST /commands/{code}`: 쓰기 가능한 Tuya code에 값 설정

## SmartThings Edge Driver Discovery

Edge Driver는 Python 서버의 호스트와 포트를 수동 설정하지 않고 SSDP `M-SEARCH`로 찾습니다.
Python 서버는 `data/settings.yaml`의 `ssdp.enabled`가 `true`일 때 `LOCATION` 헤더로 브리지 API 주소를 광고합니다.
서버 주소나 포트가 바뀐 경우에도 Edge Driver는 기존 캐시 요청이 실패하면 SSDP discovery를 다시 수행합니다.

## SmartThings Edge Driver 배포 및 설치

### 사전 준비

1. SmartThings 허브와 이 브리지 서버를 같은 로컬 네트워크에 연결합니다.
2. SmartThings CLI를 설치하고 삼성 계정으로 로그인합니다.

   ```bash
   npm install -g @smartthings/cli
   smartthings login
   ```

3. 브리지 서버가 실행 중이고 SSDP discovery가 켜져 있는지 확인합니다.

   ```bash
   cp data/settings.example.yaml data/settings.yaml
   uv sync
   uv run copy-air-bridge
   ```

   `data/settings.yaml`에는 실제 Tuya `device_id`, `local_key`, IP 주소를 로컬 환경에서만 입력하고 저장소에 커밋하지 마세요.
   SmartThings Edge Driver가 자동으로 서버를 찾으려면 `ssdp.enabled`를 `true`로 설정해야 합니다.

### 드라이버 패키징

저장소 루트에서 Edge Driver 디렉터리를 기준으로 패키지를 빌드합니다.

```bash
smartthings edge:drivers:package smartthings-edge
```

성공하면 CLI 출력에 패키징된 드라이버의 `driverId`가 표시됩니다.
이후 명령에서 드라이버를 선택하라는 프롬프트가 나오면 `copy-air-bridge` 또는 방금 생성된 `driverId`를 선택합니다.

### 채널 생성 및 드라이버 등록

Edge Driver는 개인 채널에 등록한 뒤 허브에 설치합니다.

```bash
smartthings edge:channels:create
smartthings edge:channels:assign
smartthings edge:channels:enroll
```

- `edge:channels:create`: 개인 배포 채널을 생성합니다. 이미 사용할 채널이 있으면 생략할 수 있습니다.
- `edge:channels:assign`: 패키징한 `copy-air-bridge` 드라이버를 채널에 추가합니다.
- `edge:channels:enroll`: 드라이버를 설치할 SmartThings 허브를 해당 채널에 등록합니다.

CLI가 채널, 드라이버, 허브를 선택하라고 요청하면 현재 계정의 채널과 대상 허브를 선택합니다.

### 허브에 드라이버 설치

채널 등록이 끝나면 대상 허브에 드라이버를 설치합니다.

```bash
smartthings edge:drivers:install
```

설치 대상 허브와 `copy-air-bridge` 드라이버를 선택합니다.
설치 상태는 다음 명령으로 확인할 수 있습니다.

```bash
smartthings edge:drivers:installed
```

### 디바이스 추가 및 동작 확인

1. SmartThings 앱에서 `기기 추가`를 실행합니다.
2. `주변 검색` 또는 `Scan nearby`를 선택합니다.
3. 허브가 설치된 Edge Driver를 통해 `Tuya Air Conditioner` 디바이스를 생성하는지 확인합니다.
4. 생성된 디바이스에서 전원, 모드, 목표 온도, 팬 속도 같은 쓰기 가능한 명령을 실행합니다.
5. 브리지 서버 로그에서 SmartThings 요청이 들어오고 TinyTuya 명령이 전송되는지 확인합니다.

드라이버 로그를 실시간으로 확인하려면 다음 명령을 사용합니다.

```bash
smartthings edge:drivers:logcat
```

로그 대상 허브와 `copy-air-bridge` 드라이버를 선택한 뒤 discovery, capability handler, API 요청 실패 여부를 확인합니다.

### 문제 해결 체크리스트

- 드라이버가 검색되지 않으면 허브와 브리지 서버가 같은 서브넷에 있는지 확인합니다.
- 브리지 서버가 Docker로 실행 중이면 컨테이너가 SSDP multicast를 송수신할 수 있는 네트워크 모드인지 확인합니다.
- `GET /health`, `GET /model`, `GET /status`가 브리지 서버에서 정상 응답하는지 확인합니다.
- `data/settings.yaml`의 Tuya `device_id`, `local_key`, IP 주소, protocol version이 실제 기기와 일치하는지 확인합니다.
- `ssdp.enabled`가 `true`인지 확인하고, 서버 주소나 포트를 바꾼 뒤에는 드라이버 로그에서 discovery 재시도 여부를 확인합니다.
- 명령이 거부되면 현재 기기 상태에서 허용되지 않는 조작일 수 있습니다. 예를 들어 전원이 꺼져 있으면 전원 켜기 외의 명령은 차단됩니다.
- SmartThings 앱에 읽기 전용 DP가 명령으로 보이면 안 됩니다. 쓰기 가능한 capability만 노출되는지 프로필과 매핑을 확인합니다.

예시:

```bash
curl -X POST http://localhost:8080/commands/temp_set \
  -H 'Content-Type: application/json' \
  -d '{"value": 24}'
```
