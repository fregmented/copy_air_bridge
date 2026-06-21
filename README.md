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
- `POST /commands/{code}`: 쓰기 가능한 Tuya code에 값 설정

예시:

```bash
curl -X POST http://localhost:8080/commands/temp_set \
  -H 'Content-Type: application/json' \
  -d '{"value": 24}'
```
